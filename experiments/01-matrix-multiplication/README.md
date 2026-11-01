# Experiment 01: Memory-access order in matrix multiplication

## Research question

Matrices are stored row by row (row-major). Moving along a row follows memory order, while moving down a column jumps a whole row at a time. How much does this cost in matrix multiplication, and can changing the access order fix it? Can cache measurements explain the difference?

## Theory

A CPU fetches data in chunks called cache lines (typically 64 bytes, i.e. 8 `double` values), not one number at a time. When a cache line is loaded, nearby elements are already available for the next accesses.

```text
A = [ 1  2  3  4  5]
    [ 6  7  8  9 10]
    [11 12 13 14 15]
```

1. **Moving across a row (good spatial locality).** `1 -> 2 -> 3 -> 4` are consecutive in memory. One cache line serves several accesses.
2. **Moving down a column (poor spatial locality).** `1 -> 6 -> 11` skip the rest of the row. For a matrix with `n` columns the distance between vertical neighbours is

   ```text
   stride = n * sizeof(element)
   ```

   For `double` and `n = 512` that is 512 \* 8 = 4096 bytes. Almost every access touches a different cache line, so a vertical traversal can touch many cache lines even when the whole matrix is small.

## The three versions (`main.cpp`)

All three compute the same product `C = A * B`. Matrices are stored in contiguous row-major order: element `(i, j)` is at `i * n + j`. They differ only in the order of memory accesses.

| Name       | Loop order                 | What the inner loop does to B                                        |
| ---------- | -------------------------- | -------------------------------------------------------------------- |
| `naive`    | i, j, k (textbook)         | `B[k*n + j]` changes k: walks **down a column** (stride `n*8` bytes) |
| `row_wise` | i, k, j                    | `B[k*n + j]` changes j: walks **along a row** (contiguous)           |
| `tiled`    | i, k, j inside 32x32 tiles | works on one small tile at a time so the data stays in cache         |

Every run checks its result against `naive` (tolerance 1e-9) before timing. All three versions produce identical checksums at every size.

## How to build and run

From the repository root, see the main [README](../../README.md) for the build instructions (Release is the default build type). Then, for example:

```bash
./build/experiments/01-matrix-multiplication/matrix_multiplication row_wise 512
```

Usage: `matrix_multiplication <naive|row_wise|tiled> <n> [repetitions=7] [tile_size=32]`

The program prints a CSV header and one result row.

To reproduce all results (build, timings, cache counters, no-SIMD check, environment file) on Linux or WSL:

```bash
bash scripts/run.sh experiments/01-matrix-multiplication
```

This uses the shared tooling in [`scripts/`](../../scripts/README.md) with this experiment's [`benchmark.conf`](benchmark.conf) (target, versions, sizes, repetitions). It writes a new folder under `results/` named `<date>-local`; rename it to `<date>-<machine>` if you keep it. It takes roughly 5 to 10 minutes on the machine below, mostly because of `naive` at n=1024. To run only some checks, add their names (`environment`, `timings`, `cache_counters`, `no_vectorization`).

## Method

- Machine: AMD Ryzen 5 5500U, WSL2 (Ubuntu 26.04), g++ 15.2.0, `-O3 -DNDEBUG` (Release). Caches: L1d 32 KiB per core, L2 512 KiB per core, L3 4 MB. Full details: `results/2026-10-18-ryzen5500u-wsl2/environment.txt`.
- Matrices of `double`, uniform random in [-1, 1], fixed seed (12345). Each version runs in its own process.
- Timing: one warm-up run, then the median of the repeated runs (7 repetitions, 5 at n=1024). Allocation and input generation are outside the timed region.
- Cache counters: `perf stat` (user-mode events). The program also runs a reference multiply and setup in the same process. To remove that, each version was run with 1 and with 4 repetitions, and the counter difference was divided by 3. All values are per multiplication.

## Results (`results/2026-10-18-ryzen5500u-wsl2/`)

### Execution time (`timings.csv`)

| n    | naive (ms) | row_wise (ms) | tiled (ms) | naive / row_wise | row_wise / tiled |
| ---- | ---------- | ------------- | ---------- | ---------------- | ---------------- |
| 64   | 0.136      | 0.052         | 0.058      | 2.6x             | 0.9x             |
| 128  | 2.20       | 0.41          | 0.48       | 5.4x             | 0.9x             |
| 256  | 38.2       | 4.06          | 4.01       | 9.4x             | 1.0x             |
| 512  | 832        | 34.0          | 36.4       | 24.5x            | 0.9x             |
| 1024 | 8630       | 742           | 369        | 11.6x            | 2.0x             |

