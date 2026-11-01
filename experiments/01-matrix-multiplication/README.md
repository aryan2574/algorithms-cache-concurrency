# Experiment 01: Memory-access order in matrix multiplication

## Research questions

Matrices are stored row by row (row-major). Moving along a row follows memory order; moving down a column jumps a whole row at a time. How much does this cost in `C = A * B`, and can cache measurements explain it?

1. **Theoretical miss counts** for (a) row-major × row-major (`naive`), (b) row-major × column-major (same traffic as `row_wise` if B is stored transposed; we did not implement a transposed B), (c) tiled with `d × d` tiles. Every answer depends on cache size `Z` and line size `L`.
2. **Lower bound** from the literature: the fewest cache misses any classical (`n³` multiply-add) algorithm can have.
3. **Three regimes:** (a) whole matrix < cache, (b) one row < cache < whole matrix, (c) cache < one row. How do the three versions behave in each, and what does the machine actually do?
4. **Which cache are we measuring?** This CPU has L1, L2 and L3. The generic `perf` name `cache-misses` is **L2 misses** on AMD Zen 2, not last-level / L3. WSL2 cannot count L3 or DRAM.

Hardware vocabulary (sets, ways, prefetch, TLB, AMAT) is in [`19-nov.txt`](19-nov.txt). Dated notes of what was done when are in [`docs/findings-log.md`](../../docs/findings-log.md).

## Findings in one page (2026-11-01)

On an AMD Ryzen 5 5500U (L1d 32 KiB / L2 512 KiB / L3 4 MiB, 64-byte lines), `double` matrices, Release `-O3`:

| What                                                                                                                 | Why it happens                                                                                                                                                                                                                                                                                                   |
| -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `row_wise` L1 misses = `n³/8`, within 1–7%                                                                           | Inner loop walks rows. One 64-byte line serves 8 doubles. This is the formula, and the counter matches it at every size we ran.                                                                                                                                                                                  |
| `naive` L1 misses ≈ `n³` at n = 256, 400, 500, 512, 1000, 1024                                                       | The inner loop walks a **column** of B. Each step is a new cache line, so almost every access misses. At n = 250 the column still fits in L1 and misses drop to about `n³/8`.                                                                                                                                    |
| `naive` is 3–4× slower than `row_wise` at n = 250, 400, 500, but **9–24×** at n = 256, 512, 1024                     | Extra factor is **conflict misses**, not capacity. A power-of-two row is a multiple of 4096 bytes, so a whole column of B maps to 1 or 2 L1 sets (8 ways). Those 8–16 lines cannot hold a column of 256–1024 lines, so L1 (and at 512/1024 also L2) thrashes.                                                    |
| `naive` at n = 1024 is 5.6× slower than at n = 1000, for 2.4% more work                                              | n = 1024 column → 1 L1 set and 8 L2 sets. n = 1000 column spreads over all 64 L1 sets and all 1024 L2 sets. Same arithmetic; the address mapping is different.                                                                                                                                                   |
| `tiled` (d = 32) does nothing useful up to n = 512, then is **2.0–2.4×** faster than `row_wise` at n = 1000 and 1024 | `row_wise` streams all of B once per row of A. B is 8 MB at n = 1024 and no longer fits in the 4 MiB L3, so that stream comes from RAM (~11 GB/s). Tiling reuses each B tile `n/d` times while it is still in L2/L3. L1 miss counts go **up** for tiled; the win is fewer trips to RAM, which WSL2 cannot count. |
| Tile-size sweep at n = 1000: d = 32 is fastest (6.53 GFLOPS). d = 8 is slow; d = 64 and 128 fall off                 | L1 optimum is `d* ≈ √(Z/3) ≈ 37`. d = 32 fits three tiles in L1; d = 64 does not (3 × 64² = 12 288 doubles > 4096).                                                                                                                                                                                              |
| Without SIMD at n = 500, `row_wise` is still 2.3× faster than `naive`                                                | Access order, not vectorisation, is the main effect. SIMD (SSE2 only; no AVX2 in this build) adds about 1.2× for `row_wise`/`tiled`. The old “14× without SIMD at n = 512” mixed this with the power-of-two conflict.                                                                                            |

