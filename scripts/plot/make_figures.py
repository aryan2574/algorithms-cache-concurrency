#!/usr/bin/env python3
"""Makes the figures of an experiment from a results folder.

Usage:
  python scripts/plot/make_figures.py <results folder> [--out DIR] [--formats pdf png]
                                      [--only NAME ...] [--experiment NAME]
  python scripts/plot/make_figures.py --diagrams [--out DIR] [--formats pdf png]
  python scripts/plot/make_figures.py --list

<results folder>  one dated measurement session, for example
                  experiments/01-matrix-multiplication/results/2026-11-14-ryzen5500u-wsl2-run2
                  Figures are written to docs/<experiment>/figures/<session>/ unless --out is given.
                  A relative path is looked up from the current directory and then from the
                  repository root. If the folder only contains sessions (for example
                  experiments/01-matrix-multiplication/results), every session is processed.
--diagrams        the conceptual diagrams of an experiment (memory layouts, recursion). They need
                  no data and go to docs/<experiment>/diagrams/ unless --out is given.
--only NAME ...   only these figures (names from --list)
--experiment      the experiment directory name, if the results folder is not inside
                  experiments/<name>/results/

A figure whose CSV tables are not in the folder is skipped with a message, so the same command
works for every results folder. What each figure shows is explained in the experiment README.
See scripts/plot/README.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # write files, never open a window

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt  # noqa: E402

from plotlib import data, diagrams, experiment01, style  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

# experiment directory name -> module with a FIGURES dict
EXPERIMENTS = {"01-matrix-multiplication": experiment01}


def list_figures() -> None:
    for experiment, module in EXPERIMENTS.items():
        print(f"{experiment}:")
        for name, (_, needs) in module.FIGURES.items():
            print(f"  {name:28s} needs: {', '.join(needs)}")
        print("  diagrams (--diagrams): " + ", ".join(module.DIAGRAMS))


def docs_folder(experiment: str) -> Path:
    """All generated figures of an experiment live in docs/<experiment>/."""
    return REPO_ROOT / "docs" / experiment


def make_diagrams(experiment: str | None, out_dir: Path | None, formats: list[str]) -> int:
    if experiment is None and len(EXPERIMENTS) == 1:
        experiment = next(iter(EXPERIMENTS))
    if experiment not in EXPERIMENTS:
        print(f"error: say which experiment with --experiment ({', '.join(EXPERIMENTS)})", file=sys.stderr)
        return 1
    out_dir = out_dir or docs_folder(experiment) / "diagrams"
    style.apply()
    for name, function in EXPERIMENTS[experiment].DIAGRAMS.items():
        fig = function()
        for path in style.save(fig, out_dir, name, formats):
            print(f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
        plt.close(fig)
    return 0


def resolve_folder(folder: Path) -> Path | None:
    """Finds the folder from the current directory or, failing that, from the repository root,
    so the command works from any directory (for example from inside scripts/)."""
    if folder.exists():
        return folder.resolve()
    if not folder.is_absolute() and (REPO_ROOT / folder).exists():
        return (REPO_ROOT / folder).resolve()
    return None


def session_folders(folder: Path) -> list[Path]:
    """A session folder holds the CSV files itself. A folder that only holds session folders
    (for example .../results) stands for all of them."""
    if any(folder.glob("*.csv")):
        return [folder]
    return sorted(p for p in folder.iterdir() if p.is_dir() and any(p.glob("*.csv")))


def make_experiment_figures(folder: Path, out_dir: Path | None, formats: list[str],
                            only: list[str] | None, experiment: str | None) -> int:
    found = resolve_folder(folder)
    if found is None:
        print(f"error: folder not found: {folder} (looked in the current directory and in {REPO_ROOT})",
              file=sys.stderr)
        return 1
    sessions = session_folders(found)
    if not sessions:
        print(f"error: no CSV files in {found} or in its sub-folders", file=sys.stderr)
        return 1
    if len(sessions) > 1:
        if out_dir is not None:
            print("error: --out cannot be used when several sessions are processed", file=sys.stderr)
            return 1
        print(f"{len(sessions)} sessions found in {found}")
    status = 0
    for session in sessions:
        status |= make_session_figures(session, out_dir, formats, only, experiment)
        print()
    return status


def make_session_figures(folder: Path, out_dir: Path | None, formats: list[str],
                         only: list[str] | None, experiment: str | None) -> int:
    # experiments/<experiment>/results/<session>: the experiment is two levels above the session
    experiment = experiment or folder.parent.parent.name
    if experiment not in EXPERIMENTS:
        print(f"error: no figures are defined for '{experiment}'. Known: {', '.join(EXPERIMENTS)} "
              f"(use --experiment if the folder is somewhere else)", file=sys.stderr)
        return 1
    module = EXPERIMENTS[experiment]

    unknown = [n for n in (only or []) if n not in module.FIGURES]
    if unknown:
        print(f"error: unknown figure(s): {', '.join(unknown)}. See --list.", file=sys.stderr)
        return 1

    run = data.load_run(folder)
    out_dir = out_dir or docs_folder(experiment) / "figures" / folder.name
    style.apply()

    print(f"results: {folder}")
    print(f"tables:  {', '.join(sorted(run.tables)) or 'none'}")
    for note in run.notes:
        print(f"note: {note}")

    made = 0
    for name, (function, needs) in module.FIGURES.items():
        if only and name not in only:
            continue
        missing = [t for t in needs if t not in run.tables]
        if missing:
            print(f"skipped {name}: needs {', '.join(missing)}")
            continue
        try:
            fig = function(run)
        except data.NotApplicable as reason:
            print(f"skipped {name}: {reason}")
            continue
        for path in style.save(fig, out_dir, name, formats, run.machine.footnote(run.name)):
            print(f"wrote {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
        plt.close(fig)
        made += 1

    if made == 0:
        print("no figure could be made from this folder")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", nargs="?", type=Path, help="results folder (one dated session)")
    parser.add_argument("--out", type=Path, help="output folder for the figures")
    parser.add_argument("--formats", nargs="+", default=["pdf", "png"], choices=["pdf", "png", "svg"],
                        help="file formats (default: pdf png)")
    parser.add_argument("--only", nargs="+", help="only these figures")
    parser.add_argument("--experiment", help="experiment directory name, e.g. 01-matrix-multiplication")
    parser.add_argument("--diagrams", action="store_true", help="make the conceptual diagrams instead")
    parser.add_argument("--list", action="store_true", help="list the available figures")
    args = parser.parse_args()

    if args.list:
        list_figures()
        return 0
    if args.diagrams:
        return make_diagrams(args.experiment, args.out, args.formats)
    if args.folder is None:
        parser.print_help()
        return 1
    return make_experiment_figures(args.folder, args.out, args.formats, args.only, args.experiment)


if __name__ == "__main__":
    sys.exit(main())
