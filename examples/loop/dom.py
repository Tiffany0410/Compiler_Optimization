from cfg import *
import copy
import json

def find_dominators(graph, initial_node):
    dom = {vertex : list(graph.keys()) for vertex in graph}
    prev_dom = {}
    while dom != prev_dom:
        prev_dom = copy.deepcopy(dom)
        for vertex in graph:
            if vertex == initial_node: # only node dominating the first block of the function is itself
                dom[vertex] = [vertex]
            else:
                l = [set(dom[predecessor]) for predecessor in graph[vertex].predecessors]
                if l != []:
                    intersection = set.intersection(*l)
                else:
                    intersection = set()
                dom[vertex] = list(intersection.union({vertex}))
    return dom

def find_strict_dominators(dominators_dict):
    strict_dominators = copy.deepcopy(dominators_dict)
    for vertex in dominators_dict:
        strict_dominators[vertex].remove(vertex)

    return strict_dominators

def find_immediate_dominators(strict_dominators_dict):
    immediate_dominators = {vertex : [] for vertex in strict_dominators_dict}
    for vertex in strict_dominators_dict:
        for dominated_vertex in strict_dominators_dict[vertex]:
            can_add = True
            for other_vertex in strict_dominators_dict:
                if dominated_vertex in strict_dominators_dict[other_vertex] and other_vertex in strict_dominators_dict[vertex]:
                    can_add = False
                    break
            if can_add:
                immediate_dominators[vertex].append(dominated_vertex)
    return immediate_dominators

def compute_dominance_frontier(graph, strict_dominators_dict):
    dominance_frontier = {vertex : [] for vertex in strict_dominators_dict}
    for vertex in strict_dominators_dict:
        for other_vertex in graph:
            if not other_vertex in strict_dominators_dict[vertex]: # can't be in the frontier if A strictly dominates B
                for preds in graph[other_vertex].predecessors:
                    if preds in strict_dominators_dict[vertex]:
                        dominance_frontier[vertex].append(other_vertex)
                        break

    return dominance_frontier

def get_dominator_tree(immediate_dominators_dict):
    dominator_tree = {vertex: GraphNode() for vertex in immediate_dominators_dict}
    for vertex in immediate_dominators_dict:
        for st_dominated_vertex in immediate_dominators_dict[vertex]:
            dominator_tree[vertex].predecessors.add(st_dominated_vertex)
            dominator_tree[st_dominated_vertex].successors.add(vertex)

    return dominator_tree

def main():
    prog = json.load(sys.stdin)
    for func in prog['functions']:
        # Get the basic block and CFG for this function
        blocks = form_blocks(func['instrs'])
        label2block = label_blocks(blocks)
        graph, new_label2block = get_cfg(label2block)

        print("############################################################GRAPH")
        print(graph)
        print("############################################################DOMINATORS")
        dominators = find_dominators(graph, label2block[0][0])
        for d in dominators:
            dominators[d].sort()
        print(json.dumps(dominators, indent = 4, sort_keys = True))
        print("############################################################STRICT DOMINATORS")
        strict_dominators = find_strict_dominators(dominators)
        for d in strict_dominators:
            strict_dominators[d].sort()
        print(json.dumps(strict_dominators, indent = 4, sort_keys = True))
        print("############################################################IMMEDIATE DOMINATORS")
        immediate_dominators = find_immediate_dominators( strict_dominators)
        for d in immediate_dominators:
            immediate_dominators[d].sort()
        print(json.dumps(immediate_dominators, indent = 4, sort_keys = True))
        print("############################################################DOMINATOR TREE")
        dominator_tree = get_dominator_tree(immediate_dominators)
        print(dominator_tree)

if __name__ == '__main__':
    main()