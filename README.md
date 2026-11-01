# Algorithm Optimisation, Cache Behaviour and Concurrency

This repository contains the C++ implementations and experiments developed for my master's thesis. The work explores algorithm optimisation, data structures, memory-access patterns, cache locality, and—where relevant—concurrency.

The aim is to make each experiment straightforward to build, run, measure, and reproduce. Because performance depends on the hardware, operating system, compiler, build configuration, and input data, these details should be recorded with every set of results.

## Research scope

Experiments will be added incrementally as the thesis progresses. Each experiment will document its research question, implementation variants, test inputs, measurement method, results, and conclusions.

The first experiment is matrix multiplication, beginning with row-wise and column-wise traversal to investigate how memory-access patterns affect performance.

## Repository structure

```text
master-thesis/
├── CMakeLists.txt
├── README.md
├── .gitattributes                   # keeps .sh and .conf files on Unix line endings
├── .gitignore
├── docs/
│   └── findings-log.md              # current summary + dated Q&A research log
├── scripts/                         # shared benchmark tooling for all experiments
│   ├── README.md                    # how to use it, add an experiment or a check
│   ├── run.sh                       # entry point: run.sh <experiment> [check ...]
│   ├── lib/common.sh
│   └── checks/                      # one file per check
│       ├── environment.sh
│       ├── timings.sh
│       ├── cache_counters.sh
│       └── no_vectorization.sh
└── experiments/
    └── 01-matrix-multiplication/
        ├── README.md                # report: question, theory, method, results, conclusions
        ├── 19-nov.txt               # cache-hierarchy notes (hardware vocabulary)
        ├── CMakeLists.txt
        ├── benchmark.conf           # settings the shared scripts read (target, versions, sizes)
        ├── main.cpp
        └── results/
            ├── 2026-10-18-ryzen5500u-wsl2/   # first timings + 3-run counters
            └── 2026-11-01-ryzen5500u-wsl2/   # theory-check run (see experiment README)
                ├── timings.csv, cache-counters.csv, no-vectorization-500.csv
                ├── perf-event-mapping.txt, environment.txt
                ├── large-n/                  # n = 1000, 1024
                ├── l3-sweep/                 # row_wise vs tiled, n = 600..1000
                └── tile-sweep/d8 .. d128/    # tile size at n = 1000
```

- The root `CMakeLists.txt` configures the overall project and registers the experiments.
- Each experiment is self-contained: its code, build file, benchmark settings (`benchmark.conf`), raw results and written findings all live in its own directory under `experiments/`. Start with that experiment's `README.md`.
- Measuring is done by the shared tooling in `scripts/`, so every experiment is measured the same way. You pass it an experiment's `benchmark.conf` (or directory) and choose which checks to run. See [scripts/README.md](scripts/README.md).
- Each measurement session gets its own dated folder under the experiment's `results/` (`<date>-<machine>`), with an `environment.txt` describing the hardware and toolchain. Old runs are not overwritten.
- `docs/findings-log.md` has a short current summary per experiment and a dated Q&A research log (what was asked, what was measured, what was later corrected).
- Build output and generated files belong in the build directory; they should not be committed to the repository.

## Experiments

| # | Experiment | Question | Report |
|---|---|---|---|
| 01 | Matrix multiplication | How does memory-access order (row-wise versus column-wise) affect speed, and can cache measurements explain it? | [README](experiments/01-matrix-multiplication/README.md) |

To add a new experiment:

1. Create `experiments/NN-name/` with its own `CMakeLists.txt`, program, `README.md` and `benchmark.conf`.
2. Make the program follow the contract in [scripts/README.md](scripts/README.md) (`<variant> <size> <repetitions>` in, CSV out), so the shared scripts can measure it.
3. Register it in the root `CMakeLists.txt` with `add_subdirectory(...)`.
4. Add a row to the table above and an entry in `docs/findings-log.md`.

## Requirements

- Git
- CMake 3.20 or newer
- A C++20-compatible compiler, such as GCC, Clang, or MSVC

Install a compiler and CMake using the tools appropriate for your operating system. For example, on Ubuntu or Ubuntu under WSL:

```bash
sudo apt update
sudo apt install build-essential cmake git
```

Check that the tools are available:

```bash
g++ --version
cmake --version
git --version
```

A different compiler can be used if it is supported by CMake and the project's C++ standard requirements.

## Get the source code

Clone the repository and enter its root directory (the directory containing the root `CMakeLists.txt`):

```bash
git clone https://github.com/aryan2574/master-thesis.git
cd master-thesis
```

## Configure and build

CMake is used to configure and build the experiments. Run these commands from the repository root.

For single-configuration generators commonly used with GCC or Clang on Linux and macOS:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

For multi-configuration generators, such as the Visual Studio generator on Windows:

```powershell
cmake -S . -B build
cmake --build build --config Release --parallel
```

To build only the matrix multiplication target:

```bash
cmake --build build --target matrix_multiplication --config Release --parallel
```

The `--config Release` argument is used by multi-configuration generators and is harmless for common single-configuration generators. For single-configuration builds, the root `CMakeLists.txt` defaults to a Release build when no build type is given; passing `-DCMAKE_BUILD_TYPE=Release` explicitly, as shown above, is still recommended. An unoptimised build is roughly 35 times slower on this experiment and gives misleading timings.

## Run an experiment

After a successful build, run the generated `matrix_multiplication` executable. Its exact location depends on the operating system, compiler, and CMake generator. For a typical single-configuration Linux build, run:

```bash
./build/experiments/01-matrix-multiplication/matrix_multiplication row_wise 512
```

The arguments are `<naive|row_wise|tiled> <n> [repetitions] [tile_size]`; run the program without arguments to see the usage line. See the [experiment README](experiments/01-matrix-multiplication/README.md) for what each version does.

For a typical Visual Studio multi-configuration build on Windows, the executable is usually under the experiment's `Release` build directory, for example:

```powershell
.\build\experiments\01-matrix-multiplication\Release\matrix_multiplication.exe row_wise 512
```

If the executable is not at that exact path, inspect the generated `build` directory or use your IDE's run configuration for the `matrix_multiplication` CMake target.

To measure an experiment (timings, cache counters, no-SIMD check and environment description) on Linux or WSL, use the shared scripts. For matrix multiplication:

```bash
bash scripts/run.sh experiments/01-matrix-multiplication            # all checks
bash scripts/run.sh experiments/01-matrix-multiplication timings    # one check
bash scripts/run.sh --list                                          # available checks
```

You can also open the repository root in any IDE that supports CMake projects. Load or configure the root `CMakeLists.txt`, choose an available C++ toolchain, and select the target for the experiment you want to run. The project does not require a specific IDE.

## Benchmarking and reproducibility

For a fair comparison, keep the compiler, optimisation settings, inputs, and measurement procedure consistent across implementations. Use a Release build for performance measurements, repeat measurements, and avoid drawing conclusions from a single run. Verify that compared implementations produce equivalent results.

Record at least the following for each experiment:

- CPU model and operating system
- Compiler name and version
- Build configuration and compiler flags
- Input sizes and implementation variant
- Number of repetitions and the summary statistic reported
- Timing method and any profiling tools or hardware counters used

Where supported, collect hardware-counter data—such as cache misses—alongside elapsed time. Be aware that virtualised environments and some operating systems may limit access to hardware performance counters.

Do not compare Debug-build timings with Release-build timings. Document environmental limitations and any measurement conditions that could affect the results.