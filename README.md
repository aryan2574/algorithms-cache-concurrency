# Algorithm Optimisation, Cache Behaviour and Concurrency

Master's thesis experiments in C++20. Each experiment asks how memory layout and access order affect a classical algorithm, and whether cache-aware or cache-oblivious designs help.

## Start here

1. **[docs/agenda.md](docs/agenda.md)** — thesis question, experiment table, professor tasks by date, open items.
2. **[docs/findings.md](docs/findings.md)** — half a page of results per experiment (and corrections to earlier claims).
3. The experiment report — for 01: [experiments/01-matrix-multiplication/README.md](experiments/01-matrix-multiplication/README.md).

Hardware background (caches, TLB, what `perf` counts on this CPU): [docs/theory/caches.md](docs/theory/caches.md).

## Repository map

```text
docs/
├── agenda.md                 # start here
├── findings.md               # results, short
├── theory/caches.md          # shared cache theory
└── 01-matrix-multiplication/ # generated figures and diagrams
experiments/
├── 01-matrix-multiplication/ # report, code, benchmark.conf, notes/, results/
└── 02-merge-sort/            # recursive vs iterative mergesort
scripts/                      # shared measurement + figure tooling
```

- One fact in one place: agenda for tasks, findings for the short answer, the experiment README for the full report, `notes/` for the lab notebook of that day.
- Figures live under `docs/<experiment>/figures/<session>/` (PDF + PNG); raw CSV under `experiments/<experiment>/results/<date>-<machine>/`.

## Experiments

| # | Experiment | Status | Report |
|---|---|---|---|
| 01 | Matrix multiplication (+ transpose) | done | [README](experiments/01-matrix-multiplication/README.md) · [findings](docs/findings.md) |
| 02 | Merge sort (recursive vs iterative) | done | [README](experiments/02-merge-sort/README.md) · [findings](docs/findings.md) |

## Build and run

Requirements: Git, CMake ≥ 3.20, a C++20 compiler (GCC / Clang / MSVC). On Ubuntu or WSL: `sudo apt install build-essential cmake git`.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
./build/experiments/01-matrix-multiplication/matrix_multiplication row_wise 512
./build/experiments/02-merge-sort/merge_sort recursive 65536
```

On Visual Studio (multi-config): `cmake -S . -B build` then `cmake --build build --config Release --parallel`. Use a Release build for timings (Debug is ~35× slower here).

Measure on Linux / WSL with the shared scripts ([scripts/README.md](scripts/README.md)):

```bash
bash scripts/run.sh experiments/01-matrix-multiplication            # default checks
bash scripts/run.sh experiments/02-merge-sort environment timings cache_counters
bash scripts/run.sh --list
```

Figures from a results folder ([scripts/plot/README.md](scripts/plot/README.md)):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scripts/plot/requirements.txt
.\.venv\Scripts\python.exe scripts/plot/make_figures.py experiments/01-matrix-multiplication/results/2026-11-14-ryzen5500u-wsl2-run2
.\.venv\Scripts\python.exe scripts/plot/make_figures.py experiments/02-merge-sort/results/<session>
```

## Add an experiment

1. Create `experiments/NN-name/` with `CMakeLists.txt`, program, `README.md`, `benchmark.conf`, and empty `notes/` + `results/`.
2. Follow the program contract in [scripts/README.md](scripts/README.md) (`<variant> <size> <repetitions>` in, CSV out).
3. Register it in the root `CMakeLists.txt` with `add_subdirectory(...)`.
4. Add a row to [docs/agenda.md](docs/agenda.md) and a short entry in [docs/findings.md](docs/findings.md).
