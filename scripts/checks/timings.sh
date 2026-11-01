# Check: timings
# Runs every variant at every size and writes timings.csv (one row per run).
# The CSV header is taken from the experiment program's own output.
# Sourced by scripts/run.sh.

check_timings() {
    ensure_release_build
    log "Timings"

    local out="$OUT_DIR/timings.csv" size variant result
    : >"$out"

    for size in $SIZES; do
        for variant in $VARIANTS; do
            result="$(run_variant "$RELEASE_EXE" "$variant" "$size" "$(reps_for "$size")")"
            if [ ! -s "$out" ]; then
                echo "$result" | head -n 1 >"$out"
            fi
            echo "$result" | tail -n 1 >>"$out"
        done
    done
}
