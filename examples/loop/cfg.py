import json
import sys

# A list of terminating instructions
TERMINATORS = 'jmp', 'ret', 'br'

def form_blocks(body):
    """
    Form basic blocks from a given
    Bril function.

    returns: a list of basic blocks.
    """

    cur_block = []
    for instr in body:
        # If this is an instruction
        if 'op' in instr:
            cur_block.append(instr)
            if instr['op'] in TERMINATORS:
                if cur_block:
                    yield cur_block
                cur_block = []

        # If this is a label
        elif 'label' in instr:
            if cur_block:
                yield cur_block
            cur_block = [instr]

    # Return the final block
    if cur_block:
        yield cur_block


def label_blocks(blocks):
    """
    Label the basic blocks.

    returns: an association list of labels and block.
    """

    label2block = []

    # Iterate over all blocks
    for block in blocks:
        id = len(label2block)

        # If this block is empty then we can just skip it
        if not block:
            continue

        # If the first instruction is a label then we
        # use that as a label for the block
        elif 'label' in block[0]:
            label_name = block[0]['label']

        # Otherwise generate a label for the block
        else:
            label_name = 'l{}'.format(id)

        # Set the name of the blocks
        label2block.append((label_name, block))

    return label2block


class GraphNode(object):
    """
    Represents a node in the CFG which
    has a successors object and a
    predecessors object.
    """

    def __init__(self, succ=[]):
        """
        Initialise the graph node
        with the given successors.
        """

        self.successors = set(succ)
        self.predecessors = set()

    def __repr__(self):
        """
        Return a string representation of this object.
        """

        return "GraphNode(successors={}, predecessors={})".format(self.successors, self.predecessors)


def get_cfg(label2block):
    """
    Create a CFG given an association
    list of labels and block.

    returns: a dict from labels to the
             graph node.
    """

    # The dict for a result is a map
    # from block labels to an object
    # of it's successors and predecessors
    graph = {}

    # Iterate over all blocks with their labels
    for idx, (name, block) in enumerate(label2block):
        # If the block is empty then we don't have any successors
        if not block:
            graph[name] = GraphNode()
            continue

        # Get the block's last instruction
        last = block[-1]

        # If we can get the next block information
        # from the last instruction then use it
        if "op" not in last:
            succ = []
        elif last['op'] in ('jmp', 'br'):
            succ = last['labels']
        elif last['op'] == 'ret':
            succ = []

         # Fall through to next block
         # but which is the next block?
        else:
            if idx < len(label2block) - 1:
                succ = [label2block[idx + 1][0]]
            else:
                succ = []

        # Create the graph node with it's successor
        graph[name] = GraphNode(succ)

    # Iterate over the graph and set precessors
    for label, node in graph.items():
        for val in node.successors:
            graph[val].predecessors.add(label)

    # Return the graph
    return graph, dict(label2block)


def main():
    # Load the program JSON
    prog = json.load(sys.stdin)

    # Do this for each function
    for func in prog['functions']:
        # Get the basic block and CFG for this function
        blocks = form_blocks(func['instrs'])
        label2block = label_blocks(blocks)
        graph, label2block = get_cfg(label2block)

        # Print the obtained graph and basic blocks
        print("============GRAPH:" + str(graph))
        print("============LABEL2BLOCK:" + str(label2block))


if __name__ == '__main__':
    main()
