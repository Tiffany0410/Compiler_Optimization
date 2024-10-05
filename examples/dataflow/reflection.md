# CS265 Task 2 Dataflow
### Tiffany Tang (3037261885)
This reflection outlines the implementation of dataflow analysis using worklist algorithms. It provides a general framework for forward dataflow problem (global constant propagation analysis) and backward dataflow problem (global liveness analysis). 

## How to Run

```bash
cd examples/dataflow
bril2json < {filename.bril} | python3 dataflow.py cprop # for global constant propagation
bril2json < {filename.bril} | python3 dataflow.py live # for global liveness analysis
```

## Global Constant Propagation Analysis
The global constant propagation analysis demonstrates a forward dataflow problem and uses a worklist algorithm to propagate constant values across basic blocks. The idea is to identify expressions that have constant values at runtime and replace variables with constants where applicable. 

### Design Decisions:
1. Worklist Algorithm: I chose to implement a worklist-based approach to handle both forward and backward dataflow. For constant propagation, I used a forward propagation direction, as we are interested in determining how constants flow from one block to another in the program.
2. Merging Constants: The `cprop_merge ` function ensures that if a variable is assigned different constant values in different paths, the value becomes unknown (?).
3. Transfer Function: If a variable is assigned a constant (op == 'const'), the transfer function propagates that constant; otherwise, it assigns the unknown value.


## Global Liveness Analysis
The global liveness analysis, a backward dataflow problem, determines which variables are "live" at different points in the program. A variable is considered live if its value is read before being redefined. Using this analysis, I implemented a global dead code elimination (DCE) pass to remove instructions that define variables that are never used.

### Design Decisions:
1. Backward Propagation: Liveness analysis uses a backward worklist algorithm.
2. Union-Based Merge: The merge function for liveness uses set union to combine the liveness information from different paths in the control flow graph (CFG).
3. Dead Code Elimination: By integrating liveness analysis with the global dead code elimination pass, I ensured that only variables that are not live at the end of a block are removed. This eliminates trivial dead code and optimizes the program by removing unnecessary computations.

