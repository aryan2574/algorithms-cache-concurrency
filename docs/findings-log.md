# Findings log

One short entry per experiment, as an outline for the thesis document. Details, data and limitations are in each experiment's own README.

## 01 Matrix multiplication: memory-access order

- **Question:** how much does column-wise access (cache-unfriendly) cost compared with row-wise access in matrix multiplication, and can cache measurements explain it?
- **Versions:** `naive` (textbook loops, walks down a column of B), `row_wise` (reordered loops, walks along rows), `tiled` (row_wise in small tiles).
- **Main result:** reordering the loops from `naive` to `row_wise` makes multiplication about 10x to 25x faster for n >= 256 (24.5x at n=512). About 14x of that is memory-access order; the rest at n=512 is SIMD vectorisation of `row_wise`.
- **Evidence:** `naive` misses L1 on 60 to 65% of loads against about 8% for `row_wise`, and has over 100x more last-level cache misses (measured with `perf`).
- **Tiling:** no gain up to n=512, 2x faster than `row_wise` at n=1024 (B no longer fits in L3). The counters do not explain the mechanism, which remains a hypothesis.
- **Open questions:** tile-size sweep, n=2048, cache-oblivious and Z-order versions, a cache simulator to confirm the tiling effect.
- **Report:** [experiments/01-matrix-multiplication/README.md](../experiments/01-matrix-multiplication/README.md)
- **Data:** `experiments/01-matrix-multiplication/results/2026-10-18-ryzen5500u-wsl2/`
