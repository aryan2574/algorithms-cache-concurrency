# Shared helpers for the benchmark scripts. Sourced by scripts/run.sh,
# never run directly.
#
# Variables available to every check after load_experiment:
#   REPO_ROOT   repository root
#   EXP_DIR     experiment directory (the one containing benchmark.conf)
#   EXP_NAME    experiment directory name, e.g. 01-matrix-multiplication
#   EXP_REL     experiment path relative to the repository root
#   OUT_DIR     where this run writes its result files
#   TMP_DIR     scratch directory, removed when the run ends
#   plus everything defined in the experiment's benchmark.conf

log() { echo "== $* =="; }
warn() { echo "warning: $*" >&2; }
die() { echo "error: $*" >&2; exit 1; }

# load_experiment <path to benchmark.conf>
load_experiment() {
    local conf="$1"
    [ -f "$conf" ] || die "experiment file not found: $conf"

    EXP_DIR="$(cd "$(dirname "$conf")" && pwd)"
    EXP_NAME="$(basename "$EXP_DIR")"
    EXP_REL="${EXP_DIR#"$REPO_ROOT"/}"

    # shellcheck disable=SC1090
    source "$conf"

    : "${TARGET:?benchmark.conf must set TARGET (the CMake target name)}"
    : "${VARIANTS:?benchmark.conf must set VARIANTS (the versions to compare)}"
    : "${SIZES:?benchmark.conf must set SIZES (the problem sizes)}"
    : "${REPS:=7}"           # repetitions for sizes below LARGE_FROM
    : "${REPS_LARGE:=5}"     # repetitions for sizes from LARGE_FROM upwards
    : "${LARGE_FROM:=1024}"
    : "${EXTRA_ARGS:=}"      # appended after <variant> <size> <repetitions>
    : "${COUNTER_SIZES:=}"   # empty = skip the cache_counters check
    : "${NOVEC_SIZE:=}"      # empty = skip the no_vectorization check
}

# reps_for <size>
reps_for() {
    if [ "$1" -ge "$LARGE_FROM" ]; then echo "$REPS_LARGE"; else echo "$REPS"; fi
}

# build_variant <build_dir> [extra CMAKE_CXX_FLAGS]
# Configures and builds only the experiment's target in Release mode.
build_variant() {
    local build_dir="$1" flags="${2:-}"
    cmake -S "$REPO_ROOT" -B "$build_dir" \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_FLAGS="$flags" >/dev/null
    cmake --build "$build_dir" --target "$TARGET" --parallel >/dev/null
}

# ensure_release_build: builds once per run, sets RELEASE_BUILD_DIR and RELEASE_EXE.
ensure_release_build() {
    if [ -z "${RELEASE_EXE:-}" ]; then
        log "Building $TARGET (Release)"
        RELEASE_BUILD_DIR="$REPO_ROOT/build/$EXP_NAME-release"
        build_variant "$RELEASE_BUILD_DIR"
        RELEASE_EXE="$RELEASE_BUILD_DIR/$EXP_REL/$TARGET"
        [ -x "$RELEASE_EXE" ] || die "executable not found: $RELEASE_EXE"
    fi
}

# ensure_novec_build: same, without SIMD auto-vectorisation. Sets NOVEC_EXE.
ensure_novec_build() {
    if [ -z "${NOVEC_EXE:-}" ]; then
        log "Building $TARGET (Release, no auto-vectorisation)"
        local build_dir="$REPO_ROOT/build/$EXP_NAME-no-vectorization"
        build_variant "$build_dir" "-fno-tree-vectorize -fno-tree-slp-vectorize"
        NOVEC_EXE="$build_dir/$EXP_REL/$TARGET"
        [ -x "$NOVEC_EXE" ] || die "executable not found: $NOVEC_EXE"
    fi
}

# run_variant <exe> <variant> <size> <repetitions>
# Runs the experiment program once. Prints its stdout (CSV header, then one row).
# The program's stderr (progress messages) goes to the terminal.
run_variant() {
    local exe="$1" variant="$2" size="$3" reps="$4"
    # EXTRA_ARGS is intentionally unquoted so it can hold several arguments.
    # shellcheck disable=SC2086
    "$exe" "$variant" "$size" "$reps" $EXTRA_ARGS
}
