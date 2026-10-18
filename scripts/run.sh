#!/usr/bin/env bash
# Runs benchmark checks for one experiment. Works on Linux and WSL.
#
# Usage:
#   bash scripts/run.sh <experiment> [check ...] [--out DIR]
#   bash scripts/run.sh --list
#
# <experiment>  an experiment's benchmark.conf, or the experiment directory
#               that contains one
# check         which checks to run (default: all). See --list.
# --out DIR     where to write results
#               (default: <experiment dir>/results/<YYYY-MM-DD>-local)
#
# Examples:
#   bash scripts/run.sh experiments/01-matrix-multiplication
#   bash scripts/run.sh experiments/01-matrix-multiplication timings
#   bash scripts/run.sh experiments/01-matrix-multiplication/benchmark.conf \
#        environment cache_counters --out /tmp/my-run
#
# Any setting in benchmark.conf can be overridden from the command line:
#   SIZES="64 128" REPS=3 bash scripts/run.sh experiments/01-matrix-multiplication timings
#
# See scripts/README.md for how to add an experiment or a new check.

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPTS_DIR/.." && pwd)"

# shellcheck source=lib/common.sh
source "$SCRIPTS_DIR/lib/common.sh"

DEFAULT_CHECKS=(environment timings cache_counters no_vectorization)

available_checks() {
    local file
    for file in "$SCRIPTS_DIR"/checks/*.sh; do
        basename "$file" .sh
    done
}

usage() {
    sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

experiment=""
out_dir_arg=""
checks=()

while [ $# -gt 0 ]; do
    case "$1" in
        -h | --help) usage; exit 0 ;;
        --list) available_checks; exit 0 ;;
        --out) out_dir_arg="${2:?--out needs a directory}"; shift 2 ;;
        -*) die "unknown option: $1 (try --help)" ;;
        *)
            if [ -z "$experiment" ]; then experiment="$1"; else checks+=("$1"); fi
            shift
            ;;
    esac
done

if [ -z "$experiment" ]; then usage; exit 1; fi
if [ -d "$experiment" ]; then experiment="$experiment/benchmark.conf"; fi
if [ ${#checks[@]} -eq 0 ]; then checks=("${DEFAULT_CHECKS[@]}"); fi

for check in "${checks[@]}"; do
    [ -f "$SCRIPTS_DIR/checks/$check.sh" ] ||
        die "unknown check '$check'. Available: $(available_checks | tr '\n' ' ')"
done

load_experiment "$experiment"

OUT_DIR="${out_dir_arg:-$EXP_DIR/results/$(date +%F)-local}"
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Experiment: $EXP_NAME"
echo "Checks:     ${checks[*]}"
echo "Output:     $OUT_DIR"

for check in "${checks[@]}"; do
    # shellcheck disable=SC1090
    source "$SCRIPTS_DIR/checks/$check.sh"
    "check_$check"
done

echo "Done. Results are in: $OUT_DIR"
