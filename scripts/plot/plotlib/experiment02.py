"""Figures for experiment 02 (merge sort: recursive vs iterative).

Tables: timings, cache-counters. Columns of timings match experiment 01
(n, algorithm, tile_size, repetitions, median_ms, gflops, checksum); gflops holds
million elements sorted per second.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch, Rectangle

from . import style
from .data import NotApplicable, Run, fmt_bytes

REC = "recursive"
IT = "iterative"

REC_STYLE = {"color": style.BLUE, "linestyle": "--", "marker": "s", "label": "recursive (top-down)"}
IT_STYLE = {"color": style.VERMILLION, "linestyle": "-", "marker": "o", "label": "iterative (bottom-up)"}


def _finish_layout(fig, bottom: float = 0.04) -> None:
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.set(rect=(0, bottom, 1, 1 - bottom))


def _power_of_two_axis(ax, values, axis: str = "x") -> None:
    values = sorted(set(int(v) for v in values))
    if axis == "x":
        ax.set_xscale("log", base=2)
        ax.set_xticks(values)
        ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
        ax.xaxis.set_minor_locator(mticker.NullLocator())
    else:
        ax.set_yscale("log", base=2)
        ax.set_yticks(values)
        ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
        ax.yaxis.set_minor_locator(mticker.NullLocator())


def _plain_log_yaxis(ax) -> None:
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(mticker.NullLocator())


def _cache_boundaries(run: Run) -> list[tuple[float, str]]:
    """n where the working set (array + temp = 16n bytes) crosses each cache size."""
    out = []
    for name, size in run.machine.caches():
        n = size / 16  # bytes / (2 * 8-byte elements)
        out.append((n, f"{name} ({fmt_bytes(size)})"))
    return out


def _vlines(ax, positions: list[tuple[float, str]], lo: float, hi: float) -> None:
    for x, label in positions:
        if lo <= x <= hi:
            ax.axvline(x, color="#888888", linestyle=":", linewidth=0.9, zorder=0)
            ax.text(x, 0.98, label, transform=ax.get_xaxis_transform(), rotation=90,
                    va="top", ha="right", fontsize=6, color="#555555")


def _pair(df, n: int):
    rec = df[(df.n == n) & (df.algorithm == REC)]
    it = df[(df.n == n) & (df.algorithm == IT)]
    if len(rec) == 0 or len(it) == 0:
        return None
    return float(rec.median_ms.iloc[0]), float(it.median_ms.iloc[0])


def fig_overview_time_vs_n(run: Run):
    """Median time against n for recursive and iterative mergesort."""
    df = run.tables["timings"]
    fig, ax = plt.subplots(figsize=(6.2, 3.6), layout="constrained")
    for name, st in ((REC, REC_STYLE), (IT, IT_STYLE)):
        sub = df[df.algorithm == name].sort_values("n")
        if sub.empty:
            continue
        ax.plot(sub.n, sub.median_ms, **st)
    ns = sorted(df.n.unique())
    _power_of_two_axis(ax, ns)
    _plain_log_yaxis(ax)
    _vlines(ax, _cache_boundaries(run), min(ns), max(ns))
    ax.set_xlabel("array length n (int64)")
    ax.set_ylabel("median time (ms)")
    ax.set_title("Merge sort: recursive vs iterative")
    ax.legend(loc="upper left")
    _finish_layout(fig)
    return fig


def fig_ratio_vs_n(run: Run):
    """Time ratio iterative / recursive against n (>1 means recursive is faster)."""
    df = run.tables["timings"]
    ns, ratios = [], []
    for n in sorted(df.n.unique()):
        pair = _pair(df, int(n))
        if pair is None:
            continue
        rec_ms, it_ms = pair
        ns.append(int(n))
        ratios.append(it_ms / rec_ms)

    if not ns:
        raise NotApplicable("timings has no paired recursive/iterative rows")

    fig, ax = plt.subplots(figsize=(6.2, 3.6), layout="constrained")
    ax.plot(ns, ratios, color=style.GREEN, marker="D", linestyle="-")
    ax.axhline(1.0, color=style.GREY, linestyle="--", linewidth=1.0, label="equal time")
    ax.fill_between(ns, 1.0 - style.NOISE_BAND, 1.0 + style.NOISE_BAND,
                     color=style.GREY, alpha=0.15, label="±10% noise band")
    _power_of_two_axis(ax, ns)
    _vlines(ax, _cache_boundaries(run), min(ns), max(ns))
    ax.set_xlabel("array length n (int64)")
    ax.set_ylabel("time(iterative) / time(recursive)")
    ax.set_title("Discrepancy vs n (>1 → recursive faster)")
    ax.legend(loc="best")
    _finish_layout(fig)
    return fig


def fig_throughput_vs_n(run: Run):
    """Million elements sorted per second against n."""
    df = run.tables["timings"]
    fig, ax = plt.subplots(figsize=(6.2, 3.6), layout="constrained")
    for name, st in ((REC, REC_STYLE), (IT, IT_STYLE)):
        sub = df[df.algorithm == name].sort_values("n")
        if sub.empty:
            continue
        ax.plot(sub.n, sub.gflops, **st)
    ns = sorted(df.n.unique())
    _power_of_two_axis(ax, ns)
    _vlines(ax, _cache_boundaries(run), min(ns), max(ns))
    ax.set_xlabel("array length n (int64)")
    ax.set_ylabel("million elements / s")
    ax.set_title("Throughput vs n")
    ax.legend(loc="best")
    _finish_layout(fig)
    return fig


def fig_cache_misses(run: Run):
    """L1 miss rate and L2 misses (perf cache-misses on Zen 2) for both versions."""
    df = run.tables["cache-counters"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), layout="constrained")

    for name, st in ((REC, REC_STYLE), (IT, IT_STYLE)):
        sub = df[df.algorithm == name].sort_values("n")
        if sub.empty:
            continue
        axes[0].plot(sub.n, sub.l1_miss_rate_pct, **st)
        axes[1].plot(sub.n, sub.cache_misses_per_run, **st)

    ns = sorted(df.n.unique())
    for ax in axes:
        _power_of_two_axis(ax, ns)
        _vlines(ax, _cache_boundaries(run), min(ns), max(ns))
        ax.set_xlabel("n")

    axes[0].set_ylabel("L1 load miss rate (%)")
    axes[0].set_title("L1 data miss rate")
    axes[0].legend(loc="best", fontsize=7)

    _plain_log_yaxis(axes[1])
    axes[1].set_ylabel("misses per sort (perf cache-misses)")
    axes[1].set_title("L2 misses (Zen 2: cache-misses)")

    fig.suptitle("Cache counters: recursive vs iterative mergesort", fontsize=9)
    _finish_layout(fig)
    return fig


def fig_misses_per_element(run: Run):
    """L2 misses per element — highlights the extra full-array passes of iterative."""
    df = run.tables["cache-counters"]
    fig, ax = plt.subplots(figsize=(6.2, 3.6), layout="constrained")
    for name, st in ((REC, REC_STYLE), (IT, IT_STYLE)):
        sub = df[df.algorithm == name].sort_values("n")
        if sub.empty:
            continue
        ax.plot(sub.n, sub.cache_misses_per_run / sub.n, **st)
    ns = sorted(df.n.unique())
    _power_of_two_axis(ax, ns)
    _vlines(ax, _cache_boundaries(run), min(ns), max(ns))
    ax.set_xlabel("array length n (int64)")
    ax.set_ylabel("L2 misses / element")
    ax.set_title("Cache misses normalised by n")
    ax.legend(loc="best")
    _finish_layout(fig)
    return fig


def fig_l1_loads(run: Run):
    """L1 loads per sort — both versions should be in the same ballpark (same merge work)."""
    df = run.tables["cache-counters"]
    fig, ax = plt.subplots(figsize=(6.2, 3.6), layout="constrained")
    for name, st in ((REC, REC_STYLE), (IT, IT_STYLE)):
        sub = df[df.algorithm == name].sort_values("n")
        if sub.empty:
            continue
        ax.plot(sub.n, sub.l1_loads_per_run / sub.n, **st)
    ns = sorted(df.n.unique())
    _power_of_two_axis(ax, ns)
    ax.set_xlabel("array length n (int64)")
    ax.set_ylabel("L1 loads / element")
    ax.set_title("L1 loads per element (sanity: similar work)")
    ax.legend(loc="best")
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- diagrams

def diagram_bottom_up_passes():
    """Conceptual: iterative passes over powers of 2 vs recursive locality."""
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 4.2), layout="constrained",
                             gridspec_kw={"height_ratios": [1.1, 1]})

    # Top: one iterative outer-loop pass (width = 4 → merge pairs of blocks of 4)
    ax = axes[0]
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Iterative (bottom-up): each outer pass walks the whole array", fontsize=9, loc="left")

    for i in range(16):
        ax.add_patch(Rectangle((i, 1.2), 0.95, 0.9, facecolor="#EEEEEE", edgecolor="#333333", linewidth=0.6))
        ax.text(i + 0.45, 1.55, str(i), ha="center", va="center", fontsize=7)
    # brackets for width-4 merges
    for start, c in ((0, "#0072B2"), (8, "#56B4E9")):
        ax.annotate("", xy=(start + 7.9, 0.9), xytext=(start, 0.9),
                    arrowprops=dict(arrowstyle="-", color=c, lw=2))
        ax.text(start + 4, 0.35, f"merge [{start}:{start+4}) with [{start+4}:{start+8})",
                ha="center", fontsize=7, color=c)
    ax.text(8, 2.55, "pass with width = 4 (one of log₂ n passes over all of A)", ha="center", fontsize=8)

    # Bottom: recursive — once a subarray fits, stay on it
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    ax.set_title("Recursive (top-down): finish a fitting subarray while it stays in cache", fontsize=9, loc="left")

    def box(x, y, w, h, text, fc):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                    facecolor=fc, edgecolor="#333333", linewidth=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7)

    box(3.5, 3.0, 3.0, 0.7, "sort A[0:n)", "#DDEEFF")
    box(1.0, 1.8, 3.0, 0.7, "sort left half", "#BBDDFF")
    box(6.0, 1.8, 3.0, 0.7, "sort right half", "#BBDDFF")
    box(0.2, 0.4, 2.2, 0.7, "fits → stay", "#009E7333")
    box(2.6, 0.4, 2.2, 0.7, "fits → stay", "#009E7333")
    box(5.4, 0.4, 2.2, 0.7, "fits → stay", "#009E7333")
    box(7.8, 0.4, 2.0, 0.7, "fits → stay", "#009E7333")
    ax.plot([5.0, 2.5], [3.0, 2.5], color="#555555", lw=0.8)
    ax.plot([5.0, 7.5], [3.0, 2.5], color="#555555", lw=0.8)
    ax.plot([2.5, 1.3], [1.8, 1.1], color="#555555", lw=0.8)
    ax.plot([2.5, 3.7], [1.8, 1.1], color="#555555", lw=0.8)
    ax.plot([7.5, 6.5], [1.8, 1.1], color="#555555", lw=0.8)
    ax.plot([7.5, 8.8], [1.8, 1.1], color="#555555", lw=0.8)

    return fig


FIGURES = {
    "overview_time_vs_n": (fig_overview_time_vs_n, ["timings"]),
    "ratio_vs_n": (fig_ratio_vs_n, ["timings"]),
    "throughput_vs_n": (fig_throughput_vs_n, ["timings"]),
    "cache_misses": (fig_cache_misses, ["cache-counters"]),
    "misses_per_element": (fig_misses_per_element, ["cache-counters"]),
    "l1_loads": (fig_l1_loads, ["cache-counters"]),
}

DIAGRAMS = {
    "bottom_up_passes": diagram_bottom_up_passes,
}
