# Experiment 01: matrix multiplication, figures

All charts and diagrams of experiment 01 live here. They are generated from the CSV files in `experiments/01-matrix-multiplication/results/<session>/` by `scripts/plot/` (see [scripts/plot/README.md](../../scripts/plot/README.md)); do not edit them by hand.

- **Agenda of the experiment:** [experiments/01-matrix-multiplication/README.md](../../experiments/01-matrix-multiplication/README.md)
- **Results and drawbacks (short):** [docs/findings-log.md](../findings-log.md)

```text
docs/01-matrix-multiplication/
├── README.md                 this page: what every figure shows and how to explain it
├── diagrams/                 pictures that explain the idea (no measurements)
└── figures/
    ├── 2026-10-18-ryzen5500u-wsl2/        first session: naive / row_wise / tiled, cache counters, SIMD
    └── 2026-11-14-ryzen5500u-wsl2-run2/   second session: tile sizes, 3 layouts, cache-aware vs cache-oblivious
```

Each figure exists as `.png` (slides) and `.pdf` (vector, for the thesis). The file names start with the topic: `overview_`, `layout_`, `tile_`, `oblivious_`, `cache_`, `simd_`, `quality_`.

Machine for all figures: AMD Ryzen 5 5500U, one thread, `double`, g++ -O3, WSL2. L1d 32 KiB, L2 512 KiB per core, L3 4 MiB. One n x n matrix is 8 n^2 bytes (n = 1024: 8 MiB, n = 2048: 32 MiB). The grey band in several figures is +-10 %: the same measurement repeated differs by about 3 to 4 % (see `quality_noise_check`), so smaller differences should not be explained.

## Suggested order for explaining the results

1. `diagrams/memory_layouts` and `diagrams/recursion_steps`: what the three layouts and the cache-oblivious recursion are.
2. `overview_ranking`: who wins.
3. `overview_gflops_vs_n`: why plain loops collapse for large matrices.
4. `tile_size_vs_time` and `tile_fit_regimes`: how the tile size matters, and what happens when the tile does not fit.
5. `layout_comparison` and `layout_tile_wise_vs_row_major`: does the layout matter.
6. `oblivious_vs_aware`: cache-oblivious against cache-aware.
7. `cache_misses`: the hardware counters (only the October session, see the limits below).
8. `quality_noise_check`: how far the numbers can be trusted.

## Diagrams (`diagrams/`)

| File | Shows | Say |
|---|---|---|
| `memory_layouts` | The same 8 x 8 matrix stored row-major, column-major and tile-wise (4 x 4 tiles). Same colour = same 64-byte cache line. | Walking along a row touches 1 cache line in row-major, 8 in column-major, 2 in tile-wise; walking down a column is the reverse, and tile-wise is a compromise. The picture is computed from the same index formulas as `main.cpp`. |
| `recursion_steps` | How the cache-oblivious algorithm halves i, then j, then k. | The recursion never uses a cache size. At some depth the three blocks fit into every cache level by themselves. |

## Session 2026-11-14 (`figures/2026-11-14-ryzen5500u-wsl2-run2/`)

Data: `tile-sweep.csv` (row-major and tile-wise, tile sizes 4 to 512, n = 256 to 2048) and `oblivious.csv` (all nine versions, parameters 32, 64, 128). Machine conditions are in `run-conditions.txt` of the results folder.

### Overview

| Figure | Shows | Reading it |
|---|---|---|
| `overview_ranking` | All versions at n = 1024 and n = 2048, fastest on top, with the best parameter of each. | At n = 2048 the plain loops need 4.9 s; every tiled or recursive version needs 1.8 to 2.8 s. The fastest is cache-oblivious on tile-wise (1819 ms, 2.7 times faster than `row_wise`), then cache-aware tile-wise (1884 ms). |
| `overview_gflops_vs_n` | GFLOPS against n for all versions, best parameter. | The plain loops lose more than half of their speed between n = 512 and n = 1024 (from about 8 to 3.5 GFLOPS), where one matrix (8 MiB) becomes larger than L3 (4 MiB). Tile-wise stays at about 9 to 9.7 GFLOPS for every size. |
| `overview_time_vs_n` | Time against n on log-log axes with the n^3 growth of the work. | Without a cache problem a curve would be parallel to the n^3 line. The plain-loop curves bend upward at n = 1024; the tiled and recursive curves stay close to parallel. |
| `overview_speedup_bars` | Speed-up over `row_wise` for three layouts x plain / aware / oblivious. | Same information as the ranking, grouped by layout. The number inside a bar is the best tile size or recursion base. |

### Storage layout

| Figure | Shows | Reading it |
|---|---|---|
| `layout_algorithms` | One panel per layout, every algorithm and parameter against n. | The dotted plain-loop line is the one that drops. All cache-aware and cache-oblivious lines stay far above it. In the row-major and column-major panels the lightest lines (parameter 32) are the lowest at n = 2048. |
| `layout_comparison` | The three layouts side by side for each kind of algorithm, best parameter. | Plain loops: row-major and column-major are the same within 2 % for n >= 1024 (the loop order makes the symmetric difference, as predicted). Cache-aware and cache-oblivious: tile-wise is the fastest layout at n >= 512, by about 15 to 45 % depending on the case. |
| `layout_tile_wise_vs_row_major` | Time(tile-wise) / time(row-major) for the same loops and tile size. | Below 1 the tile-wise layout is faster. Inside the grey band (mostly n = 256 and n = 512) the difference is not reliable. For n = 1024 and n = 2048 it is below the band for every tile size; the largest gains are at tile size 512 (ratio 0.37 at n = 2048, 0.57 at n = 1024) and, at n = 1024, at tile size 4 (0.42). |

