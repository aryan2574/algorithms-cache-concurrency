# Findings

Half a page per experiment. Full tables, figures and method: the experiment's own README. Agenda and professor tasks: [agenda.md](agenda.md).

---

## 01 — Matrix multiplication

**Report:** [experiments/01-matrix-multiplication/README.md](../experiments/01-matrix-multiplication/README.md) · **Theory:** [theory/caches.md](theory/caches.md) · **Data:** `results/2026-10-18-…`, `2026-11-01-…`, `2026-11-14-…-run2/`

**Question.** How much does column-wise vs row-wise access cost in `C = A * B`, and can tiling (cache-aware) and recursion (cache-oblivious) fix it when the data leaves the cache? Three storage layouts: row-major, column-major, tile-wise.

**Results.**

- **Access order.** `row_wise` is 2.4–3.4× faster than `naive` at ordinary sizes, and **9–24×** at powers of two (n = 256 / 512 / 1024) because a whole column of B then maps to 1–2 L1 sets. Without SIMD at n = 500 the gap is still **2.3×**; vectorisation adds about 1.2×.
- **Counters match the formulas.** `row_wise` L1 misses = `n³/8` within 1–7%. `naive` ≈ `n³` once the column does not fit or collides. On this CPU `perf` `cache-misses` counts **L2** misses, not last-level.
- **Tiling.** No gain up to n = 512. From ~n = 600 (B leaves usable L3) `tiled` is **1.3–2.4×** faster than `row_wise`. Best tile at n = 1024 / 2048 is **T = 128** (U-shaped curve); T = 4 is up to 5.3× *slower* than no tiling. A tile larger than L3 (T = 512) can be worse than plain loops on row-major.
- **Layouts and oblivious.** Cache-oblivious matches tuned cache-aware within ~7% (noise) on every layout, with no tile size to choose. Fastest at n = 2048: **oblivious + tile-wise**, 1819 ms vs 4905 ms for `row_wise` (**2.7×**). Column-major mirrors row-major for plain loops (within 2%).
- **Regimes.** (a) and (b) shown at every cache level. (c) "cache < single row" on L1 needs n > 4096 — only partly measured at n = 4096; expected extra slowdown of `row_wise` **not** seen.

**Limits.** WSL2: noisy counters, no L3/DRAM events. Why tile-wise wins stays a hypothesis (counter run stopped). One machine, one thread, `double`, medians only. Differences under ~10% unreliable.

### Corrected since October

| Old claim | Correction |
| --- | --- |
| `cache-misses` = last-level / LLC | **L2** misses on Zen 2 |
| "10–25× for n ≥ 256" | only at **powers of two**; nearby sizes ~3× |
| "14× without SIMD is the memory effect" | true at n = 512 (conflicts); **2.3×** at n = 500 |
| "hardware counts only demand misses" | L2 event yes; **L1 includes prefetch** |
| "counters do not explain tiled at n = 1024" | L1 counters *should not*; win is L3/RAM reuse (GFLOPS sweep) |
| "best tile T = 128" as general | power-of-two sizes; at n = 1000 best was **d = 32** (~10% gap, near noise) |

---

## 02 — Merge sort

Not started. Placeholder: [experiments/02-merge-sort/README.md](../experiments/02-merge-sort/README.md).
