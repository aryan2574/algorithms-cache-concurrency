# Findings log

One place to read **what each experiment found** and **what its limits are**.  
For the agenda of an experiment (what was done, in what order), open that experiment’s README.  
Charts live under `docs/<experiment>/`.

---

## 01 — Matrix multiplication (cache, layouts, tiling)

**Report (agenda + detail):** [experiments/01-matrix-multiplication/README.md](../experiments/01-matrix-multiplication/README.md)  
**Figures (how to explain each chart):** [docs/01-matrix-multiplication/README.md](01-matrix-multiplication/README.md)  
**Day notes:** [01-nov.txt](../experiments/01-matrix-multiplication/01-nov.txt) (theory), [14-nov.txt](../experiments/01-matrix-multiplication/14-nov.txt) (main results), [15-nov.txt](../experiments/01-matrix-multiplication/15-nov.txt) (figures / counters)  
**Main data:** `results/2026-10-18-ryzen5500u-wsl2/` · `results/2026-11-14-ryzen5500u-wsl2-run2/`

### What this experiment set out to answer

1. How much does column-wise vs row-wise memory access cost in matrix multiplication, and do cache misses explain it?
2. How do **cache-aware** (tiled) and **cache-oblivious** (recursive) multiplication compare on three storage layouts: row-major, column-major, tile-wise?
3. How does **tile size** change performance? What if the tile no longer fits in cache? What if the whole matrix is larger than the cache but a single row still fits — and what if a single row no longer fits?

### Results

**Access order (October)**
- Reordering loops from `naive` (walks down a column of B) to `row_wise` (walks along rows) is about **10× to 25×** faster for n ≥ 256 (**24.5×** at n=512).
- About **14×** of that gap is memory-access order; the rest at n=512 is SIMD auto-vectorisation of `row_wise` (shown by a no-vectorisation build).
- Cache counters support this: `naive` misses L1 on **60–65%** of loads vs **~8%** for `row_wise`, and has **>100×** more last-level misses.

**Tile size (November)**
- For n ≥ 1024 the curve over tile size is **U-shaped**. Best tile is **T=128** (L2-sized), not the L1-sized tile that theory first predicted (T=16–64).
- Tiny tiles are bad: T=4 at n=2048 is up to **5.3× slower** than no tiling.
- Best tiling vs `row_wise`: about **1.9–2.2×** (row-major) and **~2.6×** (tile-wise). No clear gain at n ≤ 512.

**When the tile does not fit in cache**
- At n=2048, row-major time more than doubles from T=128 to T=512 and ends **18% worse** than plain `row_wise`.
- Tile-wise only rises about **13%** for the same step. At equal T, tile-wise is **13–32%** faster than row-major (up to **63%** at T=512).

**Layouts, cache-aware vs cache-oblivious**
- **Cache-oblivious** matches the best tuned cache-aware version on every layout (**within ~7%**, about the noise), with no tile size to tune.
- Fastest overall at n=2048: **cache-oblivious + tile-wise** — 1819 ms vs 4905 ms for `row_wise` (**2.7×**).
- Column-major **mirrors** row-major for plain loops (within **2%**).

**Cache regimes**
- **Whole matrix > cache > single row** (n=1024, 2048): plain loops collapse once the matrix leaves L3; tiling and recursion keep ~6–10 GFLOPS.
- **Single row ≈ / > L1** (n=4096): only partly measured (stopped for wall time). `row_wise` stayed at **3.7 GFLOPS** (same as n=2048); tiled T=128 was **1.8×** faster. The expected extra slowdown of `row_wise` was **not** seen.

### Drawbacks and limits

| Limit | Detail |
| --- | --- |
| Noise | Repeated measurements differ by **3–7%** (n ≥ 512). Differences under **~10%** are not reliable; n=256 is too short to trust. |
| Counters incomplete | Finished `perf` data only for `naive` / `row_wise` / `tiled` (October). Why tile-wise wins (conflicts, TLB, prefetch) stays a **hypothesis**. A full multi-layout counter run was started 2026-11-15 and **stopped** (partial folder only). |
| Large n / wall time | Work grows as **n³**. n=4096 (~20–40 s per multiply) was cut short on purpose (>1 h for a full sweep). Large tiles (T≤512) **were** measured at n≤2048 — the bottleneck is **n**, not T. |
| Memory | n=8192 does not fit in ~3 GB WSL2. |
| Scope | One machine (Ryzen 5 5500U), one thread, `double` only. No Z-order layout. No error bars (CSV has median only). Code not committed when the November timings were taken. |
| Unexplained | `tiled` can show **more** L1 misses than `row_wise` yet run faster at n=1024. Column-major tiled can be up to **~20%** slower than row-major tiled at n=2048. |

### Where the evidence is

| Kind | Path |
| --- | --- |
| October timings + counters + SIMD | `experiments/01-matrix-multiplication/results/2026-10-18-ryzen5500u-wsl2/` |
| November tile / layout / oblivious (main) | `.../results/2026-11-14-ryzen5500u-wsl2-run2/` |
| n=4096 partial | `.../results/2026-11-14-ryzen5500u-wsl2-run2-n4096/` |
| Charts + diagrams | `docs/01-matrix-multiplication/` |