### Tile size

| Figure | Shows | Reading it |
|---|---|---|
| `tile_size_vs_time` | Time against tile size, one panel per n. Stars mark the best tile size; dotted lines mark where three tiles fill L1, L2, L3. | U-shaped for n >= 1024. Tile size 4 is slower than not tiling at every n (and 8 is too on row-major); the best size is T = 128 for both layouts at n >= 1024. |
| `tile_fit_regimes` | GFLOPS against the memory the three tiles need (24 T^2 bytes), background = which cache level they fit. | Answers the question "what if the tile does not fit": the best point is T = 128 (384 KiB, fits L2 but not L1). At T = 512 the tiles are larger than L3. Row-major then falls (n = 2048: from 6.9 to 3.1 GFLOPS, below the plain loops with 3.6); tile-wise falls much less (from 9.3 to 8.3). |
| `tile_speedup_heatmap` | Speed-up over `row_wise` for every n and tile size. | Overview of the whole sweep in numbers. Values below 1x (red) are slower than not tiling. |

### Cache-oblivious

| Figure | Shows | Reading it |
|---|---|---|
| `oblivious_parameter` | Cache-aware and cache-oblivious time for each parameter value. | The parameter matters by up to about 20 % between 32 and 128 (largest for row-major at n = 2048, where 32 is 19 % slower than 128); 32 is generally the weakest. Every value is far better than the plain loops (grey dashed line). |
| `oblivious_vs_aware` | Best cache-aware time / best cache-oblivious time per layout and n. | For n >= 512 all values are between 0.97 and 1.08: the recursion, which needs no cache size, is as fast as the tuned tiles (within the noise). n = 256 is faint because the runs last only a few ms. |

### Quality of the measurement

| Figure | Shows | Reading it |
|---|---|---|
| `quality_noise_check` | The same configuration measured in two separate passes of the session (`tile-sweep.csv` and `oblivious.csv`). | 28 pairs; median difference 4.1 % (3.2 % for n >= 512). At n = 256 one pair differs by 40 %, so n = 256 is not used for conclusions. At n = 2048 the row-major tile results are 7 to 9 % faster in the second pass: a small systematic drift (cause not investigated). |

## Session 2026-10-18 (`figures/2026-10-18-ryzen5500u-wsl2/`)

Data: `timings.csv`, `cache-counters.csv` (from `perf stat`, user-mode events only under WSL2), `no-vectorization-512.csv`. Versions: `naive`, `row_wise`, `tiled` (tile size 32), all row-major.

| Figure | Shows | Reading it |
|---|---|---|
| `overview_baseline` | GFLOPS of the three versions against n. | The naive i,j,k loop is slow already at n = 64 and falls to 0.25 GFLOPS at n = 1024. |
| `cache_misses` | L1 miss rate, L1 misses per multiply-add, last-level misses. | `naive` misses L1 on 60 to 65 % of the loads and has about 1.1 billion last-level misses at n = 1024; `row_wise` 8 % and 9.4 million. `tiled` (tile size 32) has a higher L1 miss rate than `row_wise` (18 to 19 %). |
| `cache_misses_vs_speed` | GFLOPS against the counters, one point per version and size. | The counters explain the gap between `naive` and the others, but not the gap between `row_wise` and `tiled` at n = 1024: `tiled` has more misses and is still twice as fast. The generic `cache-misses` event is only a rough measure, so this is an open question, not a result. |
| `simd_vectorization` | Time with and without auto-vectorisation at n = 512. | Without SIMD `row_wise` is 56 ms instead of 34 ms; the naive version does not change (832 against 799 ms). The speed-up of the better loop order is therefore not a SIMD effect. |

## What is not covered yet

- **Cache misses for column-major, tile-wise and the cache-oblivious versions.** Finished counters exist only for `naive`, `row_wise` and `tiled` (October). `perf` works again (2026-11-15), but the multi-layout counter run was stopped on purpose; the partial CSV in `results/2026-11-15-ryzen5500u-wsl2-counters/` is not a finished result (see `15-nov.txt`). The reasons why tile-wise is faster remain hypotheses. The `cache_misses` figure already supports any version in `cache-counters.csv`.
- **Large matrix sizes and wall time.** The work grows as n³, so n = 4096 is about eight times more work than n = 2048 (one multiply ~20 to 40 s). A full tile/layout/oblivious sweep there was expected to take more than an hour and was stopped after four runs; that session has no figures. Large tile sizes (T ≤ 512) were measured at n ≤ 2048 — the wall-time problem is the matrix dimension, not the tile size. n = 8192 does not fit in ~3 GB of WSL2. The first, noisy run of 2026-11-14 also has no figures (not used).
- Error bars: the program prints only the median of the repetitions.
