import json
import sys
import itertools

def flatten(ll):
    """Flatten an iterable of iterable to a single list. Blocks (List of a list) -> Instrs (List)
    """
    return list(itertools.chain(*ll))

def fresh(seed, names):
    '''Generate a new name that is not in `names` starting with `seed`.
    '''
    i = 0
    while True:
        name = seed + str(i)
        if name not in names:
            return name
        i += 1

# Instructions that terminate a basic block.
TERMINATORS = 'br', 'jmp', 'ret'

def form_blocks(instrs):
    """Given a list of Bril instructions, generate a sequence of
    instruction lists representing the basic blocks in the program.
    Every instruction in `instr` will show up in exactly one block. Jump
    and branch instructions may only appear at the end of a block, and
    control can transfer only to the top of a basic block---so labels
    can only appear at the *start* of a basic block. Basic blocks may
    not be empty.
    """

    cur_block = []

    for instr in instrs:
        if 'op' in instr: # This is an instruction
            cur_block.append(instr) # Add into current basic block

            if instr['op'] in TERMINATORS: # This is a terminator instruction
                yield cur_block
                cur_block = []
        
        else: # This is a label
            # End the block (if it contains anything). 
            if cur_block: # if this condition doesn't exist, there would be empty cur_block yielded when the label is right behind a TERMINATOR. 
                yield cur_block
            
            # Start a new block with the label
            cur_block = [instr]

    # Produce the final block, if any
    if cur_block: # If this condition doesn't exist, if we have a `ret` in the last instr, this would yield a empty block. 
        yield cur_block

def print_df(In: dict, Out: dict):
    '''
    Print the result of Dataflow Analysis based on certain format. 
    in_var, out_var could be *set* or *dict*
    '''

    for block_label in In.keys():
        in_var = In[block_label]
        out_var = Out[block_label]

        if isinstance(in_var, set):
            in_var = ', '.join(sorted(in_var)) if (len(in_var) != 0) else '∅'
            out_var = ', '.join(sorted(out_var)) if (len(out_var) != 0) else '∅'
        elif isinstance(in_var, dict):
            if (len(in_var) != 0):
                in_var = ', '.join('{}: {}'.format(k, v)
                                            for k,v in sorted(in_var.items()))
            else:
                in_var = '∅'
            
            if (len(out_var) != 0):
                out_var = ', '.join('{}: {}'.format(k, v)
                                        for k,v in sorted(out_var.items()))
            else:
                out_var = '∅'

        print(f"{block_label}:")
        print(f"  in:  {in_var}")
        print(f"  out: {out_var}")
