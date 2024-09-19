import json
import sys
from collections import namedtuple
from form_blocks import form_blocks
from util import flatten

Value = namedtuple('Value', ['op', 'args'])

class Numbering(dict):
    def __init__(self, init=None):
        super().__init__(init or {})
        self._next_id = 0

    def add(self, key):
        self[key] = self._next_id
        self._next_id += 1
        return self[key]

def last_writes(instrs):
    out = [False] * len(instrs)
    seen = set()
    for idx in range(len(instrs) - 1, -1, -1):
        instr = instrs[idx]
        if 'dest' in instr:
            dest = instr['dest']
            if dest not in seen:
                out[idx] = True
                seen.add(dest)
    return out

def get_variables_read_before_write(instrs):
    read_before_write = set()
    written_vars = set()
    for instr in instrs:
        args = instr.get('args', [])
        read_before_write.update(arg for arg in args if arg not in written_vars)
        if 'dest' in instr:
            written_vars.add(instr['dest'])
    return read_before_write

def canonicalize(value):
    # If the operation is commutative, sort the arguments
    if value.op in {'add', 'mul'}:
        return Value(value.op, tuple(sorted(value.args)))
    return value

def lvn_block(block):
    var2num = Numbering()
    value2num = {}
    num2vars = {}
    num2const = {}

    for var in get_variables_read_before_write(block):
        num = var2num.add(var)
        num2vars[num] = [var]

    for instr, last_write in zip(block, last_writes(block)):
        argvars = instr.get('args', [])
        argnums = tuple(var2num[var] for var in argvars)

        if 'args' in instr:
            instr['args'] = [num2vars[n][0] for n in argnums]

        if 'dest' in instr:
            for rhs in num2vars.values():
                if instr['dest'] in rhs:
                    rhs.remove(instr['dest'])

        val = None
        if 'dest' in instr and 'args' in instr and instr['op'] != 'call':
            val = canonicalize(Value(instr['op'], argnums))

            num = value2num.get(val)
            if num is not None:
                var2num[instr['dest']] = num

                if num in num2const:
                    instr.update({
                        'op': 'const',
                        'value': num2const[num],
                    })
                    del instr['args']
                else:
                    instr.update({
                        'op': 'id',
                        'args': [num2vars[num][0]],
                    })
                    num2vars[num].append(instr['dest'])
                continue

        if 'dest' in instr:
            newnum = var2num.add(instr['dest'])

            if instr['op'] == 'const':
                num2const[newnum] = instr['value']

            if last_write:
                var = instr['dest']
            else:
                var = 'lvn.{}'.format(newnum)

            num2vars[newnum] = [var]
            instr['dest'] = var

            if val is not None:
                value2num[val] = newnum

def lvn(prog):
    for func in prog['functions']:
        blocks = list(form_blocks(func['instrs']))
        for block in blocks:
            lvn_block(block)
        func['instrs'] = flatten(blocks)


if __name__ == '__main__':
    prog = json.load(sys.stdin)
    lvn(prog)
    json.dump(prog, sys.stdout, indent=2)