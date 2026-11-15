# Figures (Python + matplotlib)

Turns the CSV files of a results folder into charts for the thesis report and for presentations. It only reads the CSV and `environment.txt` files; it does not run any benchmark.

## Set up (once)

From the repository root, on Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scripts/plot/requirements.txt
```

On Linux / WSL:

```bash
python3 -m venv .venv && .venv/bin/pip install -r scripts/plot/requirements.txt
```

`.venv/` is git-ignored.

## Use

```powershell
# all figures that can be made from a results folder
.\.venv\Scripts\python.exe scripts/plot/make_figures.py experiments/01-matrix-multiplication/results/2026-11-14-ryzen5500u-wsl2-run2

# all sessions of an experiment at once
.\.venv\Scripts\python.exe scripts/plot/make_figures.py experiments/01-matrix-multiplication/results

# only some figures, other formats, other output folder
.\.venv\Scripts\python.exe scripts/plot/make_figures.py <results folder> --only overview_ranking tile_size_vs_time --formats pdf png svg --out my-figures

# conceptual diagrams (memory layouts, recursion), written to docs/<experiment>/diagrams/
.\.venv\Scripts\python.exe scripts/plot/make_figures.py --diagrams

# what figures exist
.\.venv\Scripts\python.exe scripts/plot/make_figures.py --list
```

The command works from any directory: a relative path is looked up from the current directory and then from the repository root. If you pass the `results/` folder of an experiment instead of one session, every session inside it is processed (`--out` is not allowed then). From WSL you can use the same Windows Python, for example `python.exe plot/make_figures.py experiments/01-matrix-multiplication/results/` when you are inside `scripts/`.

Figures go to `docs/<experiment>/figures/<session>/` (for example `docs/01-matrix-multiplication/figures/2026-11-14-ryzen5500u-wsl2-run2/`) as vector `.pdf` (for LaTeX / Word) and `.png` (for slides). Results folders contain only data. Each experiment's folder in `docs/` has a README that explains every figure; update it when you add a figure. A figure whose input table is missing in that folder is skipped, so you can run the tool on any folder, also on a partial one.

The experiment is detected from the path (`experiments/<experiment>/results/<session>`); use `--experiment` if the folder lives elsewhere.

## Figures for experiment 01

| Name | Needs | Shows |
|---|---|---|
The names start with the topic, so the files sort by topic. What each figure means and how to explain it: [docs/01-matrix-multiplication/README.md](../../docs/01-matrix-multiplication/README.md).

| Name | Needs | Shows |
|---|---|---|
| `overview_ranking` | `oblivious.csv` | all versions ranked by time at n = 1024 and 2048, each with its best parameter |
| `overview_gflops_vs_n` | `oblivious.csv` | best result of each version (3 layouts × plain / aware / oblivious) against matrix size |
| `overview_time_vs_n` | `oblivious.csv` | the same as time on log-log axes, with the n^3 growth as a guide |
| `overview_speedup_bars` | `oblivious.csv` | best aware vs best oblivious vs plain loops per layout, with the parameter used |
| `overview_baseline` | `timings.csv` | naive, row_wise, tiled against size (October session) |
| `layout_algorithms` | `oblivious.csv` | one panel per layout, plain / aware / oblivious at every parameter against n |
| `layout_comparison` | `oblivious.csv` | the three layouts side by side for each kind of algorithm |
| `layout_tile_wise_vs_row_major` | `tile-sweep.csv` | ratio tile-wise / row-major for the same loops and tile size, with the +-10 % noise band |
| `tile_size_vs_time` | `tile-sweep.csv` | time against tile size, one panel per matrix size, row-major vs tile-wise, markers where 3 tiles = L1 / L2 / L3 |
| `tile_fit_regimes` | `tile-sweep.csv` | GFLOPS against the memory of the three tiles, shaded by the cache level they fit |
| `tile_speedup_heatmap` | `tile-sweep.csv` | speed-up over `row_wise` for every size × tile size, both layouts |
| `oblivious_parameter` | `oblivious.csv` | how sensitive aware and oblivious are to tile size / recursion base |
| `oblivious_vs_aware` | `oblivious.csv` | best aware time / best oblivious time per layout and size |
| `cache_misses` | `cache-counters.csv` | L1 miss rate, L1 misses per multiply-add, last-level misses; shows every version found in the file |
| `cache_misses_vs_speed` | `cache-counters.csv` + `timings.csv` | GFLOPS against the counters, one point per version and size |
| `simd_vectorization` | `timings.csv` + `no-vectorization-512.csv` | effect of switching off auto-vectorisation |
| `quality_noise_check` | `tile-sweep.csv` + `oblivious.csv` | the same configuration measured twice in one session: how repeatable the numbers are |
| `memory_layouts` (diagram) | none | which elements share a cache line in the three layouts, computed from the same index formulas as `main.cpp` |
| `recursion_steps` (diagram) | none | how the cache-oblivious recursion halves i, j and k |

## Reading the figures

- Colour is the layout (blue row-major, orange column-major, green tile-wise), the line style / hatching is the algorithm (dotted plain loops, solid cache-aware, dashed / hatched cache-oblivious). Same meaning in every figure.
- Every figure has a footnote with CPU, caches, compiler and the results folder, read from `environment.txt`.
- The grey band marks +-10 %. The repeated `row_wise` measurements in one run differ by 3-7 %, so differences inside the band are not reliable. n = 256 is unreliable in general (a run lasts only a few ms).
- Speed-ups here are against the `row_wise` row **of the same CSV file**. `14-nov.txt` uses the `row_wise` baseline of the tile sweep, so a ratio can differ by about 0.1 (for example 2.1x here, 2.2x there). Both are inside the noise.
- The figures show medians of 7 repetitions without error bars (the C++ program only prints the median). Recording min / max of the repetitions in the C++ output as well would allow error bars; this is not done yet.

## Code layout

```text
scripts/plot/
├── make_figures.py        command line, finds the experiment, runs the figure functions
├── requirements.txt
└── plotlib/
    ├── data.py            reads CSV + environment.txt (Machine, Run, best_per_group)
    ├── style.py           colours, line styles, labels, save() with footnote
    ├── experiment01.py    one function per figure of experiment 01
    └── diagrams.py        conceptual diagrams (no data needed)
```

## Add a figure or an experiment

- New figure of experiment 01: write `def fig_my_figure(run) -> Figure` in `experiment01.py` (use the tables and machine info of `run`, and `style.style_for(version)`), then add `"my_figure": (fig_my_figure, ["tile-sweep"])` to the `FIGURES` dict at the bottom of the file (the list names the CSV tables the figure needs). Raise `data.NotApplicable` if the data cannot support it.
- New experiment: add `plotlib/experiment02.py` with its own `FIGURES` dict (and a `DIAGRAMS` dict, possibly empty), register it in `EXPERIMENTS` in `make_figures.py`, and add `docs/<new experiment>/README.md` that explains the figures. If its CSV has other columns, add a table to `load_run` in `data.py`.
- Keep figures computed from the data. Do not type numbers into a figure by hand.