**Corrections to the 2026-10-18 write-up:** `cache-misses` is L2, not last-level. “10× to 25× for n ≥ 256” is the power-of-two case; nearby sizes are ~3×. The hardware L1 miss counter **includes** prefetches; the L2 counter **excludes** L2 prefetches. Load counts near `1.5 n³` are expected (`L1-dcache-loads` counts loads and stores, one per instruction, and SSE2 moves 2 doubles).

---

## Theory

### Cache lines

The CPU fetches 64-byte **cache lines**, not single numbers. A line holds `L = 8` doubles.

```text
A = [ 1  2  3  4  5]
    [ 6  7  8  9 10]
    [11 12 13 14 15]
```

1. Along a row (`1 → 2 → 3 → 4`): neighbours in memory. One line serves several accesses.
2. Down a column (`1 → 6 → 11`): skip the rest of the row. Distance = `n × 8` bytes. For `n = 512` that is 4096 bytes, so every vertical step is a **different line** and, on this L1, the **same set**.

### Model and notation

Ideal-cache model (Frigo, Leiserson, Prokop, Ramachandran, FOCS 1999): one cache of `Z` elements, line size `L` elements, fully associative, optimal replacement. `Q` = number of lines moved into the cache (misses).

| Level                |   Bytes | `Z` (doubles) |  Lines | `L` |
| -------------------- | ------: | ------------: | -----: | --: |
| L1 data              |  32 KiB |         4 096 |    512 |   8 |
| L2                   | 512 KiB |        65 536 |  8 192 |   8 |
| L3 (usable, one CCX) |   4 MiB |       524 288 | 65 536 |   8 |

On this CPU the L3 is a **victim cache** (a line enters L3 only when L2 evicts it) and is shared by 3 cores. One core can keep about 4.5 MiB (L2 + L3) close by. WSL2 reports 4 MiB L3.

### Two counting rules

1. A contiguous walk of `m` doubles costs `m / L` misses (one miss per line).
2. A walk with stride ≥ one line (a column of B) costs `m` misses, unless those `m` lines already sit in the cache.

Compulsory traffic for any algorithm that reads A, B and writes C once: `Q ≥ 3 n² / L`.

### (a) `naive` — row-major × row-major, loop order (i, j, k)

Inner loop: `sum += A[i,k] * B[k,j]`. A is walked along a row; B is walked **down a column**.

For each of the `n²` pairs `(i, j)` the inner loop does `n` accesses to B, each a new line. Those `n` lines (one column) stay in cache only if they fit **and** do not collide in one set.

- **Column fits** (`Z ≥ (L+1) n` lines: the column plus the current row of A): B is paid once per line, `Q ≈ n³ / L + 2 n² / L`.
- **Column does not fit** (capacity: `n` lines > `Z / L`, or conflict: the column uses fewer sets than it has lines): almost every B access misses, `Q ≈ n³`. With LRU, the sequential walk of A can miss as well and `Q ≈ n³ (1 + 1/L)`.

On L1, `(L+1) n ≤ 4096` means `n ≤ 455`. That is why n = 250 is the only size in this study where `naive` should (and does) look like `n³/L`. At n = 400 the fully-associative test still says “fits”, but a 400-element column uses only 32 of 64 L1 sets (8 × 32 = 256 lines < 400), so it **conflicts** and we see `n³`.

### (b) Row-major × column-major

If B were stored **column-major**, `naive`'s inner loop would walk B in memory order. The miss count is then the same as our `row_wise` on row-major storage: `Q ≈ n³ / L` whenever two rows fit (`2n ≤ Z`). We did not implement a transposed B; `row_wise` is the equivalent access pattern.

### `row_wise` — loop order (i, k, j)

Inner loop walks `B[k, :]` and `C[i, :]` (contiguous). Working set: two rows = `2n` doubles.

- Two rows fit (`2n ≤ Z`), matrix B does not (`n² > Z`): each of the `n³` inner-loop accesses to B is sequential, so `Q ≈ n³ / L + 2 n² / L`.
- On L1 this holds for all our n (need only `n ≤ 2048`). The **time** still changes with n, because the `n³ / L` lines have to come from L2, L3 or RAM depending on whether B itself fits there.

### (c) `tiled` — `d × d` tiles, (i, k, j) inside each tile

