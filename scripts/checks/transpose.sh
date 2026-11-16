# Check: transpose
# Compares naive, tiled (cache-aware) and recursive (cache-oblivious) out-of-place
# matrix transposition and writes transpose.csv (one row per run).
# Skipped if TRANSPOSE_SIZES is empty. Sourced by scripts/run.sh.
#
# Versions (see main.cpp):
#   transpose_naive       two nested loops (no parameter)
#   transpose_tiled       T x T tiles, parameter = tile size
#   transpose_oblivious   recursive split, parameter = smallest block of the recursion
#
# For each matrix size in TRANSPOSE_SIZES, the parameter versions run once per value in
# TRANSPOSE_PARAMS. Every version must produce the same checksum (checked at the end).
# The sixth CSV column is named gflops for the shared program format; for transpose it
# holds million elements copied per second.

TRANSPOSE_PLAIN_VERSIONS="transpose_naive"
TRANSPOSE_PARAM_VERSIONS="transpose_tiled transpose_oblivious"

# _transpose_run <variant> <size> <parameter>
_transpose_run() {
    "$RELEASE_EXE" "$1" "$2" "$(reps_for "$2")" "$3" transpose_naive
}

check_transpose() {
    if [ -z "$TRANSPOSE_SIZES" ]; then
        warn "TRANSPOSE_SIZES is not set in benchmark.conf; skipping transpose"
        return 0
    fi

    ensure_release_build
    log "Matrix transposition (parameters: $TRANSPOSE_PARAMS; matrix sizes: $TRANSPOSE_SIZES)"

    local out="$OUT_DIR/transpose.csv" size variant param result
    : >"$out"

    for size in $TRANSPOSE_SIZES; do
        for variant in $TRANSPOSE_PLAIN_VERSIONS; do
            echo "n=$size $variant" >&2
            result="$(_transpose_run "$variant" "$size" 32)"
            if [ ! -s "$out" ]; then
                echo "$result" | head -n 1 >"$out"
            fi
            echo "$result" | tail -n 1 >>"$out"
        done

        for variant in $TRANSPOSE_PARAM_VERSIONS; do
            for param in $TRANSPOSE_PARAMS; do
                echo "n=$size $variant parameter=$param" >&2
                result="$(_transpose_run "$variant" "$size" "$param")"
                echo "$result" | tail -n 1 >>"$out"
            done
        done
    done

    # Columns: 1=n 2=algorithm 3=tile_size 4=repetitions 5=median_ms 6=gflops 7=checksum
    awk -F, 'NR > 1 {
                 if (!($1 in first)) first[$1] = $7
                 else if ($7 != first[$1]) { bad = 1; print "error: checksum differs at n=" $1 " " $2 " " $3 > "/dev/stderr" }
             }
             END { exit bad }' "$out" || die "transpose produced different checksums, see $out"
}
