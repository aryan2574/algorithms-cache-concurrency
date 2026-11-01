# Check: environment
# Writes environment.txt: hardware, OS, compiler, build flags, git commit and
# the experiment's benchmark parameters. Sourced by scripts/run.sh.

check_environment() {
    ensure_release_build
    log "Environment"

    local cache="$RELEASE_BUILD_DIR/CMakeCache.txt"
    local compiler
    compiler="$(grep 'CMAKE_CXX_COMPILER:' "$cache" | cut -d= -f2)"

    {
        echo "=== Environment: $EXP_NAME ==="
        echo "Date (UTC): $(date -u '+%F %T')"
        echo "Git commit: $(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
        if [ -n "$(git -C "$REPO_ROOT" status --porcelain -- "$EXP_REL" 2>/dev/null)" ]; then
            echo "Working tree: has uncommitted changes in $EXP_REL"
        else
            echo "Working tree: clean for $EXP_REL"
        fi
        echo
        echo "=== Operating system ==="
        grep PRETTY_NAME /etc/os-release || true
        uname -a
        echo
        echo "=== CPU ==="
        lscpu | grep -E 'Model name|^CPU\(s\)|L1d|L2|L3' || true
        echo
        echo "=== Compiler and build ==="
        grep -E 'CMAKE_CXX_COMPILER:|CMAKE_BUILD_TYPE|CMAKE_CXX_FLAGS_RELEASE:' "$cache" || true
        "$compiler" --version | head -n 1
        cmake --version | head -n 1
        echo "No-vectorisation build adds: -fno-tree-vectorize -fno-tree-slp-vectorize"
        echo
        echo "=== Parameters (from $EXP_REL/benchmark.conf) ==="
        echo "TARGET=$TARGET"
        echo "VARIANTS=$VARIANTS"
        echo "SIZES=$SIZES"
        echo "REPS=$REPS  REPS_LARGE=$REPS_LARGE (sizes >= $LARGE_FROM)  EXTRA_ARGS=$EXTRA_ARGS"
        echo "COUNTER_SIZES=$COUNTER_SIZES  NOVEC_SIZE=$NOVEC_SIZE"
        echo "perf: $(perf --version 2>/dev/null || echo 'not available')"
    } >"$OUT_DIR/environment.txt"
}