Three tiles (a piece of A, of B, of C) must fit: `3 d² ≤ Z`, i.e. `d ≤ √(Z/3)`. Also want `d ≥ L` so a tile row is at least one line.

Each B tile is reused `n/d` times (once per A-tile-row). Traffic:

`Q ≈ 2 n³ / (d L) + n² / L`

| Cache | `√(Z/3)` | Practical `d` |
| ----- | -------: | ------------: |
| L1    |       37 |            32 |
| L2    |      148 |           128 |
| L3    |      418 |       256–400 |

d = 32 is the L1 choice. Larger d helps L2/L3 reuse but overflows L1.

### What “the lower bound” means (question 2)

It is **not** “the smallest number we measured”. It is a proof that **no** algorithm which does the classical `n³` multiply-adds can move fewer than this many words between cache and memory, no matter the loop order.

Intuition (Hong and Kung 1981; Loomis–Whitney): a cache that holds `Z` numbers can only “see” about `Z^{3/2}` useful multiply-adds before it must reload. Doing `n³` work therefore needs about `n³ / Z^{3/2}` reloads of `Z` words, i.e. `Ω(n³ / √Z)` word transfers, or in lines

`Q ≥ 2 n³ / (L √Z)`

(tight constant: Smith, Lowery, Langou, van de Geijn, arXiv:1702.02017; they also subtract `2Z`, which is negligible for our n). Plus the compulsory `3 n² / L`.

The bound does **not** apply to Strassen-type algorithms (Ballard et al., 2012): those do fewer than `n³` multiply-adds.

| Version                  | Predicted `Q` (regime: two rows fit, matrix does not) | Ratio to the bound     |
| ------------------------ | ----------------------------------------------------- | ---------------------- |
| `naive` (column misses)  | `n³`                                                  | `L √Z / 2` = 256 on L1 |
| `row_wise`               | `n³ / L`                                              | `√Z / 2` = 32 on L1    |
| `tiled` at our d = 32    | `2 n³ / (d L)`                                        | `√Z / d` = 2 on L1     |
| `tiled` at `d* = √(Z/3)` | `2 n³ √3 / (L √Z)`                                    | `√3 ≈ 1.73`            |

Cache-oblivious recursion (Frigo et al.) meets the bound at **every** cache level without knowing `Z`. That is the natural next version.

### The three regimes

Three cases, written for one cache of `Z` elements. They must be applied **per level**: L1, L2 and L3 have different `Z`.

| Regime                       | Definition   | On this laptop                                                    |
| ---------------------------- | ------------ | ----------------------------------------------------------------- |
| (a) whole matrix < cache     | `n² < Z`     | L1: n < 64. L2: n < 256. L3: n < 724.                             |
| (b) one row < cache < matrix | `n ≤ Z < n²` | L1: 64 ≤ n ≤ 4096 (all our n after 64). L2: 256 ≤ n. L3: 724 ≤ n. |
| (c) cache < one row          | `Z < n`      | L1 would need n > 4096. We never reach it.                        |

What each algorithm does:

|            | (a) matrix fits            | (b) row fits, matrix does not                                                               | (c) row does not fit                 |
| ---------- | -------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------ |
| `naive`    | only compulsory `3 n² / L` | `n³ / L` if the column fits and does not conflict; **`n³` if it conflicts or `Z < (L+1)n`** | `n³ (1 + 1/L)` — A and B both miss   |
| `row_wise` | compulsory                 | `n³ / L` as long as `2n ≤ Z`                                                                | `2 n³ / L` — B and C both stream     |
| `tiled`    | compulsory                 | `2 n³ / (d L)` if three tiles fit                                                           | **unchanged**, as long as `3 d² ≤ Z` |

What the **system** does in each regime (this is the machine, not the formula):

- **(a)** After a warm-up, A, B and C live in that cache. Hits. The three versions should be close; leftover differences are loop overhead and a few conflicts. At n = 64 (Oct 18) `naive` was still 2.6× slower: 64² doubles = 32 KiB, so **one** matrix fills L1 and three do not.
- **(b)** The CPU keeps the current row(s) or tile and must reload the rest. `row_wise` is bandwidth-bound: prefetchers hide latency, time ≈ `(bytes moved) / bandwidth`. `naive`'s column walk has no useful prefetch (and at power-of-two n, no useful associativity), so it is **latency-bound**: each miss waits ~12 cycles (L2) or ~40 (L3) or ~100 ns (RAM). Tiling cuts bytes moved by about `n/d` at the level the tile was sized for.
- **(c)** Even one row spills. `row_wise` loses its 8-wide line reuse for C as well. Tiling is the algorithm that still makes sense. We cannot show this on L1 without n > 4096 (or a cache simulator).

