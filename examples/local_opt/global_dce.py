import json
import sys

def global_dce(func):
    """
    Trival global dead code elimination.
    Continue until convergence.
    """
    converge = False
    used = set()
    while not converge:
        converge = True
        for instr in func["instrs"]:
            if "args" in instr:
                used.update(instr["args"])
        
        for instr in func["instrs"]:
            if ("dest" in instr) and (instr["dest"] not in used):
                func["instrs"].remove(instr)
                converge = False

if __name__ == "__main__":
    prog = json.load(sys.stdin)
    for func in prog['functions']:
        global_dce(func)
    json.dump(prog, sys.stdout, indent=2)