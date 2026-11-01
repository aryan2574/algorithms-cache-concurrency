# Findings log

Details, tables and limitations: [experiments/01-matrix-multiplication/README.md](../experiments/01-matrix-multiplication/README.md). Hardware vocabulary: [experiments/01-matrix-multiplication/19-nov.txt](../experiments/01-matrix-multiplication/19-nov.txt).

---

## Current summary (as of 2026-11-01)

### 01 Matrix multiplication: memory-access order

- **Question:** how much does column-wise access cost compared with row-wise access in `C = A * B`, and can cache measurements explain it? Also the professor's three theory questions (miss formulas, lower bound, three regimes) and “which cache are we counting?”.
- **Versions:** `naive` (i, j, k — column of B), `row_wise` (i, k, j — rows), `tiled` (row_wise in `d × d` tiles, default d = 32).
- **Main result:** `row_wise` L1 misses equal `n³/8` (the line size) within 1–7%. `naive` is only ~3× slower at n = 250/400/500, but **9–24×** at n = 256/512/1024 because a power-of-two row is a multiple of 4096 bytes and a whole B column maps to 1–2 L1 sets. Tiling does nothing until B no longer fits in L3 (~n ≥ 600); then it is **2.0–2.4×** faster than `row_wise`. Best tile size at n = 1000 is d = 32.
- **Lower bound:** any classical `n³` algorithm needs at least `2 n³ / (L √Z)` misses (Hong & Kung 1981; tight constant Smith et al. 2017). On L1 that is `n³/256`. `row_wise` is ~32× above it; ideal tiled is ~2× above it; measured tiled at n = 1000 is ~11× above it.
- **Evidence:** `perf` on Zen 2. `cache-misses` is **L2**, not last-level. L1 miss counter includes prefetch; L2 miss counter does not. WSL2 cannot count L3/DRAM — the tiled win at n ≥ 1000 is a timing result.
- **Open questions:** cache-oblivious version, padded/copied layout to remove the 4096-byte conflict, cache simulator for regime (c) (cache < one row), n = 2048, native Linux L3 counters.
- **Report:** [experiments/01-matrix-multiplication/README.md](../experiments/01-matrix-multiplication/README.md)
- **Data:** `experiments/01-matrix-multiplication/results/2026-10-18-ryzen5500u-wsl2/` and `.../2026-11-01-ryzen5500u-wsl2/`

---

## Research log

### 2026-10-12 / 2026-10-13 — set up the project

**Q. What is this repository for?**
A. Master's thesis on algorithm optimisation, cache behaviour and concurrency. One experiment at a time, C++20 + CMake, shared bash scripts so every experiment is measured the same way.

**Q. What was recorded?**
A. Environment file dated 2026-10-13: AMD Ryzen 5 5500U, WSL2 Ubuntu, g++ , L1d / L2 / L3 sizes as Linux reports them. First commit around 2026-10-12. No systematic timings yet.

---

### 2026-10-18 — first full run of experiment 01

**Q. Does changing the loop order of matrix multiplication matter, and do cache counters show why?**
A. Yes. On this laptop, `naive` / `row_wise` was 2.6× (n=64), 5.4× (128), 9.4× (256), 24.5× (512), 11.6× (1024). `tiled` (d=32) matched `row_wise` up to n=512 and was **2.0×** faster at n=1024.

**Q. What did the counters say?**
A. At n=512: `naive` L1 miss rate 65% vs 8.5% `row_wise` vs 18% `tiled`. The generic `cache-misses` event was 136 M (`naive`) vs 0.49 M (`row_wise`). We wrote “last-level / LLC” in the README. **That name was wrong** — see 2026-11-01.

**Q. Is the speedup just the compiler vectorising `row_wise`?**
A. No. At n=512 without auto-vectorisation, `row_wise` was still 14× faster than `naive` (799 ms vs 56 ms). SIMD added another ~1.7× for `row_wise`. We treated “14× is the memory effect” as general. It is not: n=512 is also the conflict-miss case.

**Q. Why does `tiled` win only at n=1024?**
A. Hypothesis: B is 2 MB at n=512 (fits in 4 MB L3) and 8 MB at n=1024 (does not), so `row_wise` streams B from RAM once per row. The counters did not confirm it (`tiled` had _more_ L1 misses). We left it as a hypothesis.