For **our sizes on L1**, everyone except n = 64 is in regime (b). The interesting split inside (b) is “does the B column fit / conflict?”, which is why n = 250 and n = 256 behave like different algorithms.

### What the model leaves out

| Reality                                                       | Effect we actually see                                                                                                                                                             |
| ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 8-way (L1/L2) / 16-way (L3), not fully associative            | Power-of-two n: a B column uses 1 L1 set. `tiled` at n = 256/512/1024: the 32 tile rows also share a set, so L1 misses jump ~38× above the formula.                                |
| Allocations sit at page + 16 bytes (checked 2026-11-01)       | Every row starts mid-line → `n/L + 1` lines, not `n/L`. A 32-double tile row spans **5 lines, not 4**. About +25% for tiled, +1–3% for `row_wise`.                                 |
| L1 miss counter includes prefetches; L2 miss counter does not | `row_wise` L1 ≈ theory; `row_wise` L2 is far **below** `n³/L` because the L2 prefetcher already moved the lines.                                                                   |
| Several levels; L3 is a victim cache                          | `row_wise` time drops gradually from n ≈ 600, not as a cliff at n = 724. Effective L3 is smaller than 4 MiB (shared, victim, A and C also pass through).                           |
| TLB (64 L1 + 2048 L2 entries, 4 KiB pages)                    | `naive` at n = 512: ~n³ L1-TLB misses, but only ~1 M page walks (L2 TLB still holds 1536 pages). At n = 1024: 3 matrices = 6144 pages > 2048, and we counted **114 M page walks**. |
| Pseudo-LRU, not optimal / Belady                              | Same counts as the formulas except near a size boundary.                                                                                                                           |

---

## The three versions (`main.cpp`)

All three compute `C = A * B`. Storage is contiguous row-major: `(i, j)` is at `i * n + j`. They differ only in access order. Every run checks its result against `naive` (tolerance 1e-9) before timing.

| Name       | Loop order                   | What the inner loop does to B                                  |
| ---------- | ---------------------------- | -------------------------------------------------------------- |
| `naive`    | i, j, k                      | `B[k*n + j]` changes k: **down a column** (stride `n*8` bytes) |
| `row_wise` | i, k, j                      | `B[k*n + j]` changes j: **along a row**                        |
| `tiled`    | i, k, j inside `d × d` tiles | same as `row_wise`, one tile at a time                         |

## How to build and run

From the repository root (Release is the default; see the main [README](../../README.md)):

```bash
./build/experiments/01-matrix-multiplication/matrix_multiplication row_wise 512
```

Usage: `matrix_multiplication <naive|row_wise|tiled> <n> [repetitions=7] [tile_size=32]`

To reproduce the 2026-11-01 folder:

```bash
# n = 250..512, 30 measured counter runs, no-vectorisation at 500
SIZES="250 256 400 500 512" COUNTER_SIZES="250 256 400 500 512" COUNTER_RUNS=30 NOVEC_SIZE=500 \
    bash scripts/run.sh experiments/01-matrix-multiplication \
    environment timings cache_counters no_vectorization \
    --out experiments/01-matrix-multiplication/results/2026-11-01-ryzen5500u-wsl2

# n = 1000, 1024
SIZES="1000 1024" COUNTER_SIZES="1000 1024" COUNTER_RUNS=10 \
    bash scripts/run.sh experiments/01-matrix-multiplication \
    environment timings cache_counters \
    --out experiments/01-matrix-multiplication/results/2026-11-01-ryzen5500u-wsl2/large-n

# tile-size sweep at n = 1000
for d in 8 16 32 64 128; do
    VARIANTS=tiled EXTRA_ARGS="$d" SIZES=1000 COUNTER_SIZES=1000 COUNTER_RUNS=10 \
        bash scripts/run.sh experiments/01-matrix-multiplication \
        environment timings cache_counters \
        --out experiments/01-matrix-multiplication/results/2026-11-01-ryzen5500u-wsl2/tile-sweep/d$d
done
```

