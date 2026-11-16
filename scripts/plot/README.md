# Figures (Python + matplotlib)

Turns the CSV files of a results folder into charts for the thesis report. It only reads the CSV and `environment.txt` files; it does not run any benchmark. What each figure shows is explained next to it in the experiment README (for example [experiments/01-matrix-multiplication/README.md](../../experiments/01-matrix-multiplication/README.md)).

## Set up (once)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scripts/plot/requirements.txt
```

On Linux / WSL: `python3 -m venv .venv && .venv/bin/pip install -r scripts/plot/requirements.txt`. `.venv/` is git-ignored.

## Use

```powershell
.\.venv\Scripts\python.exe scripts/plot/make_figures.py experiments/01-matrix-multiplication/results/2026-11-14-ryzen5500u-wsl2-run2
.\.venv\Scripts\python.exe scripts/plot/make_figures.py experiments/01-matrix-multiplication/results   # every session
.\.venv\Scripts\python.exe scripts/plot/make_figures.py <folder> --only overview_ranking tile_size_vs_time
.\.venv\Scripts\python.exe scripts/plot/make_figures.py --diagrams
.\.venv\Scripts\python.exe scripts/plot/make_figures.py --list
```

Figures go to `docs/<experiment>/figures/<session>/` as `.pdf` (vector) and `.png`. A figure whose CSV tables are missing is skipped. Sub-folders of a session (for example `large-n/`, `l3-sweep/`) are loaded as `"<sub-folder>/<stem>"`.

## Figures for experiment 01

| Name | Needs | Shows |
|---|---|---|
| `overview_baseline` | `timings` | naive, row_wise, tiled against size |
| `access_power_of_two` | `timings` (+ `large-n/timings`) | power-of-two vs other sizes |
| `overview_ranking` | `oblivious` | all versions ranked at large n |
| `overview_gflops_vs_n` | `oblivious` | best of each version against n |
| `tile_size_vs_time` | `tile-sweep` | time against tile size |
| `tile_fit_regimes` | `tile-sweep` | GFLOPS vs memory of the three tiles |
| `tile_l3_sweep` | `l3-sweep/timings` | where tiling starts to pay off |
| `oblivious_vs_aware` | `oblivious` | best aware / best oblivious |
| `transpose_vs_n` | `transpose` | naive vs best tiled vs best recursive transpose |
| `transpose_cache_misses` | `cache-counters` | L1/L2 counters for transpose versions |
| `transposed_b_vs_row_wise` | `timings` | A×Bᵀ (ijk ± tiled) vs row_wise / tiled |
| `cache_misses` | `cache-counters` | L1 miss rate, L1 misses/FMA, L2 misses (`perf` cache-misses) |
| `simd_vectorization` | `timings` + `no-vectorization` | with / without auto-vectorisation |
| `quality_noise_check` | `tile-sweep` + `oblivious` | same configuration measured twice |
| `memory_layouts`, `recursion_steps` | (diagrams) | layouts and the recursive split |

Colour = layout (blue row-major, orange column-major, green tile-wise); line style = algorithm (dotted plain, solid aware, dashed oblivious). Grey band = ±10% noise. Speed-ups use the `row_wise` row of the same CSV.

## Figures for experiment 02

| Name | Needs | Shows |
|---|---|---|
| `overview_time_vs_n` | `timings` | recursive vs iterative time against n |
| `ratio_vs_n` | `timings` | iterative/recursive time ratio against n |
| `throughput_vs_n` | `timings` | million elements/s against n |
| `cache_misses` | `cache-counters` | L1 miss rate and L2 misses |
| `misses_per_element` | `cache-counters` | L2 misses per element |
| `l1_loads` | `cache-counters` | L1 loads per element (sanity) |
| `bottom_up_passes` | (diagram) | iterative full-array passes vs recursive locality |

Blue dashed = recursive, vermillion solid = iterative. Grey band on the ratio plot = ±10% noise. Vertical dotted lines = working set (`16n` bytes) vs L1 / L2 / L3.

## Code layout

```text
scripts/plot/
├── make_figures.py
├── requirements.txt
└── plotlib/
    ├── data.py            CSV + environment.txt (Machine, Run, best_per_group)
    ├── style.py           colours, labels, save() with footnote
    ├── experiment01.py    one function per figure
    ├── experiment02.py    merge-sort figures
    └── diagrams.py
```

New figure of experiment 01: add `fig_…` in `experiment01.py` and an entry in `FIGURES`. New experiment: add `plotlib/experimentNN.py` with its own `FIGURES`, register it in `make_figures.py`. Keep figures computed from the data; do not type numbers in by hand.
