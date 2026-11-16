# Check: oblivious
# Compares cache-oblivious and cache-aware multiplication on the three storage layouts
# (row-major, column-major, tile-wise) and writes oblivious.csv (one row per run).
# Skipped if OBLIVIOUS_PARAMS is empty. Sourced by scripts/run.sh.
#
# Versions (see main.cpp):
#   row_wise, col_wise                       plain loops, no parameter (row-major / column-major)
#   tiled                                    cache-aware, row-major layout, parameter = tile size
#   tiled_col_major                          cache-aware, column-major layout, parameter = tile size
#   tiled_tile_wise                          cache-aware, tile-wise layout, parameter = tile size
#   oblivious_row_major, oblivious_col_major recursive, parameter = smallest block of the recursion
#   oblivious_tile_wise                      recursive over tiles, parameter = tile size of the layout
#
# For each matrix size in OBLIVIOUS_SIZES, the parameter versions run once per value in
# OBLIVIOUS_PARAMS. Every version computes each element of C with the same additions in the same
# order, so all rows for one size must have an identical checksum (checked at the end).

OBLIVIOUS_PLAIN_VERSIONS="row_wise col_wise"
OBLIVIOUS_PARAM_VERSIONS="tiled tiled_col_major tiled_tile_wise oblivious_row_major oblivious_col_major oblivious_tile_wise"

# _oblivious_run <variant> <size> <parameter> <reference>
_oblivious_run() {
    "$RELEASE_EXE" "$1" "$2" "$(reps_for "$2")" "$3" "$4"
}

check_oblivious() {
    if [ -z "$OBLIVIOUS_PARAMS" ]; then
        warn "OBLIVIOUS_PARAMS is not set in benchmark.conf; skipping oblivious"
        return 0
    fi

    ensure_release_build
    log "Cache-oblivious vs cache-aware (parameters: $OBLIVIOUS_PARAMS; matrix sizes: $OBLIVIOUS_SIZES)"

    local out="$OUT_DIR/oblivious.csv" size variant param reference result
    : >"$out"

    for size in $OBLIVIOUS_SIZES; do
        if [ "$size" -le "$TILE_SWEEP_NAIVE_REFERENCE_MAX" ]; then
            reference=naive
        else
            reference=row_wise
        fi

        for variant in $OBLIVIOUS_PLAIN_VERSIONS; do
            echo "n=$size $variant" >&2
            result="$(_oblivious_run "$variant" "$size" 32 "$reference")"
            if [ ! -s "$out" ]; then
                echo "$result" | head -n 1 >"$out"
            fi
            echo "$result" | tail -n 1 >>"$out"
        done

        for variant in $OBLIVIOUS_PARAM_VERSIONS; do
            for param in $OBLIVIOUS_PARAMS; do
                echo "n=$size $variant parameter=$param" >&2
                result="$(_oblivious_run "$variant" "$size" "$param" "$reference")"
                echo "$result" | tail -n 1 >>"$out"
            done
        done
    done

    # Columns: 1=n 2=algorithm 3=tile_size 4=repetitions 5=median_ms 6=gflops 7=checksum
    awk -F, 'NR > 1 {
                 if (!($1 in first)) first[$1] = $7
                 else if ($7 != first[$1]) { bad = 1; print "error: checksum differs at n=" $1 " " $2 " " $3 > "/dev/stderr" }
             }
             END { exit bad }' "$out" || die "oblivious produced different checksums, see $out"
}
