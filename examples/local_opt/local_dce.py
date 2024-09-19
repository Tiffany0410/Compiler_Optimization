import json
import sys
from form_blocks import form_blocks
from util import flatten

def local_dce(func):
    """
    Local dead code elimination.
    """
    blocks = list(form_blocks(func['instrs']))
    for block in blocks:
        last_def = {}
        for i, instr in enumerate(block):
            for arg in instr.get('args', []):
                last_def.pop(arg, None)
            
            if 'dest' in instr:
                dest = instr['dest']
                if dest in last_def:
                    block.pop(last_def[dest])
                last_def[dest] = i

    func['instrs'] = flatten(blocks)

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for func in prog['functions']:
        local_dce(func)
    json.dump(prog, sys.stdout, indent=2)