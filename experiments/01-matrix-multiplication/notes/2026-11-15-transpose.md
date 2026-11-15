# 2026-11-15: matrix transposition (+ counters) and multiply with B transposed

## Professor tasks covered today

1. Transposition `A → Aᵀ` (exact wording in [docs/agenda.md](../../../docs/agenda.md)): nested loops vs recursive; measure at large n because O(n²).
2. Professor case b literally: row-major A × column-major / transposed B — not only via `row_wise` loop order, but by storing Bᵀ and using ijk (`transposed_b`) and its tiled form (`tiled_transposed_b`).

## Sessions

| Folder | Contents |
| --- | --- |
| `results/2026-11-15-ryzen5500u-wsl2-transpose/` | timings n = 1024…8192 |
| `results/2026-11-15-ryzen5500u-wsl2-transpose-counters/` | perf counters n = 1024…4096 (T/base = 16 and 32) |
| `results/2026-11-15-ryzen5500u-wsl2-transposed-b/` | multiply: naive / row_wise / transposed_b / tiled / tiled_transposed_b |

### CPU / wall-time limits (not skipped without reason)

- **Transpose counters at n = 8192:** not run. Under `perf`, each version is measured twice (1 and 1+R reps). At n = 8192 one naive transpose is already ~4 s; a full counter sweep would be many minutes for little extra signal beyond n = 4096. **Limit: CPU time of this laptop (Ryzen 5 5500U, one thread), not a missing algorithm.**
- **`naive` multiply at n = 2048** in the transposed-b session: skipped. O(n³); ~10 s median at n = 1024 already, ~1–2 min per repetition at n = 2048, and the default reference check is also naive. See `results/...-transposed-b/STOPPED.txt`. **Same CPU-time limit.** naive is present at n = 512 and 1024 in that folder.

## Transposition timings (best = base/T 16)

| n | naive | best tiled | best recursive | speed-up |
| --- | ---: | ---: | ---: | ---: |
| 1024 | 13.3 ms | 5.6 ms | **4.3 ms** | **3.1×** |
| 2048 | 152 ms | 25.9 ms | **25.4 ms** | **6.0×** |
| 4096 | 665 ms | 123 ms | **121 ms** | **5.5×** |
| 8192 | 4171 ms | 1293 ms | **1024 ms** | **4.1×** |

## Transposition counters (T/base = 16; L2 = perf `cache-misses` on Zen 2)

| n | naive L2 | tiled L2 | obl L2 | L2 reduction (obl) |
| --- | ---: | ---: | ---: | ---: |
| 1024 | 1.24 M | 0.29 M | **0.24 M** | **5.1×** |
| 2048 | 6.42 M | 1.53 M | **1.02 M** | **6.3×** |
| 4096 | 41.3 M | 7.04 M | **4.07 M** | **10.2×** |

L1 *miss rate* can look higher for tiled/oblivious; the absolute L2 miss count (and the wall time) is what matches the cache story. At T = 32 and n = 4096 the L2 counters collapse toward naive — same cliff as in the timings.

## Multiply with B transposed

Checksums match `row_wise` / `naive` at every measured size. Times (ms):

| n | naive | transposed_b | row_wise | tiled_transposed_b | tiled |
| --- | ---: | ---: | ---: | ---: | ---: |
| 512 | 907 | 112 | **37** | 68 | 40 |
| 1024 | 10469 | 1166 | 896 | 527 | **381** |
| 2048 | (skipped) | 9749 | 8149 | 4470 | **4271** |

- Storing Bᵀ + ijk beats naive a lot (cache-friendly k-stream), but loses to `row_wise` (ikj on row-major B): same traffic idea, better loop / SIMD shape without a layout change.
- Tiling on top of Bᵀ (`tiled_transposed_b`) nearly catches `tiled` at n = 2048 (~4% slower).

Figures: `transpose_vs_n`, `transpose_cache_misses`, `transposed_b_vs_row_wise` under `docs/01-matrix-multiplication/figures/`.