A default `bash scripts/run.sh experiments/01-matrix-multiplication` uses [`benchmark.conf`](benchmark.conf) and writes `results/<date>-local/`.

## Method

- Machine: AMD Ryzen 5 5500U, WSL2 (Ubuntu 26.04), g++ 15.2.0, `-O3 -DNDEBUG`. Geometry from `lscpu -C`: L1d 32 KiB = 64 sets × 8 ways; L2 512 KiB = 1024 × 8; L3 4 MiB = 4096 × 16; 64-byte lines; 4 KiB pages; THP = `madvise`. Files: `results/2026-10-18-ryzen5500u-wsl2/environment.txt` and `results/2026-11-01-ryzen5500u-wsl2/environment.txt`.
- Matrices of `double`, uniform in [-1, 1], seed 12345. Each version is its own process.
- Timing: one warm-up, then the median (7 repetitions; 5 at n ≥ 1024). Allocation is outside the timed region.
- Counters: `perf stat` user-mode. The process also does setup and a reference multiply. We run with `LO = 1` and `HI = 1 + COUNTER_RUNS` repetitions and take `(HI − LO) / COUNTER_RUNS`. **Validity check:** `l1_loads_per_run` should be about `1.5 n³` for every version (this counter is per instruction and includes stores; SSE2 moves 2 doubles). Under WSL2 use `COUNTER_RUNS ≥ 30` for n ≤ 512; 3 runs is too noisy (can even go negative).
- On this CPU, checked equal to the raw event codes (`results/2026-11-01-ryzen5500u-wsl2/perf-event-mapping.txt`):

| `perf` name             | Raw     | Meaning on Zen 2                                                |
| ----------------------- | ------- | --------------------------------------------------------------- |
| `L1-dcache-loads`       | `r0040` | L1 data accesses (loads and stores), per instruction            |
| `L1-dcache-load-misses` | `rc860` | L1D → L2 requests, **including prefetch and stores**            |
| `cache-references`      | `rff60` | all L2 requests                                                 |
| `cache-misses`          | `r0964` | L2 misses (data + instruction fetch), **excluding L2 prefetch** |
| `dTLB-loads`            | `rff45` | L1 DTLB misses                                                  |
| `dTLB-load-misses`      | `rf045` | L2 DTLB misses / page walks                                     |

On Intel, `cache-misses` means LLC misses. That is **not** what we have. WSL2 has no L3 / DRAM counters.

- Alignment: four `std::vector<double>` allocations at n ≥ 250 all sat at `address % 64 = 16` and `address % 4096 = 16` (page + 16 bytes).

---

## Results

Two sessions on the same laptop. Absolute times move with power plan and other programs; **ratios and miss counts** repeat. Use 2026-11-01 for theory comparisons (more sizes, 30-run counters). Keep 2026-10-18 for n = 64 / 128 and the first no-vectorisation at n = 512.

### 2026-10-18 — first measurements

`results/2026-10-18-ryzen5500u-wsl2/`

|    n | naive (ms) | row_wise (ms) | tiled (ms) | naive / row_wise | row_wise / tiled |
| ---: | ---------: | ------------: | ---------: | ---------------: | ---------------: |
|   64 |      0.136 |         0.052 |      0.058 |             2.6× |             0.9× |
|  128 |       2.20 |          0.41 |       0.48 |             5.4× |             0.9× |
|  256 |       38.2 |          4.06 |       4.01 |             9.4× |             1.0× |
|  512 |        832 |          34.0 |       36.4 |            24.5× |             0.9× |
| 1024 |       8630 |           742 |        369 |            11.6× |             2.0× |

Counters then used 3 measured runs and no TLB columns. They already showed the shape (naive L1 miss rate 60–65% vs ~8% for `row_wise`; naive L2 misses ~n³ at 512 and 1024) but some load counts were off `1.5 n³`. The “over 100× last-level misses” sentence in the old conclusions was wrong: those numbers are **L2** misses.

