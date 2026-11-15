"""Loading a results folder: the CSV tables and a description of the machine.

A results folder is one dated measurement session, for example
experiments/01-matrix-multiplication/results/2026-11-14-ryzen5500u-wsl2-run2/.
It holds environment.txt and any of the CSV files written by the scripts in scripts/checks/.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

KIB = 1024
MIB = 1024 * 1024


class NotApplicable(Exception):
    """Raised by a figure function when the table exists but lacks what the figure needs
    (for example a partial results folder). make_figures.py skips the figure with the message."""


def fmt_bytes(n_bytes: float) -> str:
    """32768 -> '32 KiB', 8388608 -> '8 MiB'."""
    if n_bytes >= MIB:
        return f"{n_bytes / MIB:g} MiB"
    return f"{n_bytes / KIB:g} KiB"


def matrix_bytes(n: int) -> int:
    """Size of one n x n matrix of double."""
    return 8 * n * n


@dataclass
class Machine:
    """What the results were measured on. Cache sizes are in bytes, per core (L3: shared)."""

    model: str = "unknown CPU"
    l1d: int = 32 * KIB
    l2: int = 512 * KIB
    l3: int = 4 * MIB
    compiler: str = ""
    system: str = ""
    from_environment: bool = False  # False = the defaults above, environment.txt was not usable

    def caches(self) -> list[tuple[str, int]]:
        return [("L1", self.l1d), ("L2", self.l2), ("L3", self.l3)]

    def footnote(self, run_name: str) -> str:
        caches = f"L1d {fmt_bytes(self.l1d)}, L2 {fmt_bytes(self.l2)}, L3 {fmt_bytes(self.l3)}"
        parts = [self.model, caches]
        if self.system:
            parts.append(self.system)
        if self.compiler:
            parts.append(self.compiler)
        parts.append("double, 1 thread")
        parts.append(f"run: {run_name}")
        return " | ".join(parts)


def _size_to_bytes(value: str, unit: str, instances: str | None) -> int:
    total = float(value) * (MIB if unit == "MiB" else KIB)
    return int(total / int(instances)) if instances else int(total)


def parse_environment(text: str) -> Machine:
    """Reads the lscpu lines written by scripts/checks/environment.sh."""
    machine = Machine()
    found = 0

    model = re.search(r"Model name:\s+(.+)", text)
    if model:
        machine.model = re.sub(r"\s+with .*$", "", model.group(1).strip())  # drop 'with Radeon Graphics'
        found += 1

    for field_name, label in (("l1d", "L1d"), ("l2", "L2"), ("l3", "L3")):
        m = re.search(rf"^{label} cache:\s+([\d.]+)\s*(KiB|MiB)(?:\s+\((\d+) instances?\))?", text, re.M)
        if m:
            # lscpu prints the total over all instances; the cache of one core is what matters
            # for L1 and L2. L3 is shared (the number of instances is normally 1).
            instances = m.group(3) if field_name != "l3" else None
            setattr(machine, field_name, _size_to_bytes(m.group(1), m.group(2), instances))
            found += 1

    compiler = re.search(r"^((?:c\+\+|g\+\+|clang\+\+?)\s.*\d+\.\d+\.\d+.*)$", text, re.M)
    flags = re.search(r"CMAKE_CXX_FLAGS_RELEASE:STRING=(\S+)", text)
    if compiler:
        version = re.search(r"\d+\.\d+\.\d+", compiler.group(1)).group(0)
        machine.compiler = f"g++ {version}" + (f" {flags.group(1)}" if flags else "")
    if re.search(r"microsoft", text, re.I) and "WSL" in text:
        machine.system = "WSL2"

    machine.from_environment = found >= 4
    return machine


@dataclass
class Run:
    folder: Path
    name: str
    machine: Machine
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def has(self, *names: str) -> bool:
        return all(n in self.tables for n in names)


def load_run(folder: Path) -> Run:
    """Loads environment.txt and every known CSV table of a results folder."""
    folder = Path(folder)
    if not folder.is_dir():
        raise SystemExit(f"error: results folder not found: {folder}")

    env_file = folder / "environment.txt"
    notes: list[str] = []
    if env_file.is_file():
        machine = parse_environment(env_file.read_text(encoding="utf-8", errors="replace"))
        if not machine.from_environment:
            notes.append("environment.txt could not be fully parsed: default cache sizes are used")
    else:
        machine = Machine()
        notes.append("no environment.txt: default machine description (32 KiB / 512 KiB / 4 MiB) is used")

    run = Run(folder=folder, name=folder.name, machine=machine, notes=notes)

    for stem in ("tile-sweep", "oblivious", "timings", "cache-counters"):
        path = folder / f"{stem}.csv"
        if path.is_file() and path.stat().st_size > 0:
            table = pd.read_csv(path)
            # older cache-counters.csv had no tile_size column; treat that as 0 (no parameter)
            if stem == "cache-counters" and "tile_size" not in table.columns:
                table.insert(2, "tile_size", 0)
            run.tables[stem] = table

    novec = sorted(folder.glob("no-vectorization-*.csv"))
    if novec and novec[0].stat().st_size > 0:
        table = pd.read_csv(novec[0])
        run.tables["no-vectorization"] = table

    return run


SPEED_STEMS = ("oblivious", "tile-sweep", "timings")


def _concat_speed(frames: list[pd.DataFrame]) -> pd.DataFrame:
    table = pd.concat(frames, ignore_index=True)
    return table.drop_duplicates(subset=["n", "algorithm", "tile_size"], keep="first")


def speed_table(run: Run) -> tuple[pd.DataFrame, str] | None:
    """Timing rows (n, algorithm, tile_size, median_ms, gflops) to put next to hardware counters.

    The counters session does not time the versions (the counters are measured under `perf`).
    Its own timing tables are used if it has any; otherwise the newest sibling session of the same
    experiment that has an oblivious.csv. Returns (table, name of the session the speeds come from)."""
    own = [run.tables[s] for s in SPEED_STEMS if s in run.tables]
    if own:
        return _concat_speed(own), run.name
    for sibling in sorted((p for p in run.folder.parent.iterdir() if p.is_dir() and p != run.folder), reverse=True):
        if (sibling / "oblivious.csv").is_file():
            frames = [pd.read_csv(sibling / f"{s}.csv") for s in SPEED_STEMS if (sibling / f"{s}.csv").is_file()]
            return _concat_speed(frames), sibling.name
    return None


def best_per_group(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """For every combination of `keys`, the row with the smallest median_ms."""
    idx = df.groupby(keys)["median_ms"].idxmin()
    return df.loc[idx].reset_index(drop=True)
