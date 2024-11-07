import sys
import json
from collections import defaultdict, deque
from form_blocks import form_blocks
from util import flatten

def construct_cfg(blocks):
    """Constructs the control flow graph (CFG) for the given blocks."""
    labels, block_map = initialize_labels(blocks)
    cfg = build_cfg_edges(blocks, labels)
    return cfg, labels

def initialize_labels(blocks):
    """Initializes labels and creates a block map for the given blocks."""
    labels, block_map = [], {}
    for idx, block in enumerate(blocks):
        label = block[0].get('label', f'<bb{idx}>')
        labels.append(label)
        block_map[label] = block
    return labels, block_map

def build_cfg_edges(blocks, labels):
    """Builds edges for the CFG based on control flow instructions."""
    cfg = {label: [] for label in labels}
    for idx, block in enumerate(blocks):
        label = labels[idx]
        last_instr = block[-1] if block else None
        
        if last_instr and 'op' in last_instr:
            add_cfg_edge(cfg, label, last_instr, labels, idx, blocks)
        elif idx + 1 < len(blocks):
            cfg[label].append(labels[idx + 1])
    
    return cfg

def add_cfg_edge(cfg, label, last_instr, labels, idx, blocks):
    """Adds edges to the CFG based on the last instruction of a block."""
    op = last_instr['op']
    if op == 'br':
        cfg[label].extend(last_instr['labels'])
    elif op == 'jmp':
        cfg[label].append(last_instr['labels'][0])
    elif idx + 1 < len(blocks):
        cfg[label].append(labels[idx + 1])

def alias_analysis(blocks, cfg, labels, func_args, alloc_sites):
    """Performs alias analysis with enhanced precision on the control flow graph (CFG) for the given blocks."""
    block_map = dict(zip(labels, blocks))
    in_state, out_state = initialize_states(labels)
    init_state = initialize_func_args_state(func_args)

    worklist = deque(labels)
    while worklist:
        label = worklist.popleft()
        in_map = merge_predecessor_states(label, cfg, out_state, init_state)
        in_state[label] = in_map.copy()

        old_out = out_state[label]
        out_map = analyze_block(block_map[label], in_map, alloc_sites)
        out_state[label] = out_map

        # If the output state changes, reprocess successors
        if out_map != old_out:
            worklist.extend([succ for succ in cfg[label] if succ not in worklist])

    return in_state, out_state

def remove_dead_stores(func, alias_info, live_out):
    """Removes dead store instructions from a function based on alias and liveness analysis with in-block consecutive store elimination."""
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = construct_cfg(blocks)
    block_map = dict(zip(labels, blocks))

    for label in labels:
        block = block_map[label]
        alias_maps = alias_info[label]
        live_vars = live_out[label].copy()
        new_block = []
        last_store_target = None

        for idx in reversed(range(len(block))):
            instr = block[idx]
            if instr.get('op') == 'store':
                target = instr['args'][0]
                alias_set = alias_maps[idx].get(target, set())

                # Check for consecutive stores to the same target
                if last_store_target == alias_set:
                    continue  # Skip redundant store
                
                if is_dead_store(instr, alias_maps[idx], live_vars):
                    continue  # Skip dead store

                last_store_target = alias_set  # Update last seen store target

            # Update liveness for other instructions
            update_live_vars(instr, alias_maps[idx], live_vars)
            new_block.append(instr)

        block[:] = reversed(new_block)  # Update the block in-place with optimized instructions

    func['instrs'] = flatten([block_map[label] for label in labels])

def is_dead_store(instr, alias_map, live_vars):
    """Checks if a store instruction is dead (i.e., does not affect any live variable)."""
    if instr.get('op') == 'store':
        target = instr['args'][0]
        points_to = alias_map.get(target, set())
        return points_to.isdisjoint(live_vars) and 'unknown' not in points_to and 'unknown' not in live_vars
    return False