No-vectorisation at n = 512: `row_wise` 56.0 ms vs `naive` 799 ms (**14×**). That 14× is real for this n, but n = 512 is the conflict-miss case. See 2026-11-01 at n = 500 for the number without that extra factor.

### 2026-11-01 — timings

`results/2026-11-01-ryzen5500u-wsl2/timings.csv` and `large-n/timings.csv`

|    n | naive (ms) | row_wise (ms) | tiled d=32 (ms) |   GFLOPS n / r / t | naive / row_wise | row_wise / tiled |
| ---: | ---------: | ------------: | --------------: | -----------------: | ---------------: | ---------------: |
|  250 |       19.5 |          6.02 |            7.18 | 1.61 / 5.19 / 4.35 |             3.2× |             0.8× |
|  256 |       63.0 |          6.71 |            6.22 | 0.53 / 5.00 / 5.39 |             9.4× |             1.1× |
|  400 |       83.2 |          26.3 |            26.8 | 1.54 / 4.86 / 4.78 |             3.2× |             1.0× |
|  500 |        169 |          50.1 |            43.4 | 1.48 / 4.99 / 5.76 |             3.4× |             1.2× |
|  512 |        976 |          40.1 |            38.7 | 0.28 / 6.69 / 6.94 |            24.3× |             1.0× |
| 1000 |       1724 |           728 |             315 | 1.16 / 2.75 / 6.36 |             2.4× |             2.3× |
| 1024 |       9650 |           788 |             384 | 0.22 / 2.73 / 5.60 |            12.2× |             2.1× |

Same ratios as Oct 18 at the shared sizes. New information: n = 250/400/500 are only ~3×, and n = 1000 `naive` is 5.6× faster than n = 1024.

### 2026-11-01 — L1 misses versus the formulas

`cache-counters.csv` (30 runs) and `large-n/cache-counters.csv` (10 runs). All `l1_loads_per_run` values are within 5% of `1.5 n³` except `naive` at n = 1024 (1.25×; still usable). A few TLB cells went negative (WSL noise on small counts); those are ignored.

L1 formulas used below: `row_wise` = `n³/L`; `naive` = `n³/L` at n = 250 (column fits), `n³` otherwise; `tiled` = `2 n³ /(d L)` with d = 32; lower bound = `2 n³ /(L √Z)` with Z = 4096.

|    n | naive meas. |                         vs formula | row_wise meas. | vs `n³/L` | tiled meas. | vs `2n³/(dL)` |
| ---: | ----------: | ---------------------------------: | -------------: | --------: | ----------: | ------------: |
|  250 |      3.08 M |                    1.58 × (`n³/L`) |         1.93 M |     0.99× |      0.65 M |          5.3× |
|  256 |      17.2 M |                        1.02 × `n³` |         2.14 M |     1.02× |      4.65 M |           35× |
|  400 |      68.8 M |                        1.07 × `n³` |         8.18 M |     1.02× |      2.16 M |          4.3× |
|  500 |       114 M |                        0.91 × `n³` |         16.0 M |     1.02× |      4.91 M |          5.0× |
|  512 |       139 M |                        1.04 × `n³` |         17.2 M |     1.02× |      39.7 M |           38× |
| 1000 |      1128 M | 1.13 × `n³` (= 1.00 × `n³(1+1/L)`) |          129 M |     1.03× |      42.3 M |          5.4× |
| 1024 |      1171 M |                        1.09 × `n³` |          144 M |     1.07× |       317 M |           38× |

`row_wise` **is** the formula. The +1–7% is the extra line from the 16-byte allocation offset.

`naive` is `n³` whenever the column does not fit in L1 **or** collides in a few sets. At n = 1000 the extra 13% matches the LRU form `n³(1+1/L)` (A misses too). At n = 250 the column spreads over many sets and 250 lines < 512, so we get the `n³/L` regime; the remaining 1.58× is alignment, counted prefetches, and some set pressure.

`tiled` at non-power-of-two n is 4–5× the ideal (5/4 from alignment, the rest from counted prefetches and leftover set pressure). At power-of-two n it is ~38× the ideal — **conflict**, not a wrong formula. The 32 rows of a B tile are `n×8` bytes apart; at n = 256/512/1024 that lands them in 1–2 L1 sets with only 8 ways.

