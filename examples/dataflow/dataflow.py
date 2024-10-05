import sys
import json
from typing import Tuple, Callable
from collections import namedtuple
from util import form_blocks, fresh, print_df

# A single dataflow analysis consists of these part:
# - forward: True for forward, False for backward.
# - init: An initial value (bottom or top of the latice).
# - merge: Take a list of values and produce a single value.
# - transfer: The transfer function.
Analysis = namedtuple('Analysis', ['forward', 'init', 'merge', 'transfer'])

def global_dce(func, liveness_out):
    """
    Trivial global dead code elimination using liveness information.
    """
    converge = False

    while not converge:
        converge = True
        
        # Iterate over the blocks and instructions
        for block_label, block in zip(func['block_labels'].values(), func['blocks']):
            new_block = []
            for instr in block:
                if "dest" in instr:
                    dest = instr["dest"]
                    # If the destination is not live in the liveness_out set for this block, it's dead code
                    if dest not in liveness_out[block_label]:
                        converge = False  # Mark as not converged to continue iteration
                        continue  # Skip adding this instruction (dead code)
                new_block.append(instr)
            # Update the block with potentially removed dead instructions
            block_index = list(func['block_labels'].values()).index(block_label)
            func['blocks'][block_index] = new_block

def union(sets):
    """
    Merge function for *live* analysis using set union.
    """
    return set().union(*sets)

def cprop_merge(dicts):
    """
    Merge function for cprop.
    For the same variable, if the values are the same -> keep it; if different -> value = '?'.
    """
    out = {}

    for d in dicts:
        for var, value in d.items():
            if var in out:
                out[var] = value if out[var] == value else '?'
            else:
                out[var] = value

    return out

def get_block_labels(blocks: list) -> dict:
    """
    Get the label names for each block.
    """
    block_labels = {}
    label_names = set()

    for i, block in enumerate(blocks):
        label = block[0].get('label', fresh(f'block.{i}', label_names))  # Generate fresh label if not present
        label_names.add(label)
        block_labels[i] = label

    return block_labels

def get_cfg(blocks: list, block_labels: dict) -> dict:
    """
    Generate the control flow graph (CFG) given blocks and their labels.
    """
    cfg = {}

    for i, block in enumerate(blocks):
        last_instr = block[-1]
        curr_label = block_labels[i]

        if last_instr['op'] == 'jmp':
            cfg[curr_label] = [last_instr['labels'][0]] # Direct jump to a single label
        elif last_instr['op'] == 'br':
            cfg[curr_label] = last_instr['labels']  # Conditional branch with two possible successor labels
        else:
            cfg[curr_label] = [block_labels[i + 1]] if i < len(blocks) - 1 else [] # Fall-through to the next block, if there is one

    return cfg

def get_predecessor(cfg: dict, curr_label: str) -> list:
    """
    Return the labels of all predecessor blocks.
    """
    return [label for label, succ in cfg.items() if curr_label in succ]

def live_func(block: list, Out: set) -> set:
    """
    Backward Transfer function for Live Variables analysis.    
    Transfer function: In = (Used(b)) Union (Out - Def(b)).
    """
    In = Out.copy()

    for instr in reversed(block):
        In.discard(instr.get('dest', None))  # Remove 'dest' (Def) if present
        In.update(instr.get('args', []))  # Add 'args' (Used) if present

    return In

def cprop_func(block: list, In: dict) -> dict:
    """
    Forward Transfer function for Constant Propagation.
    Transfer function is the same as local analysis.
    """
    Out = In.copy()

    for instr in block:
        dest = instr.get('dest')
        if dest:
            Out[dest] = instr['value'] if instr.get('op') == 'const' else '?'  # Assign constant or unknown

    return Out

def worklist_algorithm(worklist: set, cfg: dict, block_labels: dict, blocks: list, In: dict, Out: dict, 
                       transfer: Callable, merge: Callable, forward: bool = True) -> Tuple[dict, dict]:
    """
    General worklist algorithm that handles both forward and backward propagation.
    
    Args:
        worklist: set of block labels.
        cfg: control flow graph as a dictionary of label to list of labels.
        block_labels: dictionary mapping block indices to labels.
        blocks: list of blocks.
        In: dictionary of sets (variables) for each label.
        Out: dictionary of sets (variables) for each label.
        transfer: function that computes new In/Out values based on current block and In/Out.
        merge: function that merges the values of predecessor or successor blocks.
        forward: boolean indicating if the algorithm should run in forward (True) or backward (False) mode.
    
    Returns:
        Tuple of updated In and Out dictionaries.
    """
    while worklist:
        curr_label = worklist.pop()  # Pick a block from worklist

        # Determine predecessors or successors based on the direction
        if forward:
            In[curr_label] = merge(Out[pred_label] for pred_label in get_predecessor(cfg, curr_label))  # Merge function
        else:
            Out[curr_label] = merge(In[succ_label] for succ_label in cfg[curr_label])  # Merge function

        # Find the block corresponding to the current label
        block_index = list(block_labels.keys())[list(block_labels.values()).index(curr_label)]
        curr_block = blocks[block_index]

        if forward:
            Out_old = Out[curr_label]
            Out[curr_label] = transfer(curr_block, In[curr_label])  # Transfer function for forward
            if Out[curr_label] != Out_old:  # Out[b] changed
                worklist.update(cfg[curr_label])  # Add successors of the current block
        else:
            In_old = In[curr_label]
            In[curr_label] = transfer(curr_block, Out[curr_label])  # Transfer function for backward
            if In[curr_label] != In_old:  # In[b] changed
                worklist.update(get_predecessor(cfg, curr_label))  # Add predecessors of the current block
    
    return In, Out

def run_df(func, analysis):
    """
    Run dataflow analysis for the given function and analysis method.

    Data structures:
        blocks: list. Index -> Block.
        block_labels: dict. Key: Index; Value: Label name of the block.
        In: dict. Key: Label; Value: variables (set).
        Out: dict. Key: Label; Value: variables (set).
        worklist: Set. Elements are labels of *blocks*.
        cfg: dict. Key: label; Value: list of labels (control flow graph).
    """

    blocks = list(form_blocks(func['instrs']))
    block_labels = get_block_labels(blocks)
    cfg = get_cfg(blocks, block_labels)
    worklist = set(block_labels.values())
    In = {label: analysis.init for label in block_labels.values()}
    Out = {label: analysis.init for label in block_labels.values()}

    In, Out = worklist_algorithm(
        worklist, cfg, block_labels, blocks, In, Out, 
        analysis.transfer, analysis.merge, analysis.forward
    )

    # print_df(In, Out)

    if analysis == 'live' and DCE:
        global_dce(func, In, Out)

DCE = True

ANALYSES = {
    # Live variable analysis
    'live': Analysis(
        False,
        init=set(),
        merge=union,
        transfer=live_func),

    # Constant propagation pass
    'cprop': Analysis(
        True,
        init=dict(),
        merge=cprop_merge,
        transfer=cprop_func)
}

if __name__ == "__main__":
    if (len(sys.argv) > 1):
        analysis = ANALYSES[sys.argv[1]]

    prog = json.load(sys.stdin)
    for func in prog['functions']:
        run_df(func, analysis)
    json.dump(prog, sys.stdout, indent=2)