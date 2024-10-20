import copy
import json
import sys
from cfg import *
from typing import Dict, Set, List, Callable, Tuple, Any

def data_flow_analysis(graph: Dict, label2block: Dict, forward: bool, init: Any, merge_fn: Callable, transfer_fn: Callable) -> Tuple[Dict, Dict]:
    worklist = set(graph.keys())
    ins = {}
    outs = {label: copy.deepcopy(init) for label in graph}

    while worklist:
        b = worklist.pop()
        predecessors_or_successors = graph[b].predecessors if forward else graph[b].successors
        ins[b] = merge_fn([outs[x] for x in predecessors_or_successors])
        new_outs = transfer_fn(label2block[b], ins[b])

        if outs[b] != new_outs:
            outs[b] = new_outs
            worklist.update(graph[b].successors if forward else graph[b].predecessors)

    return (ins, outs) if forward else (outs, ins)

def union_sets(l: List[Set]) -> Set:
    return set().union(*l)

def merge_dicts(l: List[Dict]) -> Dict:
    return {k: set().union(*(m.get(k, set()) for m in l)) for k in set().union(*(m.keys() for m in l))}

def merge_consts(l: List[Dict]) -> Dict:
    result = {}
    for m in l:
        for k, const in m.items():
            if k not in result:
                result[k] = const
            elif result[k] != const:
                result[k] = None
    return result

def get_var_defs(instrs: List[Dict]) -> Dict:
    return {instr["dest"]: instr for instr in instrs if "dest" in instr}

def format_instruction(defn: Dict) -> str:
    op = defn["op"]
    type_ = defn["type"]
    val = f" {defn['value']}" if "value" in defn else ""
    args = "".join(f" {a}" for a in defn.get("args", []))
    funcs = "".join(f" @{f}" for f in defn.get("funcs", []))
    labels = "".join(f" .{l}" for l in defn.get("labels", []))
    return f"{op}{funcs}{args}{labels}{val}"

def reaching_defs(instrs: List[Dict], inv: Dict) -> Dict:
    outv = copy.deepcopy(inv)
    for var, defn in get_var_defs(instrs).items():
        outv[var] = {f"{var}: {defn['type']} = {format_instruction(defn)};"}
    return outv

def const_prop(instrs: List[Dict], inv: Dict) -> Dict:
    outv = copy.deepcopy(inv)
    for instr in instrs:
        if "dest" in instr:
            outv[instr["dest"]] = instr["value"] if instr["op"] == "const" else None
    return outv

def live_vars(instrs: List[Dict], inv: Set) -> Set:
    outv = copy.deepcopy(inv)
    for instr in reversed(instrs):
        if "dest" in instr:
            outv.discard(instr["dest"])
        outv.update(instr.get("args", []))
    return outv

REACHING_DEFS = (True, dict(), merge_dicts, reaching_defs)
CONST_PROP = (True, dict(), merge_consts, const_prop)
LIVE_VARS = (False, set(), union_sets, live_vars)

def pretty_print_defs(dicts: Dict) -> str:
    ds = [defn for defs in dicts.values() for defn in defs]
    return "∅" if not ds else "".join(sorted("\n      " + d for d in ds))

def pretty_print_set(sets: Set) -> str:
    return "∅" if not sets else ", ".join(sorted(str(x) for x in sets))

def pretty_print_consts(dicts: Dict) -> str:
    return "∅" if not dicts else ", ".join(sorted(f"{v} = {'?' if c is None else c}" for v, c in dicts.items()))

def main():
    prog = json.load(sys.stdin)
    analysis = sys.argv[1] if len(sys.argv) > 1 else "live"

    analysis_config = {
        "defs": (REACHING_DEFS, pretty_print_defs),
        "const": (CONST_PROP, pretty_print_consts),
        "live": (LIVE_VARS, pretty_print_set)
    }.get(analysis, (LIVE_VARS, pretty_print_set))

    for func in prog['functions']:
        name = func["name"]
        blocks = form_blocks(func['instrs'])
        label2block = label_blocks(blocks)
        graph, label2block = get_cfg(label2block)

        before, after = data_flow_analysis(graph, label2block, *analysis_config[0])

        print(f"{name}:")
        for block in graph.keys():
            print(f"  {block}:")
            print(f"    in: {analysis_config[1](before[block])}")
            print(f"    out: {analysis_config[1](after[block])}")

if __name__ == '__main__':
    main()
