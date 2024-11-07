# CS265 Task 4 Memory
### Tiffany Tang (3037261885)

### Dead Store Elimination with Alias Analysis for Bril Programs
I chose Dead Store Elimination (DSE) as the primary optimization technique. Additionally, I explored more advanced techniques, such as enhanced alias analysis and in-block memory access pattern analysis, to improve the precision of DSE.

### Implementation Details
#### Basic Alias Analysis
I implemented a straightforward alias analysis that tracks the potential alias relationships between variables and memory locations within a Bril program. This analysis is flow-insensitive, meaning it does not track the exact order of instructions but instead focuses on the relationships at a block level. The alias analysis allows the DSE to determine when a store operation can be safely eliminated without affecting subsequent program behavior.

#### Dead Store Elimination (DSE) [(dse.py)](./dse.py)
The DSE pass uses alias information to identify and remove redundant store instructions. The basic DSE algorithm works as follows:
1. **Identify Potential Dead Stores**: For each store instruction, check if its stored value is later accessed. If not, it is considered dead.
2. **Alias-Based Validation**: Using the alias information, verify that the store location does not alias with any live variables. If the store location is disjoint from the live set, the store is removed.
3. **In-Block Memory Access Pattern Analysis**: To further enhance DSE, I implemented an in-block analysis to detect consecutive store instructions to the same location with no intervening loads. Only the last store in a sequence is retained, as intermediate stores are redundant.

#### Enhanced Implementation Attempts [(enhanced_dse.py)](./enhanced_dse.py)
To improve the effectiveness of DSE, I attempted a more advanced version of alias analysis using `In-Block Memory Access Pattern Analysis`: 

In remove_dead_stores, I added a variable `last_store_target` to track consecutive stores to the same location. When a store operation is detected to the same location as `last_store_target` (with no intervening loads or operations that could invalidate it), it is skipped as redundant. This effectively keeps only the final store in a sequence of consecutive stores to the same location.

### Benchmark Results and Analysis
#### Performance
After implementing the basic DSE with alias analysis, I observed that while the optimization worked correctly on all tests, but it did not reduce insturction counts [(dse_result.csv)](./dse_result.csv). This is likely due to its conservative nature, which limits the scope of removable stores.

#### Issues with Enhanced Version
I also experimented with an enhanced version of DSE. While this enhanced version was able to identify and eliminate more redundant stores, it encountered issues on some test cases, leading to incorrect results on some tests [(enhanced_dse_result.csv)](./enhanced_dse_result.csv). These issues may stem from misclassifying stores as dead, causing the elimination of necessary stores.

### Example Bril Program

#### Original (Dynamic Instruction Count: 15)
```
@main {
  one: int = const 1;
  x: ptr<int> = alloc one;

  fifty: int = const 50;
  store x fifty;

  sixty: int = const 60;
  store x sixty;

  seventy: int = const 70;
  store x seventy;

  final_value: int = load x;
  print final_value;

  # Stores that happen after the final load, potential dead stores
  post_load_val_one: int = const 10;
  store x post_load_val_one;

  post_load_val_two: int = const 20;
  store x post_load_val_two;

  free x;
}
```

#### After optimized with basic DSE (Dynamic Instruction Count: 13)
```
@main {
  one: int = const 1;
  x: ptr<int> = alloc one;

  fifty: int = const 50;
  store x fifty;

  sixty: int = const 60;
  store x sixty;

  seventy: int = const 70;
  store x seventy;

  final_value: int = load x;
  print final_value;

  # Stores that happen after the final load, potential dead stores
  post_load_val_one: int = const 10;

  post_load_val_two: int = const 20;

  free x;
}
```

After applying basic DSE:
- The two stores after the final load (storing `10` and `20`) were removed as they are clearly dead.
- However, basic DSE did not detect the redundant stores of `50` and `60` before the final `store` of `70`, as it lacks the ability to analyze in-block memory access patterns.


Basic DSE is conservative and removes only post-load stores, resulting in limited performance gains by reducing the instruction count from 15 to 13.

#### After optimized with enhanced DSE (Dynamic Instruction Count: 11)

```
@main {
  one: int = const 1;
  x: ptr<int> = alloc one;

  fifty: int = const 50;

  sixty: int = const 60;

  seventy: int = const 70;
  store x seventy;

  final_value: int = load x;
  print final_value;

  # Stores that happen after the final load, potential dead stores
  post_load_val_one: int = const 10;

  post_load_val_two: int = const 20;

  free x;
}
```

After applying enhanced DSE:
- The stores of `50` and `60` were also removed since they were overwritten by the `store` of `70` before any `load`.
- This results in a more optimal code version, reducing the dynamic instruction count further from 13 to 11.

### Summary of Results

| Version             | Dynamic Instruction Count | Stores Removed         |
|---------------------|---------------------------|-------------------------|
| **Original**        | 15                        | None                   |
| **Basic DSE**       | 13                        | Post-load stores       |
| **Enhanced DSE**    | 11                        | Redundant in-block stores and post-load stores |

### Conclusion
- **Basic DSE** provides modest optimization by eliminating only post-load stores.
- **Enhanced DSE** further improves performance by identifying redundant in-block stores, resulting in a more efficient code version. However, this version was prone to inaccuracies in some cases during benchmarking due to the complexity of alias tracking that requires furture insights.