# Benchmark scripts

Shared tooling that measures any experiment in `experiments/` in the same way, so results are comparable across experiments. Works on Linux and WSL (needs `bash`, `cmake`, a C++ compiler; `perf` is optional).

## Usage

```bash
bash scripts/run.sh <experiment> [check ...] [--out DIR]
bash scripts/run.sh --list
```

`<experiment>` is an experiment's `benchmark.conf`, or the experiment directory containing one. With no `check` arguments, all checks run.

```bash
# everything, for experiment 01
bash scripts/run.sh experiments/01-matrix-multiplication

# only timings
bash scripts/run.sh experiments/01-matrix-multiplication timings

# several checks, custom output folder
bash scripts/run.sh experiments/01-matrix-multiplication/benchmark.conf \
    environment cache_counters --out /tmp/my-run

# quick test run: override settings from benchmark.conf
SIZES="64 128" REPS=3 bash scripts/run.sh experiments/01-matrix-multiplication timings --out /tmp/quick
```

Results go to `<experiment>/results/<YYYY-MM-DD>-local/` unless `--out` is given. Rename that folder to `<date>-<machine>` (for example `2026-10-18-ryzen5500u-wsl2`) when you keep the results.

## Checks

| Check | Writes | What it does |
|---|---|---|
| `environment` | `environment.txt` | CPU, OS, compiler, flags, git commit, the experiment's parameters |
| `timings` | `timings.csv` | median runtime of every variant at every size |
| `cache_counters` | `cache-counters.csv` | Per-run L1 loads/misses, L2 refs/misses and dTLB loads/misses, via `perf` (skipped if unavailable). Columns: `n,algorithm,tile_size,runs_measured,l1_loads_per_run,l1_load_misses_per_run,l1_miss_rate_pct,cache_refs_per_run,cache_misses_per_run,dtlb_loads_per_run,dtlb_load_misses_per_run`. Generic names depend on the CPU: on AMD Zen 2 `cache-misses` is L2 misses; on Intel it is LLC misses. |
| `no_vectorization` | `no-vectorization-<n>.csv` | same timings with SIMD auto-vectorisation off, to separate memory effects from SIMD |
| `tile_sweep` | `tile-sweep.csv` | every version in `TILE_SWEEP_VERSIONS` (`tiled` row-major, `tiled_tile_wise` tile-wise layout, optionally `tiled_col_major`) at every tile size in `TILE_SIZES` and every size in `TILE_SWEEP_SIZES`, with a `row_wise` baseline per size. Tile-wise versions skip tile sizes that do not divide n. Not run by default: ask for it by name. Needs the program to accept `<variant> <size> <repetitions> <tile_size> <reference>`. Stops with an error if checksums differ. |

| `oblivious` | `oblivious.csv` | cache-aware and cache-oblivious versions on row-major, column-major and tile-wise layouts, with plain-loop baselines, at every size in `OBLIVIOUS_SIZES` and every parameter in `OBLIVIOUS_PARAMS` (tile size, or smallest recursion block). Not run by default. Same checksum check. Tile-wise versions need n to be a multiple of the tile size. |
| `transpose` | `transpose.csv` | out-of-place matrix transposition (`transpose_naive`, `transpose_tiled`, `transpose_oblivious`) at every size in `TRANSPOSE_SIZES` and every parameter in `TRANSPOSE_PARAMS`. Not run by default. Same checksum check. The sixth CSV column holds million elements/s (not GFLOPS). |

```bash
bash scripts/run.sh experiments/01-matrix-multiplication environment tile_sweep oblivious \
    --out experiments/01-matrix-multiplication/results/<date>-<machine>
```

## Layout

```text
scripts/
├── run.sh              entry point: parses arguments, loads the experiment, runs checks
├── lib/
│   └── common.sh       shared helpers (build, run a variant, load benchmark.conf)
└── checks/
    ├── environment.sh
    ├── timings.sh
    ├── cache_counters.sh
    ├── no_vectorization.sh
    ├── oblivious.sh
    └── tile_sweep.sh
```

Charts are made from the CSV files by a separate Python tool, see [plot/README.md](plot/README.md).

## What an experiment must provide

1. A `benchmark.conf` in its directory (see [`experiments/01-matrix-multiplication/benchmark.conf`](../experiments/01-matrix-multiplication/benchmark.conf)). It is plain bash. Required settings:
   - `TARGET`: the CMake target name
   - `VARIANTS`: the versions to compare, space separated
   - `SIZES`: the problem sizes

   Optional: `REPS`, `REPS_LARGE`, `LARGE_FROM`, `EXTRA_ARGS`, `COUNTER_SIZES` (empty skips `cache_counters`), `COUNTER_RUNS` (measured runs per counter row; default 3, use 30 or more under WSL2 for n <= 512), `COUNTER_VERSIONS`, `COUNTER_PARAMS`, `COUNTER_REFERENCE` (default `row_wise` / `transpose_naive` / `recursive` by version), `NOVEC_SIZE` (empty skips `no_vectorization`), `TILE_SIZES` (empty skips `tile_sweep`), `TILE_SWEEP_VERSIONS`, `TILE_SWEEP_SIZES`, `TILE_SWEEP_NAIVE_REFERENCE_MAX`, `OBLIVIOUS_PARAMS` (empty skips `oblivious`), `OBLIVIOUS_SIZES`, `TRANSPOSE_PARAMS`, `TRANSPOSE_SIZES` (empty skips `transpose`). Write optional settings as `: "${NAME:=value}"` so they can be overridden from the command line (`SIZES`, `VARIANTS`, `EXTRA_ARGS`, `COUNTER_RUNS`, ...). A check that a counter row is usable: `l1_loads_per_run` should be about `1.5 n^3` for the matrix-multiplication experiment.
2. A program (the CMake target) that follows this contract:
   - It is called as `<executable> <variant> <size> <repetitions> [EXTRA_ARGS...]`.
   - It prints a CSV header line, then one result row, to **stdout**. Progress and error messages go to **stderr**.
   - It exits with status 0 on success and non-zero on failure.
   - For the `cache_counters` check, the work outside the timed repetitions (setup, correctness check) must not depend on the repetition count.
3. The target built by the root `CMakeLists.txt` (`add_subdirectory(experiments/NN-name)`), with the experiment directory laid out as the build directory mirrors it (the scripts expect the binary at `build/<experiment dir name>-release/experiments/<experiment dir name>/<TARGET>`, which CMake does by default).

## Adding a new check

Create `scripts/checks/<name>.sh` that defines a function `check_<name>`. That is all: `run.sh` finds it automatically (`--list` shows it). Inside it you can use:

- `ensure_release_build` (sets `RELEASE_EXE`), `ensure_novec_build` (sets `NOVEC_EXE`)
- `run_variant <exe> <variant> <size> <repetitions>`
- `$OUT_DIR` (where to write), `$TMP_DIR` (scratch space), `log`, `warn`, `die`
- everything from the experiment's `benchmark.conf` (`$VARIANTS`, `$SIZES`, ...)

To run the new check by default, add its name to `DEFAULT_CHECKS` in `run.sh`. Ideas for later: a thread-scaling check, a memory-usage check.

## Line endings

The `.sh` and `.conf` files must use Unix line endings (`LF`), or bash fails with strange errors. `.gitattributes` enforces this in the repository. If you edit them on Windows, check that your editor keeps `LF`.
