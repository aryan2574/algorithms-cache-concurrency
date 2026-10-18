# Check: no_vectorization
# Re-times every variant at NOVEC_SIZE with SIMD auto-vectorisation switched off,
# to separate the effect of memory access from the effect of vectorisation.
# Writes no-vectorization-<NOVEC_SIZE>.csv. Sourced by scripts/run.sh.

check_no_vectorization() {
    if [ -z "$NOVEC_SIZE" ]; then
        warn "NOVEC_SIZE is not set in benchmark.conf; skipping no_vectorization"
        return 0
    fi

    ensure_novec_build
    log "No-vectorisation check (size $NOVEC_SIZE)"

    local out="$OUT_DIR/no-vectorization-$NOVEC_SIZE.csv" variant result
    : >"$out"

    for variant in $VARIANTS; do
        result="$(run_variant "$NOVEC_EXE" "$variant" "$NOVEC_SIZE" "$REPS")"
        if [ ! -s "$out" ]; then
            echo "$result" | head -n 1 >"$out"
        fi
        echo "$result" | tail -n 1 >>"$out"
    done
}
