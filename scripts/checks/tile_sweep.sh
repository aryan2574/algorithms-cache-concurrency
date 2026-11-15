# Check: tile_sweep
# Runs every version in TILE_SWEEP_VERSIONS (default: tiled = row-major layout,
# tiled_tile_wise = tile-wise layout; tiled_col_major also works) at every tile size in
# TILE_SIZES, for every size in TILE_SWEEP_SIZES, and writes tile-sweep.csv (one row per
# run). For each size it first runs `row_wise` as the baseline (tile_size column 0):
# tiling is only worth it if it beats that. Tile-wise versions are skipped (with a
# message) for tile sizes that do not divide n, for example a tile larger than n.
# Skipped if TILE_SIZES is empty. Sourced by scripts/run.sh.
#
# Needs an experiment program that accepts:
#   <exe> <variant> <size> <repetitions> <tile_size> <reference>
# where <reference> is the version used for the correctness check.
#
# Every version computes each element of C with the same additions in the same
# order, so all rows for one size must have an identical checksum. A mismatch
# means a wrong result and is reported as an error.

# _sweep_run <variant> <size> <tile_size> <reference>
# Prints the program's CSV (header, then one row).
_sweep_run() {
    "$RELEASE_EXE" "$1" "$2" "$(reps_for "$2")" "$3" "$4"
}

check_tile_sweep() {
    if [ -z "$TILE_SIZES" ]; then
        warn "TILE_SIZES is not set in benchmark.conf; skipping tile_sweep"
        return 0
    fi

    ensure_release_build
    log "Tile-size sweep (tile sizes: $TILE_SIZES; matrix sizes: $TILE_SWEEP_SIZES)"

    local out="$OUT_DIR/tile-sweep.csv" size version tile reference result
    : >"$out"

    for size in $TILE_SWEEP_SIZES; do
        if [ "$size" -le "$TILE_SWEEP_NAIVE_REFERENCE_MAX" ]; then
            reference=naive
        else
            reference=row_wise
        fi

        result="$(_sweep_run row_wise "$size" 32 "$reference")"
        if [ ! -s "$out" ]; then
            echo "$result" | head -n 1 >"$out"
        fi
        echo "$result" | tail -n 1 >>"$out"

        for version in $TILE_SWEEP_VERSIONS; do
            for tile in $TILE_SIZES; do
                # The tile-wise layout needs n to be a multiple of the tile size, so a tile
                # larger than n (or not dividing n) cannot be run. Say so and go on.
                if [[ "$version" == *tile_wise* ]] && [ $((size % tile)) -ne 0 ]; then
                    echo "n=$size $version tile=$tile: skipped (n is not a multiple of the tile size)" >&2
                    continue
                fi
                echo "n=$size $version tile=$tile" >&2
                result="$(_sweep_run "$version" "$size" "$tile" "$reference")"
                echo "$result" | tail -n 1 >>"$out"
            done
        done
    done

    # Columns: 1=n 2=algorithm 3=tile_size 4=repetitions 5=median_ms 6=gflops 7=checksum
    awk -F, 'NR > 1 {
                 if (!($1 in first)) first[$1] = $7
                 else if ($7 != first[$1]) { bad = 1; print "error: checksum differs at n=" $1 " tile=" $3 > "/dev/stderr" }
             }
             END { exit bad }' "$out" || die "tile_sweep produced different checksums, see $out"
}