def initialize_states(labels):
    """Initializes the in_state and out_state for all labels."""
    return ({label: {} for label in labels}, {label: {} for label in labels})

def initialize_func_args_state(func_args):
    """Initializes the alias state for function arguments."""
    return {arg: {'unknown'} for arg in func_args}

def merge_predecessor_states(label, cfg, out_state, init_state):
    """Merges the output states of predecessors for initializing the input state of a block."""
    preds = [pred for pred in cfg if label in cfg[pred]]
    if preds:
        in_map = {}
        for pred in preds:
            for var, locs in out_state[pred].items():
                in_map.setdefault(var, set()).update(locs)
    else:
        in_map = {var: locs.copy() for var, locs in init_state.items()}
    return in_map

def analyze_block(block, in_map, alloc_sites):
    """Analyzes a block and updates the alias state based on instructions."""
    # Initialize state with copies of in_map to avoid modifying the original in_map.
    state = {var: locs.copy() for var, locs in in_map.items()}
    
    for instr in block:
        if 'op' not in instr:
            continue
        
        op = instr['op']
        dest = instr.get('dest')
        args = instr.get('args', [])
        
        if op == 'alloc' and dest:
            # x = alloc n: x points to this allocation
            state[dest] = {alloc_sites[id(instr)]}
        elif op == 'id' and dest and args:
            # x = id y: copy the alias information from y to x
            src = args[0]
            if src in state:
                state[dest] = state[src].copy()
        elif op == 'ptradd' and dest and args:
            # x = ptradd p offset: conservatively assume x may alias p
            src = args[0]
            if src in state:
                state[dest] = state[src].copy()
        elif op in {'load', 'call'} and dest:
            # x = load p or x = call: conservatively set x to unknown
            state[dest] = {'unknown'}

    return state

def memory_liveness_analysis(blocks, cfg, labels, alias_info):
    """Performs memory liveness analysis on control flow graph (CFG) blocks."""
    block_map = dict(zip(labels, blocks))
    live_in, live_out = initialize_liveness_states(labels)

    changed = True
    while changed:
        changed = False
        for label in reversed(labels):
            out_set = compute_out_set(cfg, label, live_in)
            old_in = live_in[label].copy()
            
            live_out[label] = out_set
            in_set = analyze_memory_uses(block_map[label], out_set, alias_info[label])
            live_in[label] = in_set
            
            if live_in[label] != old_in:
                changed = True

    return live_in, live_out

def initialize_liveness_states(labels):
    """Initializes empty live_in and live_out sets for each label."""
    return ({label: set() for label in labels}, {label: set() for label in labels})

def compute_out_set(cfg, label, live_in):
    """Computes the live_out set for a block based on its successors."""
    out_set = set()
    for succ in cfg.get(label, []):
        out_set.update(live_in[succ])
    return out_set

def analyze_memory_uses(block, live_out_set, alias_maps):
    live_set = live_out_set.copy()
    for idx in reversed(range(len(block))):
        instr = block[idx]
        alias_map = alias_maps[idx]
        if 'op' in instr:
            op = instr['op']
            args = instr.get('args', [])
            if op == 'ret':
                if args:
                    ret_var = args[0]
                    pts = alias_map.get(ret_var, set())
                    live_set.update(pts)
            elif op == 'store':
                p = args[0]
                pts = alias_map.get(p, set())
                live_set.update(pts)
            elif op == 'load':
                p = args[0]
                pts = alias_map.get(p, set())
                live_set.update(pts)
            elif op == 'free':
                p = args[0]
                pts = alias_map.get(p, set())
                live_set -= pts
            elif op == 'call':
                for arg in args:
                    pts = alias_map.get(arg, set())
                    live_set.update(pts)
    return live_set

