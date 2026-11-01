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
| `cache_counters` | `cache-counters.csv` | L1 and last-level cache counters per run, via `perf` (skipped if unavailable) |
| `no_vectorization` | `no-vectorization-<n>.csv` | same timings with SIMD auto-vectorisation off, to separate memory effects from SIMD |

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
    └── no_vectorization.sh
```

## What an experiment must provide

1. A `benchmark.conf` in its directory (see [`experiments/01-matrix-multiplication/benchmark.conf`](../experiments/01-matrix-multiplication/benchmark.conf)). It is plain bash. Required settings:
   - `TARGET`: the CMake target name
   - `VARIANTS`: the versions to compare, space separated
   - `SIZES`: the problem sizes

   Optional: `REPS`, `REPS_LARGE`, `LARGE_FROM`, `EXTRA_ARGS`, `COUNTER_SIZES` (empty skips `cache_counters`), `NOVEC_SIZE` (empty skips `no_vectorization`). Write optional settings as `: "${NAME:=value}"` so they can be overridden from the command line.
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

To run the new check by default, add its name to `DEFAULT_CHECKS` in `run.sh`. Ideas for later: a tile-size sweep, a thread-scaling check, a memory-usage check.

## Line endings

The `.sh` and `.conf` files must use Unix line endings (`LF`), or bash fails with strange errors. `.gitattributes` enforces this in the repository. If you edit them on Windows, check that your editor keeps `LF`.
