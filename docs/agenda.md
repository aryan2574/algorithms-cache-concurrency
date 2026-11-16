# Agenda

Reading order for the thesis work: this page → [findings](findings.md) → the experiment report → [cache theory](theory/caches.md) when you need the hardware vocabulary.

## Thesis question

How much do memory layout and access order cost in classical algorithms, and can cache-aware and cache-oblivious designs fix it when the data no longer fits in the CPU caches?

## Experiments

| # | Experiment | Status | Report |
| --- | --- | --- | --- |
| 01 | Matrix multiplication + transposition: access order, layouts, cache-aware vs cache-oblivious | **done** (multiply 2026-10-13 … 2026-11-15; transpose measured 2026-11-15) | [README](../experiments/01-matrix-multiplication/README.md) |
| 02 | Merge sort and the cache | **done** (measured twice 2026-11-15; tasks 5–10) | [README](../experiments/02-merge-sort/README.md) |

## Timeline

| Date | Professor's task (exact wording) | Status |
| --- | --- | --- |
| 2026-10-13 | "For 2D matrix, the caching are row wise but when we move along the column, we are breaking the caching and check if this could be improved." | done — `naive` vs `row_wise` vs `tiled`, first timings and counters (2026-10-18) |
| 2026-11-01 | (1) Theoretical derivation of cache misses for (a) row-major × row-major (`naive`), (b) row-major × col-major (`row_wise`), (c) tiled. (2) Lower bound for the number of cache misses in matrix multiplication. (3) Three regimes: whole matrix < cache; single row < cache < whole matrix; cache < single row — how do the algorithms perform? (4) Understand the nature of the computer's cache hierarchy; which cache are we measuring? | done — formulas, lower bound, regimes, L2 (not LLC) counters, power-of-two conflict, L3 sweep |
| 2026-11-14 | (1) Cache oblivious for all three matrix types → row major, column major, tile wise. (2) Cache aware matrix multiplication, and compare the results. (3) Different tile sizes; what if the whole matrix / the tile does not fit; cases "whole matrix > cache > single row" and "single row > cache". | done for n ≤ 2048; "single row > cache" only partial (n = 4096 stopped for wall time) |
| 2026-11-15 | (figures for the report; finish counters) | figures done; multi-layout counter run started and stopped |
| 2026-11-15 | Exact wording: "The paper about cache oblivious algorithms studies a simpler problem: matrix transposition. That is, from matrix A compute A^T. This is trivial to do with two nested for-loops but apparently a recursive algorithm has better cache behavior, and you'll be able to test it on much bigger matrices since transposition costs O(n^2) whereas matrix multiplication costs O(n^3), at least if we apply a version of the ‘high-school matrix multiplication algorithm’, which we do." | **done** — timings n=1024…8192 + perf counters n=1024…4096; recursive up to **6.0×** faster / **5–10×** fewer L2 misses; also `transposed_b` / `tiled_transposed_b` |
| 2026-11-15 | Merge sort tasks 5–10: (5) recursive mergesort with iterative merge; (6) unroll to iterative bottom-up (powers of 2); (7) which is faster — recursion overhead vs cache locality; (8) measure both vs `n`, how the discrepancy changes; (9) theoretical cache misses for recursive and iterative; (10) literature on cache behaviour of mergesort and sorting lower bounds. | **done** — two sessions; recursive wins past L3 (**~1.2×** at n=2²²; **~2.5–5×** fewer L2 misses); lit: Aggarwal–Vitter, Frigo et al., funnelsort / tall cache, LaMarca & Ladner |

Day-by-day notes (lab notebook) live under each experiment's `notes/` folder.

## Open items

- Finish or drop the multi-layout multiply cache-counter run (experiment 01).
- Optional (merge sort): larger n / native Linux L3 counters; funnelsort for the optimal bound.
- Optional later: n = 4096 for tile-wise / oblivious multiply, Z-order layout, native Linux L3 counters, error bars.