def remove_dead_stores(func, alias_info, live_out):
    """Removes dead store instructions from a function based on alias and liveness analysis."""
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = construct_cfg(blocks)
    block_map = dict(zip(labels, blocks))

    for label in labels:
        block = block_map[label]
        alias_maps = alias_info[label]
        live_vars = live_out[label].copy()
        new_block = []

        for idx in reversed(range(len(block))):
            instr = block[idx]
            if is_dead_store(instr, alias_maps[idx], live_vars):
                continue  # Skip dead store
            
            update_live_vars(instr, alias_maps[idx], live_vars)
            new_block.append(instr)

        block[:] = reversed(new_block)  # Update the block in-place with optimized instructions

    func['instrs'] = flatten([block_map[label] for label in labels])

def is_dead_store(instr, alias_map, live_vars):
    """Checks if a store instruction is dead (i.e., does not affect any live variable)."""
    if instr.get('op') == 'store':
        target = instr['args'][0]
        points_to = alias_map.get(target, set())
        return points_to.isdisjoint(live_vars) and 'unknown' not in points_to and 'unknown' not in live_vars
    return False

def update_live_vars(instr, alias_map, live_vars):
    """Updates the set of live variables based on the instruction type."""
    op = instr.get('op')
    args = instr.get('args', [])

    if op == 'load' and args:
        live_vars.update(alias_map.get(args[0], set()))
    elif op == 'free' and args:
        live_vars -= alias_map.get(args[0], set())
    elif op == 'ret' and args:
        live_vars.update(alias_map.get(args[0], set()))
    elif op == 'call':
        for arg in args:
            live_vars.update(alias_map.get(arg, set()))

def collect_alloc_sites(func):
    alloc_sites = {}
    counter = 0
    for instr in func['instrs']:
        if 'op' in instr and instr['op'] == 'alloc':
            alloc_sites[id(instr)] = f'alloc_{counter}'
            counter += 1
    return alloc_sites

def get_func_args(func):
    args = []
    for arg in func.get('args', []):
        args.append(arg['name'])
    return args

def optimize_function(func):
    """Optimizes the function by performing alias analysis and dead store elimination."""
    blocks = list(form_blocks(func['instrs']))
    cfg, labels = construct_cfg(blocks)
    alloc_sites = collect_alloc_sites(func)
    func_args = get_func_args(func)

    # Perform alias analysis
    in_alias, out_alias = alias_analysis(blocks, cfg, labels, func_args, alloc_sites)
    alias_info = build_alias_info(in_alias, labels, blocks, alloc_sites)

    # Perform memory liveness analysis
    live_in, live_out = memory_liveness_analysis(blocks, cfg, labels, alias_info)

    # Remove dead stores
    remove_dead_stores(func, alias_info, live_out)

def build_alias_info(in_alias, labels, blocks, alloc_sites):
    """Builds alias information for each instruction in each block."""
    alias_info = {}
    block_map = dict(zip(labels, blocks))

    for label in labels:
        block = block_map[label]
        state = {var: locs.copy() for var, locs in in_alias.get(label, {}).items()}
        alias_maps = []

        for instr in block:
            alias_maps.append(state.copy())
            update_state_based_on_instr(state, instr, alloc_sites)

        alias_info[label] = alias_maps  # Store the list of alias maps per block

    return alias_info

def update_state_based_on_instr(state, instr, alloc_sites):
    """Updates alias state based on the operation in the instruction."""
    if 'op' not in instr:
        return

    op = instr['op']
    dest = instr.get('dest')
    args = instr.get('args', [])

    if op == 'alloc' and dest:
        alloc_site = alloc_sites[id(instr)]
        state[dest] = {alloc_site}
    elif op == 'id' and dest and args:
        src = args[0]
        state[dest] = state.get(src, set()).copy()
    elif op == 'ptradd' and dest and args:
        src = args[0]
        state[dest] = state.get(src, set()).copy()
    elif op in {'load', 'call'} and dest:
        state[dest] = {'unknown'}

def main():
    program = json.load(sys.stdin)
    for func in program['functions']:
        optimize_function(func)
    json.dump(program, sys.stdout, indent=2)

if __name__ == '__main__':
    main()