Ratio to the L1 lower bound at n = 1000: `naive` 289× (theory 256), `row_wise` 33× (theory 32), `tiled` measured 11× (ideal would be 2). We are not yet at the bound; a cache-oblivious or conflict-avoiding layout is the way to close the gap.

### Why `naive` collapses at n = 256, 512, 1024

L1 set index = `(address / 64) mod 64` (address bits 6–11). A step of 4096 bytes leaves those bits unchanged.

|    n | Bytes per row | L1 sets used by one B column |                 Lines that set(s) can hold | Lines the column needs |
| ---: | ------------: | ---------------------------: | -----------------------------------------: | ---------------------: |
|  250 |          2000 |       many (step 31–32 sets) |                                  up to 512 |                    250 |
|  256 |          2048 |                            2 |                                         16 |                    256 |
|  400 |          3200 |                           32 |                                        256 |                    400 |
|  500 |          4000 |                         many | 512 (capacity already short: 500+63 > 512) |                    500 |
|  512 |          4096 |                        **1** |                                          8 |                    512 |
| 1000 |          8000 |                     64 (all) |                                        512 |                   1000 |
| 1024 |          8192 |                        **1** |                                          8 |                   1024 |

L2, for a 4096-byte stride, can use only 16 of 1024 sets (128 lines) because bits 6–11 stay fixed and only the physical page number varies. So at n = 512 and 1024 the column does not fit in L2 either:

|    n | naive L2 misses (`cache-misses`) | Comment                                |
| ---: | -------------------------------: | -------------------------------------- |
|  250 |                           0.42 M | column fits in L2; close to compulsory |
|  256 |                           0.58 M | L2 still mostly hits                   |
|  400 |                           0.39 M | 32 L1 sets fail, but L2 has room       |
|  500 |                           1.48 M |                                        |
|  512 |                   **136 M ≈ n³** | L2 thrashes with the column            |
| 1000 |                             77 M | B = 8 MB > L2; ~0.6 × `n³/L`           |
| 1024 |                  **1089 M ≈ n³** | 8 L2 sets vs 1024 lines                |

That is the exact reason n = 1024 `naive` takes 9.7 s and n = 1000 takes 1.7 s.

### Why `tiled` wins at n = 1000 / 1024 (L3 / RAM)

L3 and DRAM counters do not exist in this WSL2. Timing is the evidence.

`l3-sweep/timings.csv` — `row_wise` vs `tiled` (d = 32):

|    n |  B size | row_wise GFLOPS | tiled GFLOPS | tiled / row_wise |
| ---: | ------: | --------------: | -----------: | ---------------: |
|  512 | 2.0 MiB |            6.69 |         6.94 |             1.0× |
|  600 | 2.9 MiB |            5.34 |         6.85 |             1.3× |
|  650 | 3.4 MiB |            4.28 |         5.56 |             1.3× |
|  700 | 3.9 MiB |            3.54 |         6.09 |             1.7× |
|  800 | 5.1 MiB |            3.52 |         6.19 |             1.8× |
|  900 | 6.4 MiB |            2.85 |         6.11 |             2.1× |
| 1000 | 7.6 MiB |            2.58 |         6.12 |             2.4× |

The drop in `row_wise` starts around n = 600 and is **gradual**, not a step at n = 724 (`√(4 MiB / 8)`). That matches a victim L3 that is also shared and that A and C pass through: the useful capacity for B is less than 4 MiB.

Bytes `row_wise` must read from wherever B lives: `n × n² × 8` = `8 n³` bytes of B (plus A and C once). At n = 1024 that is 8.6 GB of B in 788 ms ≈ **10.9 GB/s** (Oct 18: 11.6 GB/s in 742 ms). One core streaming from RAM. Tiling reduces how often B is read from that far away; L1 misses can go up (and do) while wall time goes down.

### Tile-size sweep (n = 1000)

`tile-sweep/d*/`

