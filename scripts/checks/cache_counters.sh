# Check: cache_counters
# Measures hardware cache counters with `perf stat` and writes
# cache-counters.csv (values are per single run of the experiment's work).
# Skipped with a warning if perf or the hardware counters are unavailable.
# Sourced by scripts/run.sh.
#
# The experiment program also does setup and a correctness check in the same
# process. To remove that, each variant is measured with LO and HI repetitions;
# (HI counts - LO counts) / (HI - LO) is the cost of one run alone.

COUNTER_EVENTS=(cache-references cache-misses L1-dcache-loads L1-dcache-load-misses)

# _perf_counts <variant> <size> <repetitions> <name of associative array to fill>
_perf_counts() {
    local variant="$1" size="$2" reps="$3"
    local -n counts="$4"
    local event_list
    event_list="$(IFS=,; echo "${COUNTER_EVENTS[*]}")"

    # shellcheck disable=SC2086
    perf stat -x, -e "$event_list" -o "$TMP_DIR/perf.txt" \
        "$RELEASE_EXE" "$variant" "$size" "$reps" $EXTRA_ARGS >/dev/null 2>&1

    local event
    for event in "${COUNTER_EVENTS[@]}"; do
        # Event names may carry a ":u" suffix (user-mode only), e.g. under WSL2.
        counts[$event]="$(awk -F, -v e="$event" '$3 == e || $3 == e ":u" { print $1 }' "$TMP_DIR/perf.txt")"
    done
}

check_cache_counters() {
    if [ -z "$COUNTER_SIZES" ]; then
        warn "COUNTER_SIZES is not set in benchmark.conf; skipping cache_counters"
        return 0
    fi
    if ! command -v perf >/dev/null 2>&1 || ! perf stat -e cache-misses true >/dev/null 2>&1; then
        warn "perf is not available or hardware counters are blocked; skipping cache_counters"
        return 0
    fi

    ensure_release_build
    log "Cache counters"

    local LO=1 HI=4 size variant
    local out="$OUT_DIR/cache-counters.csv"
    echo "n,algorithm,runs_measured,l1_loads_per_run,l1_load_misses_per_run,l1_miss_rate_pct,cache_refs_per_run,cache_misses_per_run" >"$out"

    for size in $COUNTER_SIZES; do
        for variant in $VARIANTS; do
            declare -A lo=() hi=()
            _perf_counts "$variant" "$size" "$LO" lo
            _perf_counts "$variant" "$size" "$HI" hi
            awk -v n="$size" -v alg="$variant" -v runs=$((HI - LO)) \
                -v rl="${lo[cache-references]}" -v rh="${hi[cache-references]}" \
                -v ml="${lo[cache-misses]}" -v mh="${hi[cache-misses]}" \
                -v ll="${lo[L1-dcache-loads]}" -v lh="${hi[L1-dcache-loads]}" \
                -v xl="${lo[L1-dcache-load-misses]}" -v xh="${hi[L1-dcache-load-misses]}" \
                'BEGIN {
                    loads = (lh - ll) / runs; miss = (xh - xl) / runs
                    printf "%d,%s,%d,%.0f,%.0f,%.2f,%.0f,%.0f\n", n, alg, runs,
                        loads, miss, 100 * miss / loads,
                        (rh - rl) / runs, (mh - ml) / runs
                }' >>"$out"
            unset lo hi
        done
    done
}
