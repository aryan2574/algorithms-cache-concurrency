# Agenda

Reading order for the thesis work: this page → [findings](findings.md) → the experiment report → [cache theory](theory/caches.md) when you need the hardware vocabulary.

## Thesis question

How much do memory layout and access order cost in classical algorithms, and can cache-aware and cache-oblivious designs fix it when the data no longer fits in the CPU caches?

## Experiments

| # | Experiment | Status | Report |
| --- | --- | --- | --- |
| 01 | Matrix multiplication: access order, three layouts, cache-aware vs cache-oblivious, tile size | **done** (2026-10-13 … 2026-11-15) | [README](../experiments/01-matrix-multiplication/README.md) |
| 02 | Merge sort and the cache | not started | [README](../experiments/02-merge-sort/README.md) |

## Timeline

| Date | Professor's task (exact wording) | Status |
| --- | --- | --- |
| 2026-10-13 | "For 2D matrix, the caching are row wise but when we move along the column, we are breaking the caching and check if this could be improved." | done — `naive` vs `row_wise` vs `tiled`, first timings and counters (2026-10-18) |
| 2026-11-01 | (1) Theoretical derivation of cache misses for (a) row-major × row-major (`naive`), (b) row-major × col-major (`row_wise`), (c) tiled. (2) Lower bound for the number of cache misses in matrix multiplication. (3) Three regimes: whole matrix < cache; single row < cache < whole matrix; cache < single row — how do the algorithms perform? (4) Understand the nature of the computer's cache hierarchy; which cache are we measuring? | done — formulas, lower bound, regimes, L2 (not LLC) counters, power-of-two conflict, L3 sweep |
| 2026-11-14 | (1) Cache oblivious for all three matrix types → row major, column major, tile wise. (2) Cache aware matrix multiplication, and compare the results. (3) Different tile sizes; what if the whole matrix / the tile does not fit; cases "whole matrix > cache > single row" and "single row > cache". | done for n ≤ 2048; "single row > cache" only partial (n = 4096 stopped for wall time) |
| 2026-11-15 | (figures for the report; finish counters) | figures done; multi-layout counter run started and stopped |

Day-by-day notes (lab notebook) live under each experiment's `notes/` folder.

## Open items

- Finish or drop the multi-layout cache-counter run (experiment 01).
- Merge sort (experiment 02): waiting for the professor's exact task wording.
- Optional later: n = 4096 for tile-wise / oblivious, Z-order layout, native Linux L3 counters, error bars.