- Reordering the loops (`naive` to `row_wise`) gives a speedup that grows with n, up to about 25x at n=512.
- At n=1024 the `naive` / `row_wise` ratio drops to 11.6x because `row_wise` itself slows down: from 7.9 GFLOPS at n=512 to 2.9 GFLOPS at n=1024.
- Tiling gives no gain up to n=512, but is **2x faster than `row_wise` at n=1024**. A likely reason is that B (2 MB at n=512) still fits in L3 (4 MB), while B at n=1024 (8 MB) does not.
- Run-to-run variation under WSL2 is large: `naive` at n=512 measured between 822 and 1148 ms across several runs, and the `naive` / `row_wise` ratio at n=512 between 24.5x and 30x. A full re-run with the scripts on a laptop running on battery (Balanced power plan, other programs open) was 10% to 160% slower in absolute time than the data below, while giving identical checksums, L1 miss rates within about 2 percentage points, and the same conclusions (12x, 30x and 12x for `naive` / `row_wise` at n = 256, 512, 1024; `tiled` 2.1x faster than `row_wise` at n=1024). For timing runs, plug the laptop in, use a high-performance power plan and close other programs. Treat speedups as approximate.

### Cache counters (`cache-counters.csv`)

| n    | Version  | L1d loads | L1d load misses | L1 miss rate | Cache misses (generic event) |
| ---- | -------- | --------- | --------------- | ------------ | ---------------------------- |
| 512  | naive    | 213 M     | 138.8 M         | 65.1%        | 135.9 M                      |
| 512  | row_wise | 204 M     | 17.3 M          | 8.5%         | 0.49 M                       |
| 512  | tiled    | 208 M     | 37.8 M          | 18.1%        | 1.72 M                       |
| 1024 | naive    | 1970 M    | 1181 M          | 60.0%        | 1092 M                       |
| 1024 | row_wise | 1614 M    | 133.4 M         | 8.3%         | 9.4 M                        |
| 1024 | tiled    | 1652 M    | 315.0 M         | 19.1%        | 12.7 M                       |

- `naive` misses L1 on 60 to 65% of loads, against about 8% for `row_wise`. That is 8 to 9 times more L1 misses.
- On the generic cache-misses event, `naive` has 116 to 275 times more misses than `row_wise`.
- This supports the cache explanation: the column walk in `naive` causes far more cache misses, and it is much slower.

### Cache or vectorisation? (`no-vectorization-512.csv`)

Same code at n=512, compiled with `-fno-tree-vectorize -fno-tree-slp-vectorize`:

| Version  | With auto-vectorisation (ms) | Without (ms) |
| -------- | ---------------------------- | ------------ |
| naive    | 832                          | 799          |
| row_wise | 34.0                         | 56.0         |
| tiled    | 36.4                         | 57.5         |

Without SIMD, `row_wise` is still **14x faster** than `naive` (versus 24.5x with SIMD). Roughly, about 14x of the gap comes from memory-access order and a further factor of about 1.7x from the compiler vectorising `row_wise` (it cannot vectorise the `naive` sum without relaxing floating-point rules).

## Conclusions

1. Row-wise (contiguous) access in the inner loop is the main factor. Reordering loops alone gives 10 to 25x at n >= 256, with the same arithmetic and the same result.
2. Cache counters back this up: the column-wise version has about 8x more L1 misses and over 100x more last-level cache misses.
3. Tiling pays off once the working set no longer fits in L3 (2x at n=1024). It does not at n <= 512.

## Limitations

- Counters are approximate under WSL2 virtualisation. Load counts are in the expected range but not exact (for example `naive` at n=512 should have about 268 M loads and shows 213 M). Use them for ratios, not absolute values.
- The hardware counts only demand misses. Prefetched lines are not counted, so `row_wise` has few counted misses at n=1024 even though it streams B from L3 or memory.
- **The counters do not explain why `tiled` beats `row_wise` at n=1024.** `tiled` actually shows more L1 misses (315 M against 133 M). The timing result is real, but the mechanism (better reuse of tiles from L2, less streaming of B from L3 and memory) is a hypothesis that these counters do not confirm.
- Only a tile size of 32 was tested. Sizes stop at 1024; n=2048 was not run because the built-in `naive` reference check takes several minutes.
- One machine, one compiler, `double` precision only, no multithreading.
