# Check: cache_counters
# Measures hardware cache counters with `perf stat` and writes
# cache-counters.csv (values are per single run of the experiment's work).
# Skipped with a warning if perf or the hardware counters are unavailable.
# Sourced by scripts/run.sh.
#
# The experiment program also does setup and a correctness check in the same
# process. To remove that, each variant is measured with LO = 1 and HI = 1 + COUNTER_RUNS
# repetitions; (HI counts - LO counts) / COUNTER_RUNS is the cost of one run alone.
#
# Which versions and tile sizes (settings in benchmark.conf, default = the old behaviour):
#   COUNTER_VERSIONS  versions to measure (default: VARIANTS)
#   COUNTER_PARAMS    tile sizes for the versions that take one (default: EXTRA_ARGS)
# naive, row_wise and col_wise have no parameter (tile_size is written as 0).
# The program always checks its result against row_wise here (not naive): the counters measure
# the version under test, and a naive reference at n=1024 would dominate the wall time.
# naive itself is skipped from TILE_SWEEP_NAIVE_REFERENCE_MAX on (it takes minutes).
#
# Note: perf under WSL2 counts user-mode events only (event names end in ":u").

# What the generic events count depends on the CPU (see scripts/README.md).
COUNTER_EVENTS=(cache-references cache-misses L1-dcache-loads L1-dcache-load-misses
                dTLB-loads dTLB-load-misses)
COUNTER_PLAIN_VERSIONS=" naive row_wise col_wise "

# _perf_counts <variant> <size> <repetitions> <tile size> <reference> <name of associative array to fill>
_perf_counts() {
    local variant="$1" size="$2" reps="$3" tile="$4" reference="$5"
    local -n counts="$6"
    local event_list
    event_list="$(IFS=,; echo "${COUNTER_EVENTS[*]}")"

    perf stat -x, -e "$event_list" -o "$TMP_DIR/perf.txt" \
        "$RELEASE_EXE" "$variant" "$size" "$reps" "$tile" "$reference" >/dev/null 2>&1

    local event
    for event in "${COUNTER_EVENTS[@]}"; do
        # Event names may carry a ":u" suffix (user-mode only), e.g. under WSL2.
        counts[$event]="$(awk -F, -v e="$event" '$3 == e || $3 == e ":u" { print $1 }' "$TMP_DIR/perf.txt")"
    done
}

# _counter_row <size> <variant> <tile size written to the CSV> <tile size passed> <reference>
_counter_row() {
    local size="$1" variant="$2" tile_label="$3" tile="$4" reference="$5"
    local LO=1 HI=$((1 + COUNTER_RUNS))
    declare -A lo=() hi=()
    _perf_counts "$variant" "$size" "$LO" "$tile" "$reference" lo
    _perf_counts "$variant" "$size" "$HI" "$tile" "$reference" hi
    awk -v n="$size" -v alg="$variant" -v tile="$tile_label" -v runs=$((HI - LO)) \
        -v rl="${lo[cache-references]}" -v rh="${hi[cache-references]}" \
        -v ml="${lo[cache-misses]}" -v mh="${hi[cache-misses]}" \
        -v ll="${lo[L1-dcache-loads]}" -v lh="${hi[L1-dcache-loads]}" \
        -v xl="${lo[L1-dcache-load-misses]}" -v xh="${hi[L1-dcache-load-misses]}" \
        -v tl="${lo[dTLB-loads]}" -v th="${hi[dTLB-loads]}" \
        -v ul="${lo[dTLB-load-misses]}" -v uh="${hi[dTLB-load-misses]}" \
        'function per_run(l, h) {
            # Empty when perf reports "<not supported>" or "<not counted>".
            if (l !~ /^[0-9]+$/ || h !~ /^[0-9]+$/) return ""
            return sprintf("%.0f", (h - l) / runs)
        }
        BEGIN {
            loads = (lh - ll) / runs; miss = (xh - xl) / runs
            printf "%d,%s,%d,%d,%.0f,%.0f,%.2f,%.0f,%.0f,%s,%s\n", n, alg, tile, runs,
                loads, miss, 100 * miss / loads,
                (rh - rl) / runs, (mh - ml) / runs,
                per_run(tl, th), per_run(ul, uh)
        }' >>"$OUT_DIR/cache-counters.csv"
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
    local versions="${COUNTER_VERSIONS:-$VARIANTS}" params="${COUNTER_PARAMS:-$EXTRA_ARGS}"
    log "Cache counters (versions: $versions; tile sizes: $params; sizes: $COUNTER_SIZES)"

    echo "n,algorithm,tile_size,runs_measured,l1_loads_per_run,l1_load_misses_per_run,l1_miss_rate_pct,cache_refs_per_run,cache_misses_per_run,dtlb_loads_per_run,dtlb_load_misses_per_run" \
        >"$OUT_DIR/cache-counters.csv"

    local size variant param
    for size in $COUNTER_SIZES; do
        for variant in $versions; do
            # naive at n=1024 already takes about a minute for the LO/HI pair; skip from that size on
            if [ "$variant" = naive ] && [ "$size" -ge "$TILE_SWEEP_NAIVE_REFERENCE_MAX" ]; then
                warn "skipping naive at n=$size (too slow)"
                continue
            fi
            if [[ "$COUNTER_PLAIN_VERSIONS" == *" $variant "* ]]; then
                echo "n=$size $variant" >&2
                _counter_row "$size" "$variant" 0 32 row_wise
            else
                for param in $params; do
                    # the tile-wise layout needs n to be a multiple of the tile size
                    if [[ "$variant" == *tile_wise ]] && [ $((size % param)) -ne 0 ]; then
                        warn "skipping $variant at n=$size: tile size $param does not divide n"
                        continue
                    fi
                    echo "n=$size $variant tile=$param" >&2
                    _counter_row "$size" "$variant" "$param" "$param" row_wise
                done
            fi
        done
    done
}