**Q. What did we write down as conclusions (later corrected)?**
A.

- “10× to 25× for n ≥ 256” — only true for power-of-two n.
- “over 100× more last-level cache misses” — L2, not LLC; and the 100× is the power-of-two case.
- “The hardware counts only demand misses” — true for the L2 event, false for L1.
- Load counts “not exact” — partly WSL noise with only 3 measured runs.

**Data:** `experiments/01-matrix-multiplication/results/2026-10-18-ryzen5500u-wsl2/`

---

### 2026-11-01 — cache, theory, and second measurement

#### Questions

**Q1. Theoretical derivation of the number of cache misses for (a) naive, (b) row-major × col-major, (c) tiled. Why do the answers depend on cache size and line size?**
A. A miss is “the CPU had to bring in a new 64-byte line”. How many of those you pay depends on (1) how you walk memory and (2) how much the cache can hold of what you walked. Line size `L = 8` doubles turns a sequential walk of `n³` accesses into `n³/L` misses. Cache size `Z` decides whether a column, two rows, or three tiles stay resident. If they do not, you pay again.

- (a) `naive`, both matrices row-major: `Q ≈ n³/L` if the B column fits without conflicts, `Q ≈ n³` if it does not. On our L1 the column-fits boundary is n ≤ 455, and only if the column is not jammed into a few sets.
- (b) row-major × **column-major**: if B is stored transposed, `naive`'s inner loop becomes sequential. Same traffic as our `row_wise`. We did not implement a transposed B.
- (c) tiled, `d × d`: `Q ≈ 2 n³/(d L) + n²/L` when `L ≤ d ≤ √(Z/3)`. For L1, `d* ≈ 37`, so d = 32.

**Q2. What is “the lower bound for the number of cache misses in matrix multiplication”?**
A. A proof, not a measurement. Any algorithm that does the classical `n³` multiply-adds must move at least `Ω(n³ / √Z)` words (Hong & Kung 1981), or `2 n³ / (L √Z)` lines with the tight constant of Smith, Lowery, Langou, van de Geijn (arXiv:1702.02017). You cannot beat that by a cleverer loop order. You _can_ beat it with Strassen-type algorithms, which do less arithmetic. Compulsory traffic `3 n²/L` is a second, smaller bound (read A, B once; write C once).

On our L1 (Z = 4096, L = 8) the bound is `n³/256`. At n = 1000 that is 3.9 M misses. We measured 1128 M (`naive`), 129 M (`row_wise`), 42 M (`tiled`). Ratios 289× / 33× / 11×; the model predicted 256 / 32 / 2 for ideal tiled.

**Q3. Three regimes: (a) whole matrix < cache, (b) one row < cache < matrix, (c) cache < one row. How do the algorithms perform, and how does the system behave?**
A. Apply the three cases **per cache level**.

| Regime                        | L1 (32 KiB)   | L2 (512 KiB) | L3 (4 MiB)  |
| ----------------------------- | ------------- | ------------ | ----------- |
| (a) matrix fits               | n < 64        | n < 256      | n < 724     |
| (b) row fits, matrix does not | 64 ≤ n ≤ 4096 | n ≥ 256      | n ≥ 724     |
| (c) row does not fit          | n > 4096      | n > 65 536   | n > 524 288 |

We never reach (c) on this machine. In (a) all three versions have only compulsory misses; they should be close (at n=64 `naive` was still 2.6× — one matrix already fills L1). In (b) `row_wise` pays `n³/L` and is bandwidth-bound; `naive` pays `n³` if the column conflicts and is latency-bound; `tiled` pays `2 n³/(d L)` and cuts RAM traffic once B exceeds L3. In (c) `row_wise` would lose the second row as well (`2 n³/L`); tiling would keep working. To see (c) we need n > 4096 or a simulator.

**Q4. There is a whole hierarchy. Which cache are the counters talking about?**
A. L1d 32 KiB per core, L2 512 KiB per core, L3 4 MiB per 3-core CCX (victim cache). On AMD Zen 2, `perf` `cache-misses` = **L2 misses**, confirmed equal to raw event `r0964`. On Intel the same name means LLC. WSL2 has no `amd_l3` / `amd_df` devices, so L3/DRAM is inferred from time.

#### What we measured today

