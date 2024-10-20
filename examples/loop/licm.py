import sys
import json
import copy
from dataflow import *
from dom import *
from cfg import *

preheader_acc = 0

def find_natural_loop_from_backedge(graph, h, t):
    loop = {h, t}
    for node in graph:
        if node in (h, t):
            continue
        if can_reach(graph, node, t, h):
            loop.add(node)
    return {"entry": h, "loop": loop}

def can_reach(graph, start, target, avoid):
    queue = [start]
    seen = set()
    while queue:
        v = queue.pop(0)
        if v == target:
            return True
        for succ in graph[v].successors:
            if succ != avoid and succ not in seen:
                seen.add(succ)
                queue.append(succ)
    return False

def get_reaching_defs_immediately_before_loop(graph, label2block, reaching_defs, loop):
    loop_entry = loop["entry"]
    loop_reaching_defs = {}
    
    for pred in graph[loop_entry].predecessors:
        if pred in loop["loop"]:
            continue
        
        update_loop_reaching_defs(loop_reaching_defs, reaching_defs[pred])
        update_loop_reaching_defs(loop_reaching_defs, get_var_defs(label2block[pred]))
    
    return loop_reaching_defs

def update_loop_reaching_defs(loop_reaching_defs, defs):
    for var, def_set in defs.items():
        if isinstance(def_set, set):
            loop_reaching_defs.setdefault(var, set()).update(def_set)
        else:
            loop_reaching_defs.setdefault(var, set()).add(format_def(var, def_set))

def format_def(var, defn):
    op = defn["op"]
    type_ = defn["type"]
    val = f" {defn['value']}" if "value" in defn else ""
    args = "".join(f" {a}" for a in defn.get("args", []))
    funcs = "".join(f" @{f}" for f in defn.get("funcs", []))
    labels = "".join(f" .{l}" for l in defn.get("labels", []))
    return f"{var}: {type_} = {op}{funcs}{args}{labels}{val};"

def is_all_reachdefs_outside(var, before_loop_defs, block_reaching_defs):
    return var in before_loop_defs and block_reaching_defs[var] == before_loop_defs[var]

def find_loop_invariant_instrs(graph, label2block, reaching_defs, loop):
    before_loop_defs = get_reaching_defs_immediately_before_loop(graph, label2block, reaching_defs, loop)
    loop_invariants = {}

    while True:
        prev_loop_invariants = copy.deepcopy(loop_invariants)
        for lblock in loop["loop"]:
            for instr in label2block[lblock]:
                if "args" in instr and "dest" in instr:
                    if all(arg in loop_invariants or is_all_reachdefs_outside(arg, before_loop_defs, reaching_defs[lblock]) for arg in instr["args"]):
                        loop_invariants[instr["dest"]] = {"instr": instr, "block": lblock}
        if prev_loop_invariants == loop_invariants:
            break

    return loop_invariants

def get_loop_exits(graph, loop):
    return {lblock for lblock in loop["loop"] if any(succ not in loop["loop"] for succ in graph[lblock].successors)}

def is_var_defined_elsewhere(label2block, var, vardef, loop):
    return any(var == defvar and vardef != defn 
               for lblock in loop["loop"] 
               for defvar, defn in get_var_defs(label2block[lblock]).items())

def get_loop_blocks_that_use_var(label2block, var, loop):
    return {lblock for lblock in loop["loop"] 
            for instr in label2block[lblock] 
            if "args" in instr and var in instr["args"]}

def sat_relaxed_cond_3(graph, label2block, exits, li_var, loop_invariants, loop):
    if loop_invariants[li_var]["instr"].get("op") in ["div", "print"]:
        return False

    for lexit in exits:
        for succ in graph[lexit].successors:
            if succ in loop["loop"]:
                continue
            if is_var_used_in_future(graph, label2block, li_var, succ):
                return False
    return True

def is_var_used_in_future(graph, label2block, var, start_block):
    visited = set()
    stack = [start_block]
    while stack:
        curr_block = stack.pop()
        if curr_block in visited:
            continue
        visited.add(curr_block)
        if any(var in instr.get("args", []) for instr in label2block[curr_block]):
            return True
        stack.extend(succ for succ in graph[curr_block].successors if succ not in visited)
    return False

def can_move(graph, label2block, dominators, loop_invariants, li_var, loop, exits):
    li_block = loop_invariants[li_var]["block"]
    return (not is_var_defined_elsewhere(label2block, li_var, loop_invariants[li_var]["instr"], loop) and
            all(li_block in dominators[use_block] for use_block in get_loop_blocks_that_use_var(label2block, li_var, loop)) and
            all(li_block in dominators[lexit] or sat_relaxed_cond_3(graph, label2block, exits, li_var, loop_invariants, loop) for lexit in exits))

def make_preloop_header(graph, label2block, dominators, loop_invariants, loop, instrs):
    global preheader_acc
    preheader_label = f"preheader{preheader_acc}"
    loop_entry = loop["entry"]
    preloop_header = [{"label": preheader_label}]
    exits = get_loop_exits(graph, loop)
    
    movable_instrs = [loop_invariants[li_var]["instr"] for li_var in loop_invariants 
                      if can_move(graph, label2block, dominators, loop_invariants, li_var, loop, exits)]
    preloop_header.extend(movable_instrs)
    
    new_instrs = [instr for instr in instrs if instr not in movable_instrs]
    insert_index = next(i for i, instr in enumerate(new_instrs) if instr == {"label": loop_entry})
    new_instrs[insert_index:insert_index] = preloop_header
    
    new_label2block = update_label2block(label2block, preheader_label, preloop_header)
    new_graph = update_graph(graph, preheader_label, loop_entry)
    
    preheader_acc += 1
    return new_instrs, new_graph, new_label2block

def update_label2block(label2block, preheader_label, preloop_header):
    new_label2block = copy.deepcopy(label2block)
    new_label2block[preheader_label] = preloop_header
    return new_label2block

def update_graph(graph, preheader_label, loop_entry):
    new_graph = copy.deepcopy(graph)
    for vertex in new_graph:
        if loop_entry in new_graph[vertex].successors:
            new_graph[vertex].successors.remove(loop_entry)
            new_graph[vertex].successors.add(preheader_label)
    new_graph[preheader_label] = GraphNode([loop_entry])
    new_graph[preheader_label].predecessors = new_graph[loop_entry].predecessors.copy()
    return new_graph

def find_loops(graph, initial_node, dominator_map):
    return [find_natural_loop_from_backedge(graph, succ, vertex)
            for vertex in graph
            for succ in graph[vertex].successors
            if succ in dominator_map[vertex]]

def process_function(func):
    blocks = form_blocks(func['instrs'])
    label2block = label_blocks(blocks)
    graph, new_label2block = get_cfg(label2block)
    initial_node = label2block[0][0]
    dominators = find_dominators(graph, initial_node)
    analysis = REACHING_DEFS
    reaching_defs, _ = data_flow_analysis(graph, new_label2block, *analysis)
    loops = find_loops(graph, initial_node, dominators)
    
    new_instrs = func['instrs'].copy()
    for loop in loops:
        loop_invariants = find_loop_invariant_instrs(graph, new_label2block, reaching_defs, loop)
        new_instrs, graph, new_label2block = make_preloop_header(graph, new_label2block, dominators, loop_invariants, loop, new_instrs)
    
    return new_instrs

def main():
    prog = json.load(sys.stdin)
    for func in prog['functions']:
        func['instrs'] = process_function(func)
    print(json.dumps(prog, indent=4))

if __name__ == '__main__':
    main()