|      d |      ms |   GFLOPS | L1 misses | L2 demand misses | Fits in L1? (`3 d² ≤ 4096`)                            |
| -----: | ------: | -------: | --------: | ---------------: | ------------------------------------------------------ |
|      8 |     549 |     3.65 |      98 M |             48 M | yes, but `2n³/(dL)` is large and loop overhead is high |
|     16 |     402 |     4.98 |      40 M |             28 M | yes                                                    |
| **32** | **306** | **6.53** |  **38 M** |             11 M | yes, near `d* ≈ 37`                                    |
|     64 |     333 |     6.01 |     210 M |            5.7 M | **no** (12 288 > 4096) — L1 behaves like `row_wise`    |
|    128 |     337 |     5.94 |     170 M |            2.8 M | no — still fits in L2 (384 KiB < 512 KiB)              |

U-shape in time, minimum at d = 32, as predicted. L2 demand misses keep falling as d grows (better L2 reuse); that no longer helps once L1 is lost.

### TLB

|    n | version  | L1 DTLB misses | page walks |
| ---: | -------- | -------------: | ---------: |
|  512 | naive    |     135 M ≈ n³ |     1.18 M |
|  512 | row_wise |        (noise) |       ~5 k |
|  512 | tiled    |         0.58 M |        8 k |
| 1000 | naive    |    1007 M ≈ n³ |      3.2 M |
| 1000 | row_wise |          2.0 M |     0.85 M |
| 1024 | naive    |    1047 M ≈ n³ |  **114 M** |
| 1024 | row_wise |          2.3 M |      4.7 M |

`naive` at n = 512: each column step is exactly one page, 512 pages > 64 L1-TLB entries, so almost every B access misses the L1 TLB. The L2 TLB (2048) still holds 3 × 512 = 1536 pages, so walks stay in the millions, not the hundreds of millions. At n = 1024, B alone is 2048 pages and three matrices are 6144 > 2048: the L2 TLB overflows and we pay 114 M walks. That is a second reason n = 1024 `naive` is so slow, on top of L1/L2 conflict.

### Vectorisation (n = 500, 2026-11-01)

`no-vectorization-500.csv`. Release vs `-fno-tree-vectorize -fno-tree-slp-vectorize`. The binary uses SSE2 (`mulpd` on xmm), not AVX2/FMA (`-O3` without `-march=native`).

| Version  | With SSE2 (ms) | Without (ms) |                                          SIMD factor |
| -------- | -------------: | -----------: | ---------------------------------------------------: |
| naive    |            169 |          136 | ~1× (no inner-loop vectorisation of the column walk) |
| row_wise |           50.1 |         60.4 |                                                1.21× |
| tiled    |           43.4 |         54.2 |                                                1.25× |

Without SIMD, `row_wise` is still **2.3×** faster than `naive` (136 / 60). Access order is the cause. Use this number, not the 14× at n = 512, when talking about “how much is cache vs SIMD”.

---

## Conclusions

1. The miss formulas work where the model’s assumptions hold. `row_wise` L1 misses are `n³/L` at every n we measured. `naive` is `n³/L` only when the B column fits in L1 without conflicts (n = 250 here); otherwise it is `n³`.
2. The lower bound `2 n³ / (L √Z)` is the target, not a measurement. On L1, `row_wise` is ~32× above it and our tiled code is ~2× above it in the ideal (conflict-free) case, ~11× above it in the n = 1000 measurement.
3. Of the three regimes, we live in (b) on L1 for n ≥ 64. Regime (a) is n = 64 on L1 / n ≤ 256 on L2 / n ≤ 600-ish on L3. Regime (c) needs n > 4096 on L1 or a simulator. Inside (b), power-of-two n is a different machine from n = 250/400/500 because of set mapping.
4. Tiling’s job is the L3/RAM regime: 2.3× at n = 1000, 2.1× at n = 1024, best d = 32. L1 counters cannot show that win; they were never going to.
5. `cache-misses` on this CPU is L2. Saying “last-level” was a mistake.

## Limitations and open questions

- WSL2: noisy counters (need many runs), no L3/DRAM events, 4 of 12 threads visible.
- `tiled` at non-power-of-two n is still 4–5× the ideal L1 count. Alignment explains 1.25×; the rest is not isolated (prefetch in the L1 counter, residual conflicts).
- Only one machine, one compiler, `double`, one thread. No n = 2048 (`naive` reference check is several minutes).
- Not yet implemented: transposed B (professor’s (b) as storage), cache-oblivious recursion, a padded / copied layout that kills the 4096-byte conflict, a cache simulator for regime (c).