**Q. Are the 2026-10-18 miss counts trustworthy?**
A. The shape is right; the 3-run method is too noisy under WSL2 (a `row_wise` n=256 row even went negative in an early retry). We added `COUNTER_RUNS` and re-ran with 30 measured runs for n ≤ 512 and 10 for n = 1000/1024. Validity check: `l1_loads_per_run ≈ 1.5 n³`. That held within 5% except `naive` n=1024 at 1.25×.

**Q. Does `row_wise` really match `n³/L`?**
A. Yes. Measured / predicted at n = 250, 256, 400, 500, 512, 1000, 1024: 0.99, 1.02, 1.02, 1.02, 1.02, 1.03, 1.07. The leftover is the extra cache line from allocations sitting at page + 16 bytes (checked with a tiny allocator program: every matrix at n ≥ 250 had `address % 64 = 16`).

**Q. Why is `naive` ~3× at n=250/400/500 but ~10–24× at n=256/512/1024?**
A. Set mapping, not “big matrices are slow”. n=512 or 1024: one B column uses **1** L1 set (8 lines) and, because the stride is 4 KiB, only 16 L2 sets (128 lines). n=256: 2 L1 sets. n=250: many L1 sets, column fits, misses ≈ `n³/L`. n=400: 32 L1 sets hold only 256 lines < 400, so L1 still thrashes but L2 does not — time stays in the 3× bucket. n=1024 `naive` is **5.6× slower** than n=1000 for 2.4% more flops (9.65 s vs 1.72 s).

**Q. Can we confirm the L3 / RAM story for tiled vs `row_wise`?**
A. Timing sweep n = 600, 650, …, 1000. `row_wise` falls from ~5.3 GFLOPS at 600 to 2.58 at 1000, **gradually**, not as a cliff at n=725. `tiled` stays ~6.1–6.9. Ratio 2.4× at n=1000, 2.1× at n=1024. No L3 counter in WSL2; bytes/time for `row_wise` at n=1024 is ~11 GB/s, a plausible single-core RAM stream.

**Q. Does the tile-size formula hold?**
A. Sweep d = 8, 16, 32, 64, 128 at n=1000. U-shape, minimum at d=32 (6.53 GFLOPS). d=64 already overflows L1 (`3×64² = 12288 > 4096`) and L1 misses jump to 210 M (like `row_wise`). Matches `d* ≈ √(Z/3) ≈ 37`.

**Q. SIMD vs memory at a non-power-of-two n?**
A. n=500, no-vectorisation: `row_wise` 2.3× faster than `naive` (60 ms vs 136 ms). SSE2 adds 1.21× for `row_wise`. Use this, not the 14× at n=512, when splitting “cache vs SIMD”.

**Q. What about the TLB?**
A. `naive` at n=512: ~n³ L1-TLB misses, 1.18 M walks — L2 TLB (2048) still holds 3×512 pages. At n=1024: 114 M walks, because 3 matrices = 6144 pages > 2048. The 19-nov note that “few walks are needed” is true at 512 and false at 1024.

**Q. What did we change in the tooling?**
A. `COUNTER_RUNS` in `benchmark.conf` / `scripts/lib/common.sh` (default 3). `cache_counters.sh` now also records dTLB events and documents that generic event names depend on the CPU. `environment.sh` prints `lscpu -C`, page size and THP. `VARIANTS` was already overridable (used for the tile sweep).

**Q. What earlier sentences are now known to be wrong?**
A.

1. `cache-misses` = last-level / LLC → it is L2 on Zen 2.
2. “10× to 25× for n ≥ 256” → only power-of-two n; else ~3×.
3. “hardware counts only demand misses” → L2 event yes, L1 event no (includes prefetch).
4. “14× without SIMD is the memory effect” → true at n=512, inflated by conflicts; 2.3× at n=500.
5. “counters do not explain tiled at 1024” → L1 counters _should not_ explain it; the mechanism is L3/RAM reuse, visible in the GFLOPS sweep.
6. Load counts “should be ~2 n³ and we see 213 M at n=512” → the counter is per instruction including stores; expect `~1.5 n³` (201 M at n=512). 213 M was a noisy 3-run value; today 212 M with 30 runs, close enough.

**Data:** `experiments/01-matrix-multiplication/results/2026-11-01-ryzen5500u-wsl2/`
(timings, cache-counters, no-vectorization-500, large-n/, l3-sweep/, tile-sweep/d8…d128/, perf-event-mapping.txt)
