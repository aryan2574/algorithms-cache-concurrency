"""Figures for experiment 01 (matrix multiplication).

Every figure is a function `fig_<name>(run) -> matplotlib Figure`. FIGURES lists them with the
tables they need; make_figures.py skips a figure whose tables are not in the results folder.

Tables (file stems of the results folder): tile-sweep, oblivious, timings, cache-counters,
transpose, no-vectorization. A table in a sub-folder of the session is named
"<sub-folder>/<stem>", for example "large-n/timings". Columns of the timing tables
(tile-sweep, oblivious, timings, transpose): n, algorithm, tile_size, repetitions,
median_ms, gflops, checksum. For transpose, gflops holds million elements/s.
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from . import diagrams, style
from .data import NotApplicable, Run, best_per_group, fmt_bytes, matrix_bytes

TILE_VERSIONS = ("tiled", "tiled_col_major", "tiled_tile_wise")


# ----------------------------------------------------------------------------- helpers

def _finish_layout(fig, bottom: float = 0.04) -> None:
    """Leaves room at the bottom of the figure for the footnote written by style.save()."""
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.set(rect=(0, bottom, 1, 1 - bottom))


def _power_of_two_axis(ax, values, axis: str = "x") -> None:
    values = sorted(set(int(v) for v in values))
    if axis == "x":
        ax.set_xscale("log", base=2)
        ax.set_xticks(values)
        # useOffset would print a 1e6-style shift once the ticks get large
        fmt = mticker.ScalarFormatter()
        fmt.set_scientific(False)
        fmt.set_useOffset(False)
        ax.xaxis.set_major_formatter(fmt)
        ax.xaxis.set_minor_locator(mticker.NullLocator())
    else:
        ax.set_yscale("log", base=2)
        ax.set_yticks(values)
        fmt = mticker.ScalarFormatter()
        fmt.set_scientific(False)
        fmt.set_useOffset(False)
        ax.yaxis.set_major_formatter(fmt)
        ax.yaxis.set_minor_locator(mticker.NullLocator())


def _plain_log_yaxis(ax, subs=(1.0, 1.5, 2.0, 3.0, 5.0, 7.0)) -> None:
    """Log y-axis with ticks written as plain numbers (2, 5, 10, 20, 50 ...), not 2 x 10^0."""
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(mticker.LogLocator(base=10, subs=subs, numticks=30))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(mticker.NullLocator())


def _vlines(ax, positions: list[tuple[float, str]], lo: float, hi: float) -> None:
    """Dotted vertical lines with a small rotated label, only if inside [lo, hi]."""
    for x, label in positions:
        if lo <= x <= hi:
            ax.axvline(x, color="#888888", linestyle=":", linewidth=0.9, zorder=0)
            ax.text(x, 0.98, label, transform=ax.get_xaxis_transform(), rotation=90,
                    va="top", ha="right", fontsize=6, color="#555555")


def _row_wise_time(df, n: int) -> float | None:
    sub = df[(df.n == n) & (df.algorithm == "row_wise")]
    return float(sub.median_ms.iloc[0]) if len(sub) else None


def _stack(run: Run, *names: str) -> pd.DataFrame:
    """The named tables of a session (those that exist) one under the other. A configuration
    (n, algorithm, tile_size) already found in an earlier table is not taken again."""
    frames = [run.tables[name] for name in names if name in run.tables]
    table = pd.concat(frames, ignore_index=True)
    return table.drop_duplicates(subset=["n", "algorithm", "tile_size"], keep="first")


def _is_power_of_two(n: int) -> bool:
    return n > 0 and n & (n - 1) == 0


def _tiled_style(df) -> dict:
    tile = int(df[df.algorithm == "tiled"].tile_size.iloc[0])
    return dict(style.style_for("tiled"), label=f"tiled T={tile} (row-major)")


_VERSION_ORDER = ["row_wise", "col_wise", "tiled", "tiled_col_major", "tiled_tile_wise",
                  "oblivious_row_major", "oblivious_col_major", "oblivious_tile_wise"]
_KIND_ALPHA = {"plain": 0.35, "aware": 0.7, "oblivious": 1.0}
_KIND_HATCH = {"plain": "", "aware": "", "oblivious": "///"}


def _bar_style(version: str) -> dict:
    """Bar colour (layout), transparency and hatching (kind of algorithm) of a version."""
    if version == "naive":
        return {"facecolor": style.GREY, "alpha": 0.8, "hatch": "", "edgecolor": "white", "linewidth": 0.4}
    layout, kind = style.VERSIONS[version]
    return {"facecolor": style.LAYOUT_COLOR[layout], "alpha": _KIND_ALPHA[kind], "hatch": _KIND_HATCH[kind],
            "edgecolor": "white", "linewidth": 0.4}


def _kind_legend_handles(kinds=("plain", "aware", "oblivious")) -> list:
    return [Patch(facecolor="#555555", alpha=_KIND_ALPHA[k], hatch=_KIND_HATCH[k], edgecolor="white",
                  label=style.KIND_STYLE[k][2]) for k in kinds]


def _layout_legend_handles(layouts=("row", "col", "tile")) -> list:
    return [Patch(facecolor=style.LAYOUT_COLOR[l], label=style.LAYOUT_LABEL[l]) for l in layouts]


def _param_text(version: str, param) -> str:
    if param is None or (isinstance(param, float) and math.isnan(param)) or int(param) == 0:
        return ""
    if version in ("oblivious_row_major", "oblivious_col_major"):
        return f"base {int(param)}"
    return f"T={int(param)}"


def _large_sizes(df, minimum: int = 1024) -> list[int]:
    sizes = sorted(df.n.unique())
    return [n for n in sizes if n >= minimum] or sizes


# ----------------------------------------------------------------------------- access order

def fig_timings_gflops(run: Run):
    """GFLOPS against n for naive, row_wise and tiled (timings.csv)."""
    df = run.tables["timings"]
    sizes = sorted(df.n.unique())
    fig, ax = plt.subplots(figsize=(6.0, 3.8), layout="constrained")
    for v in ("naive", "row_wise", "tiled"):
        s = df[df.algorithm == v].sort_values("n")
        if s.empty:
            continue
        st = _tiled_style(df) if v == "tiled" else style.style_for(v)
        ax.plot(s.n, s.gflops, **st)
    marks = [(math.sqrt(size / 8), f"matrix = {name}") for name, size in run.machine.caches()]
    _vlines(ax, marks, min(sizes) / 1.3, max(sizes) * 1.3)
    _power_of_two_axis(ax, sizes)
    ax.set_xlim(min(sizes) / 1.25, max(sizes) * 1.25)
    ax.set_xlabel("matrix dimension n   (one matrix = 8 n^2 bytes)")
    ax.set_ylabel("GFLOPS (higher is better)")
    ax.set_ylim(bottom=0)
    ax.set_title("Speed against matrix size")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    _finish_layout(fig)
    return fig


def fig_transposed_b_vs_row_wise(run: Run):
    """Professor case b literally: A row-major × B stored as Bᵀ, plain and tiled, against row_wise / tiled."""
    df = run.tables["timings"]
    want = ["row_wise", "transposed_b", "tiled", "tiled_transposed_b"]
    if not set(want).issubset(set(df.algorithm)):
        raise NotApplicable("timings.csv needs row_wise, transposed_b, tiled, tiled_transposed_b")
    sizes = sorted(df.n.unique())
    fig, ax = plt.subplots(figsize=(6.4, 3.8), layout="constrained")
    order = ["naive", "transposed_b", "row_wise", "tiled_transposed_b", "tiled"]
    for v in order:
        sub = df[df.algorithm == v].sort_values("n")
        if sub.empty:
            continue
        ax.plot(sub.n, sub.gflops, **{**style.style_for(v), "markersize": 5})
    _power_of_two_axis(ax, sizes)
    ax.set_xlabel("matrix dimension n")
    ax.set_ylabel("GFLOPS (higher is better)")
    ax.set_ylim(bottom=0)
    ax.set_title("Store B transposed (ijk) vs reorder loops (row_wise), plain and tiled")
    ax.legend(frameon=False, fontsize=7)
    _finish_layout(fig)
    return fig


def fig_power_of_two(run: Run):
    """naive and row_wise at sizes that are and are not powers of two (timings.csv, plus large-n/
    of the same session). The work is the same; naive slows down much more at a power of two."""
    df = _stack(run, "timings", "large-n/timings")
    sizes = sorted(n for n in df[df.algorithm == "naive"].n.unique() if _row_wise_time(df, n))
    if all(_is_power_of_two(n) for n in sizes):
        raise NotApplicable("every size is a power of two; there is nothing to compare with")
    x = np.arange(len(sizes))
    pow2 = [_is_power_of_two(n) for n in sizes]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.0, 3.5), layout="constrained")

    for v in ("naive", "row_wise", "tiled"):
        s = df[df.algorithm == v].set_index("n").reindex(sizes)
        if s.gflops.notna().any():
            ax1.plot(x, s.gflops, **(_tiled_style(df) if v == "tiled" else style.style_for(v)))
    ax1.set_ylabel("GFLOPS (higher is better)")
    ax1.set_ylim(bottom=0)
    ax1.set_title("Speed at each matrix size")
    ax1.legend(frameon=False, fontsize=7, loc="center left")

    ratio = [float(df[(df.n == n) & (df.algorithm == "naive")].median_ms.iloc[0]) / _row_wise_time(df, n)
             for n in sizes]
    ax2.bar(x, ratio, 0.7, color=[style.VERMILLION if p else style.BLUE for p in pow2])
    for xi, r in zip(x, ratio):
        ax2.text(xi, r, f"{r:.1f}x", ha="center", va="bottom", fontsize=7)
    ax2.set_ylim(0, max(ratio) * 1.15)
    ax2.set_ylabel("time(naive) / time(row_wise)")
    ax2.set_title("How many times slower naive is than row_wise")
    ax2.legend(handles=[Patch(color=style.VERMILLION, label="n is a power of two"),
                        Patch(color=style.BLUE, label="n is not a power of two")],
               frameon=False, loc="upper left")

    for ax in (ax1, ax2):
        ax.set_xticks(x, [str(n) for n in sizes])
        for label, p in zip(ax.get_xticklabels(), pow2):
            if p:
                label.set_color(style.VERMILLION)
                label.set_fontweight("bold")
        ax.set_xlabel("matrix dimension n")
        ax.grid(axis="x", visible=False)
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- all versions

def fig_ranking(run: Run):
    """All versions ranked by time at the large matrix sizes, each with its best parameter."""
    df = run.tables["oblivious"]
    sizes = _large_sizes(df)
    fig, axes = plt.subplots(len(sizes), 1, figsize=(7.2, 3.3 * len(sizes) + 0.6), squeeze=False,
                             layout="constrained")
    for ax, n in zip(axes[:, 0], sizes):
        sub = df[(df.n == n) & df.algorithm.isin(_VERSION_ORDER)]
        best = best_per_group(sub, ["algorithm"]).sort_values("median_ms", ascending=False)
        base = _row_wise_time(df, n)
        for i, row in enumerate(best.itertuples()):
            ax.barh(i, row.median_ms, 0.72, **_bar_style(row.algorithm))
            speed = f"{base / row.median_ms:.1f}x" if base else ""
            ax.text(row.median_ms, i, f"  {row.median_ms:.0f} ms   {speed}   {_param_text(row.algorithm, row.tile_size)}",
                    va="center", fontsize=7)
        ax.set_yticks(range(len(best)), [style.style_for(v)["label"] for v in best.algorithm])
        ax.set_xlim(0, best.median_ms.max() * 1.55)
        ax.grid(axis="y", visible=False)
        ax.set_title(f"n = {n}   (one matrix: {fmt_bytes(matrix_bytes(n))};  fastest at the top)", loc="left")
        ax.set_xlabel("median time (ms), shorter is better;  x = speed-up over row_wise")
    fig.legend(handles=_kind_legend_handles(), loc="outside upper center", ncol=3, frameon=False)
    _finish_layout(fig)
    return fig


def fig_gflops_vs_matrix_size(run: Run):
    """GFLOPS against matrix size for every version (best parameter), with the cache sizes marked."""
    df = run.tables["oblivious"]
    best = best_per_group(df, ["n", "algorithm"])
    sizes = sorted(best.n.unique())
    fig, ax = plt.subplots(figsize=(6.6, 4.0), layout="constrained")

    for v in _VERSION_ORDER:
        s = best[best.algorithm == v].sort_values("n")
        if not s.empty:
            ax.plot(s.n, s.gflops, **style.style_for(v))

    # matrix size = cache size  <=>  8 n^2 = cache  <=>  n = sqrt(cache / 8)
    marks = [(math.sqrt(size / 8), f"matrix = {name} ({fmt_bytes(size)})") for name, size in run.machine.caches()]
    _vlines(ax, marks, min(sizes) / 1.3, max(sizes) * 1.3)
    _power_of_two_axis(ax, sizes)
    ax.set_xlim(min(sizes) / 1.25, max(sizes) * 1.25)
    ax.set_xlabel("matrix dimension n   (one matrix = 8 n^2 bytes)")
    ax.set_ylabel("GFLOPS (higher is better)")
    ax.set_ylim(bottom=0)
    ax.set_title("Speed against matrix size (best parameter of each version)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- tile size

def fig_tile_size_vs_time(run: Run):
    """Median time against tile size, one panel per matrix size, one line per layout."""
    df = run.tables["tile-sweep"]
    sizes = sorted(df.n.unique())
    versions = [v for v in TILE_VERSIONS if v in set(df.algorithm)]
    ncols = 2 if len(sizes) > 1 else 1
    nrows = math.ceil(len(sizes) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(6.6, 2.7 * nrows + 0.6), sharex=True,
                             squeeze=False, layout="constrained")
    tile_sizes = sorted(df[df.algorithm.isin(versions)].tile_size.unique())

    for ax, n in zip(axes.flat, sizes):
        sub = df[df.n == n]
        for v in versions:
            s = sub[sub.algorithm == v].sort_values("tile_size")
            if s.empty:
                continue
            st = style.style_for(v)
            ax.plot(s.tile_size, s.median_ms, **st)
            best = s.loc[s.median_ms.idxmin()]
            ax.plot([best.tile_size], [best.median_ms], marker="*", markersize=12, linestyle="none",
                    color=st["color"], markeredgecolor="black", zorder=5)
        base = _row_wise_time(sub, n)
        if base is not None:
            ax.axhline(base, color=style.GREY, linestyle="--", linewidth=1.1)
        # tile size at which three T x T tiles of double (A, B and C tile) fill a cache level
        fits = [(math.sqrt(size / 24), f"3 tiles = {name}") for name, size in run.machine.caches()]
        _vlines(ax, fits, min(tile_sizes) / 1.3, max(tile_sizes) * 1.3)
        _plain_log_yaxis(ax)
        _power_of_two_axis(ax, tile_sizes)
        ax.set_title(f"n = {n}  (one matrix: {fmt_bytes(matrix_bytes(n))})")
        ax.set_ylabel("median time (ms)")
    for ax in axes.flat[len(sizes):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("tile size T")

    handles = [Line2D([], [], **{k: v for k, v in style.style_for(v).items()}) for v in versions]
    labels = [style.style_for(v)["label"] for v in versions]
    handles += [Line2D([], [], color=style.GREY, linestyle="--"),
                Line2D([], [], marker="*", color="#999999", markeredgecolor="black", linestyle="none", markersize=11)]
    labels += ["row_wise (no tiling)", "best tile size"]
    fig.legend(handles, labels, loc="outside upper center", ncol=3, frameon=False)
    _finish_layout(fig)
    return fig


def fig_tile_fit_regimes(run: Run):
    """Speed against the memory the three tiles need, with the cache levels shaded: what happens
    when the tiles fit L1, fit L2, fit L3, or do not fit at all."""
    df = run.tables["tile-sweep"]
    versions = [v for v in ("tiled", "tiled_tile_wise") if v in set(df.algorithm)]
    sizes = sorted(df.n.unique())
    tile_sizes = sorted(df[df.algorithm.isin(versions)].tile_size.unique())
    lo, hi = 24 * min(tile_sizes) ** 2 / 1.6, 24 * max(tile_sizes) ** 2 * 1.6
    caches = run.machine.caches()
    edges = [lo] + [size for _, size in caches] + [hi]
    names = [f"fit {name}" for name, _ in caches] + ["> L3"]
    tints = ["#E3EEF8", "#E6F4EA", "#FFF4D9", "#F9E3E3"]

    ncols = 2 if len(sizes) > 1 else 1
    nrows = math.ceil(len(sizes) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(7.2, 2.9 * nrows + 0.6), sharex=True, squeeze=False,
                             layout="constrained")
    for ax, n in zip(axes.flat, sizes):
        sub = df[df.n == n]
        for a, b, tint in zip(edges[:-1], edges[1:], tints):
            ax.axvspan(max(a, lo), min(b, hi), color=tint, zorder=0, linewidth=0)
        for v in versions:
            s = sub[sub.algorithm == v].sort_values("tile_size")
            ax.plot(24 * s.tile_size ** 2, s.gflops, **style.style_for(v))
            if v == versions[0]:
                for t, x, y in zip(s.tile_size, 24 * s.tile_size ** 2, s.gflops):
                    ax.annotate(f"{int(t)}", (x, y), textcoords="offset points", xytext=(0, 5),
                                ha="center", fontsize=5.5, color="#333333")
        base = sub[sub.algorithm == "row_wise"]
        if len(base):
            ax.axhline(float(base.gflops.iloc[0]), color=style.GREY, linestyle="--", linewidth=1.1)
        ax.set_xscale("log")
        ax.set_xlim(lo, hi)
        ticks = [1024 * 16 ** k for k in range(0, 4) if lo <= 1024 * 16 ** k <= hi]
        ax.set_xticks(ticks, [fmt_bytes(t) for t in ticks])
        ax.xaxis.set_minor_locator(mticker.NullLocator())
        ax.set_ylim(bottom=0)
        ax.set_title(f"n = {n}", loc="left")
        ax.set_ylabel("GFLOPS")
        ax.grid(False)
    top_row = axes[0] if nrows else []
    for ax in top_row:
        for a, b, name in zip(edges[:-1], edges[1:], names):
            a, b = max(a, lo), min(b, hi)
            if a < b:
                ax.text(math.sqrt(a * b), 1.0, name, transform=ax.get_xaxis_transform(), ha="center",
                        va="bottom", fontsize=6, color="#555555")
    for ax in axes.flat[len(sizes):]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.set_xlabel("memory of the 3 tiles A, B, C (24 T^2 bytes)")

    handles = [Line2D([], [], **style.style_for(v)) for v in versions] + [Line2D([], [], color=style.GREY, linestyle="--"),
                                                                           Line2D([], [], linestyle="none")]
    labels = [style.style_for(v)["label"] for v in versions] + ["row_wise (no tiling)",
                                                                  "numbers on the line = tile size T"]
    fig.legend(handles, labels, loc="outside upper center", ncol=2, frameon=False)
    _finish_layout(fig, bottom=0.05)
    return fig


def fig_l3_sweep(run: Run):
    """row_wise and tiled from n = 512 to 1000 (l3-sweep/ of a session, n = 512 from timings.csv):
    tiling starts to pay off when one matrix no longer fits in L3."""
    df = _stack(run, "l3-sweep/timings", "timings")
    df = df[df.algorithm.isin(["row_wise", "tiled"]) & (df.n >= 512) & (df.n <= 1000)]
    sizes = sorted(df.n.unique())
    fig, ax = plt.subplots(figsize=(6.4, 3.6), layout="constrained")
    for v in ("row_wise", "tiled"):
        s = df[df.algorithm == v].sort_values("n")
        ax.plot(s.n, s.gflops, **(_tiled_style(df) if v == "tiled" else style.style_for(v)))
    for n in sizes:
        tiled = df[(df.n == n) & (df.algorithm == "tiled")]
        base = _row_wise_time(df, n)
        if len(tiled) and base:
            ax.annotate(f"{base / float(tiled.median_ms.iloc[0]):.1f}x", (n, float(tiled.gflops.iloc[0])),
                        textcoords="offset points", xytext=(0, 6), ha="center", fontsize=6.5)
    # one matrix = L3  <=>  8 n^2 = L3; the label goes at the bottom, the speed-ups are at the top
    edge = math.sqrt(run.machine.l3 / 8)
    ax.axvline(edge, color="#888888", linestyle=":", linewidth=0.9, zorder=0)
    ax.text(edge, 0.02, f"one matrix = L3 ({fmt_bytes(run.machine.l3)})", transform=ax.get_xaxis_transform(),
            rotation=90, va="bottom", ha="right", fontsize=6, color="#555555")
    ax.set_xlabel("matrix dimension n")
    ax.set_ylabel("GFLOPS (higher is better)")
    ax.set_ylim(0, df.gflops.max() * 1.2)
    ax.set_title("Where tiling starts to pay off (numbers: speed-up of tiled over row_wise)")
    ax.legend(frameon=False, loc="lower left")
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- cache-oblivious

def fig_oblivious_vs_aware(run: Run):
    """Best cache-oblivious time against best cache-aware time for each layout and matrix size."""
    df = run.tables["oblivious"]
    sizes = sorted(df.n.unique())
    layouts = ["row", "col", "tile"]
    fig, ax = plt.subplots(figsize=(6.6, 3.6), layout="constrained")
    width = 0.26
    for gi, n in enumerate(sizes):
        for li, layout in enumerate(layouts):
            aware = df[(df.n == n) & (df.algorithm == style.VERSION_OF[(layout, "aware")])]
            obl = df[(df.n == n) & (df.algorithm == style.VERSION_OF[(layout, "oblivious")])]
            if aware.empty or obl.empty:
                continue
            ratio = float(aware.median_ms.min()) / float(obl.median_ms.min())
            x = gi + (li - 1) * width
            ax.bar(x, ratio, width * 0.92, color=style.LAYOUT_COLOR[layout], alpha=0.5 if n <= 256 else 1.0)
            ax.text(x, ratio + 0.01, f"{ratio:.2f}", ha="center", va="bottom", fontsize=6.5)
    ax.axhline(1.0, color="black", linewidth=1)
    ax.axhspan(1 - style.NOISE_BAND, 1 + style.NOISE_BAND, color="#BBBBBB", alpha=0.35, zorder=0)
    ax.set_xticks(range(len(sizes)), [f"n={n}" + ("\n(unreliable)" if n <= 256 else "") for n in sizes])
    ax.grid(axis="x", visible=False)
    ax.set_ylim(0.6, max(1.25, ax.get_ylim()[1]))
    ax.set_ylabel("time(best cache-aware) / time(best cache-oblivious)\n(>1: cache-oblivious is faster)")
    ax.set_title("Cache-oblivious without tuning against tuned cache-aware")
    handles = _layout_legend_handles() + [Patch(facecolor="#BBBBBB", alpha=0.6, label="noise (+-10%)")]
    ax.legend(handles=handles, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- hardware counters and compiler

def _counter_frame(df, tile: int | None = None):
    """The cache-counters rows to draw, and a note naming the tile size used.

    A counters session may hold several tile sizes per version (column tile_size). One figure shows
    one of them (default: the largest, which was the fastest in the timing sweep); the versions without
    a parameter (tile_size 0) are always included."""
    note = ""
    tiles = sorted(int(t) for t in df.tile_size.unique() if t > 0)
    if tiles:
        chosen = tile if tile in tiles else max(tiles)
        df = df[(df.tile_size == 0) | (df.tile_size == chosen)]
        note = f"tile size / smallest recursion block = {chosen} for the cache-aware and cache-oblivious versions"
    return df, note


def _misses_label(run: Run) -> str:
    """What perf's generic cache-misses event counts: L2 misses on AMD, last-level misses on Intel."""
    return "L2 misses" if "AMD" in run.machine.model else "last-level cache misses"


def fig_cache_misses(run: Run):
    """L1 miss rate, L1 misses per multiply-add and perf cache-misses per version (cache-counters.csv,
    plus large-n/ of the same session)."""
    df, note = _counter_frame(_stack(run, "cache-counters", "large-n/cache-counters"))
    sizes = sorted(df.n.unique())
    order = ["naive"] + _VERSION_ORDER
    versions = [v for v in order if v in set(df.algorithm)]
    fig, axes = plt.subplots(1, 3, figsize=(10.0 if len(versions) <= 4 else 12.5, 3.9), layout="constrained")
    ax1, ax2, ax3 = axes
    width = 0.8 / len(versions)
    many = len(versions) * len(sizes) > 15
    for k, v in enumerate(versions):
        xs, rate, per_fma, misses = [], [], [], []
        for i, n in enumerate(sizes):
            row = df[(df.n == n) & (df.algorithm == v)]
            if row.empty:
                continue
            xs.append(i + (k - (len(versions) - 1) / 2) * width)
            rate.append(float(row.l1_miss_rate_pct.iloc[0]))
            per_fma.append(float(row.l1_load_misses_per_run.iloc[0]) / float(n) ** 3)
            misses.append(float(row.cache_misses_per_run.iloc[0]))
        bar = _bar_style(v)
        ax1.bar(xs, rate, width * 0.92, **bar)
        ax2.bar(xs, per_fma, width * 0.92, **bar)
        ax3.bar(xs, misses, width * 0.92, **bar)
        for x, value in zip(xs, rate):
            ax1.text(x, value + 1, f"{value:.0f}%" if not many else f"{value:.0f}", ha="center", va="bottom",
                     fontsize=6 if many else 7)
        for x, value in zip(xs, per_fma):
            ax2.text(x, value * 1.02, f"{value:.2f}", ha="center", va="bottom", fontsize=5.5 if many else 7,
                     rotation=90 if many else 0)
    for ax in axes:
        ax.set_xticks(range(len(sizes)), [str(n) for n in sizes])
        ax.set_xlabel("matrix dimension n")
        ax.grid(axis="x", visible=False)
    misses_label = _misses_label(run)
    ax1.set_ylabel("L1 data cache load miss rate (%)")
    ax1.set_ylim(0, max(80, df.l1_miss_rate_pct.max() * 1.12))
    ax2.set_ylabel("L1 load misses per multiply-add")
    ax2.set_ylim(0, df.l1_load_misses_per_run.div(df.n.astype(float) ** 3).max() * 1.25)
    ax3.set_yscale("log")
    ax3.set_ylabel(f"{misses_label} per multiplication (perf cache-misses)")
    positive = df.cache_misses_per_run[df.cache_misses_per_run > 0]
    ax3.set_ylim(bottom=10 ** math.floor(math.log10(positive.min())) if len(positive) else 1)  # bars start here (log scale)
    ax1.set_title("L1 miss rate")
    ax2.set_title("L1 misses per multiply-add")
    ax3.set_title(f"{misses_label.capitalize()} (log scale)")
    handles = [Patch(label=style.style_for(v)["label"], **_bar_style(v)) for v in versions]
    fig.legend(handles=handles, loc="outside upper center", ncol=min(len(handles), 5), frameon=False)
    if note:
        fig.text(0.5, 0.045, note, ha="center", fontsize=6.5, color="#555555")
    _finish_layout(fig, bottom=0.075 if note else 0.04)
    return fig


def fig_vectorization(run: Run):
    """Time with and without SIMD auto-vectorisation (timings.csv + no-vectorization-<n>.csv)."""
    nov = run.tables["no-vectorization"]
    n = int(nov.n.iloc[0])
    with_simd = run.tables["timings"]
    with_simd = with_simd[with_simd.n == n].set_index("algorithm").median_ms
    versions = [v for v in ("naive", "row_wise", "tiled") if v in set(nov.algorithm) and v in with_simd.index]
    without = nov.set_index("algorithm").median_ms

    fig, ax = plt.subplots(figsize=(5.6, 3.6), layout="constrained")
    width = 0.36
    for i, v in enumerate(versions):
        ax.bar(i - width / 2, with_simd[v], width * 0.92, color=style.BLUE, label="with auto-vectorisation" if i == 0 else None)
        ax.bar(i + width / 2, without[v], width * 0.92, color=style.VERMILLION, label="without (-fno-tree-vectorize)" if i == 0 else None)
        ax.text(i - width / 2, with_simd[v] * 1.08, f"{with_simd[v]:.0f}", ha="center", fontsize=7)
        ax.text(i + width / 2, without[v] * 1.08, f"{without[v]:.0f}", ha="center", fontsize=7)
    _plain_log_yaxis(ax)
    ax.set_xticks(range(len(versions)), versions)
    ax.set_ylim(top=ax.get_ylim()[1] * 2.2)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("median time (ms, log scale)")
    ax.set_title(f"Cache or SIMD? n = {n}")
    ax.legend(frameon=False, loc="upper right")
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- transposition

def fig_transpose_cache_misses(run: Run):
    """Cache counters for transposition: L1 miss rate, L1 misses per element, L2 misses.
    Unlike multiplication, work is n^2 copies, so the middle panel is per element not per FMA.
    Do not use _counter_frame here: that keeps only the largest tile size, but T=16 is fastest."""
    df = _stack(run, "cache-counters")
    sizes = sorted(df.n.unique())
    order = ["transpose_naive", "transpose_tiled", "transpose_oblivious"]
    versions = [v for v in order if v in set(df.algorithm)]
    if len(versions) < 2:
        raise NotApplicable("need at least two transpose versions in cache-counters.csv")

    hatch = {"transpose_naive": "xx", "transpose_tiled": "", "transpose_oblivious": "//"}
    preferred = 16  # best in the timing sweep
    picked = []
    for v in versions:
        sub = df[df.algorithm == v]
        if v == "transpose_naive":
            picked.append(sub)
            continue
        rows = []
        for _, g in sub.groupby("n"):
            if (g.tile_size == preferred).any():
                rows.append(g[g.tile_size == preferred].iloc[0])
            else:
                rows.append(g.loc[g.cache_misses_per_run.idxmin()])
        picked.append(pd.DataFrame(rows))
    plot_df = pd.concat(picked, ignore_index=True)
    note = f"parameter = {preferred} (best in the timing sweep)"

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.9), layout="constrained")
    ax1, ax2, ax3 = axes
    width = 0.8 / len(versions)
    for k, v in enumerate(versions):
        xs, rate, per_el, misses = [], [], [], []
        for i, n in enumerate(sizes):
            row = plot_df[(plot_df.n == n) & (plot_df.algorithm == v)]
            if row.empty:
                continue
            xs.append(i + (k - (len(versions) - 1) / 2) * width)
            rate.append(float(row.l1_miss_rate_pct.iloc[0]))
            per_el.append(float(row.l1_load_misses_per_run.iloc[0]) / float(n) ** 2)
            misses.append(float(row.cache_misses_per_run.iloc[0]))
        bar = {
            "color": style.style_for(v)["color"],
            "hatch": hatch[v],
            "edgecolor": "black",
            "linewidth": 0.4,
        }
        ax1.bar(xs, rate, width * 0.92, **bar)
        ax2.bar(xs, per_el, width * 0.92, **bar)
        ax3.bar(xs, misses, width * 0.92, **bar)
        for x, value in zip(xs, rate):
            ax1.text(x, value + 1, f"{value:.0f}%", ha="center", va="bottom", fontsize=7)
    for ax in axes:
        ax.set_xticks(range(len(sizes)), [str(n) for n in sizes])
        ax.set_xlabel("matrix dimension n")
        ax.grid(axis="x", visible=False)
    misses_label = _misses_label(run)
    ax1.set_ylabel("L1 data cache load miss rate (%)")
    ax1.set_ylim(0, max(80, float(plot_df.l1_miss_rate_pct.max()) * 1.15))
    ax2.set_ylabel("L1 load misses per element")
    ax2.set_ylim(0, float(plot_df.l1_load_misses_per_run.div(plot_df.n.astype(float) ** 2).max()) * 1.25)
    ax3.set_yscale("log")
    ax3.set_ylabel(f"{misses_label} per transpose (perf cache-misses)")
    positive = plot_df.cache_misses_per_run[plot_df.cache_misses_per_run > 0]
    ax3.set_ylim(bottom=10 ** math.floor(math.log10(positive.min())) if len(positive) else 1)
    ax1.set_title("L1 miss rate")
    ax2.set_title("L1 misses per element")
    ax3.set_title(f"{misses_label.capitalize()} (log scale)")
    handles = [
        Patch(facecolor=style.style_for(v)["color"], hatch=hatch[v], edgecolor="black",
              label=style.style_for(v)["label"])
        for v in versions
    ]
    fig.legend(handles=handles, loc="outside upper center", ncol=3, frameon=False)
    if note:
        fig.text(0.5, 0.045, note, ha="center", fontsize=6.5, color="#555555")
    _finish_layout(fig, bottom=0.075 if note else 0.04)
    return fig


def fig_transpose_vs_n(run: Run):
    """Out-of-place transposition: naive loops vs best tiled vs best oblivious against n.
    The sixth CSV column is Melem/s for these versions."""
    df = run.tables["transpose"]
    needed = {"transpose_naive", "transpose_tiled", "transpose_oblivious"}
    if not needed.issubset(set(df.algorithm)):
        raise NotApplicable("transpose.csv needs transpose_naive, transpose_tiled and transpose_oblivious")

    naive = df[df.algorithm == "transpose_naive"].set_index("n")
    best = best_per_group(df[df.algorithm != "transpose_naive"], ["n", "algorithm"])

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6), layout="constrained")

    ax = axes[0]
    ax.plot(naive.index, naive.median_ms, **{**style.style_for("transpose_naive"), "markersize": 5})
    for version in ("transpose_tiled", "transpose_oblivious"):
        sub = best[best.algorithm == version].sort_values("n")
        ax.plot(sub.n, sub.median_ms, **{**style.style_for(version), "markersize": 5})
        # The same CSV column is a tile size for the tiled copy and the recursion
        # cutoff for the oblivious copy. They are not the same parameter.
        tag = "base" if version == "transpose_oblivious" else "T"
        dy = 8 if version == "transpose_oblivious" else -9
        for row in sub.itertuples():
            ax.annotate(f"{tag}={int(row.tile_size)}", (row.n, row.median_ms), textcoords="offset points",
                        xytext=(4, dy), fontsize=6, color=style.style_for(version)["color"])
    _power_of_two_axis(ax, list(naive.index), "x")
    ax.set_yscale("log")
    ax.set_xlabel("matrix size n")
    ax.set_ylabel("median time (ms, log scale)")
    ax.set_title("Transpose time vs n (best parameter per version)")
    ax.legend(frameon=False, fontsize=7)

    ax = axes[1]
    for version in ("transpose_tiled", "transpose_oblivious"):
        sub = best[best.algorithm == version].sort_values("n")
        speedup = [naive.loc[n].median_ms / t for n, t in zip(sub.n, sub.median_ms)]
        ax.plot(sub.n, speedup, **{**style.style_for(version), "markersize": 5})
    ax.axhline(1.0, color="black", linewidth=0.8)
    ax.axhspan(1 - style.NOISE_BAND, 1 + style.NOISE_BAND, color="#BBBBBB", alpha=0.35, zorder=0)
    _power_of_two_axis(ax, list(naive.index), "x")
    ax.set_xlabel("matrix size n")
    ax.set_ylabel("speed-up over transpose_naive")
    ax.set_title("Recursive / tiled against two nested loops")
    ax.legend(frameon=False, fontsize=7)
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- quality of the measurement

def fig_noise_check(run: Run):
    """How repeatable is a measurement: the same configuration measured in tile-sweep.csv and in
    oblivious.csv (two separate passes of the same session)."""
    a, b = run.tables["tile-sweep"], run.tables["oblivious"]
    merged = a.merge(b, on=["n", "algorithm", "tile_size"], suffixes=("_first", "_second"))
    merged = merged[merged.algorithm.isin(style.VERSIONS)]
    if merged.empty:
        raise NotApplicable("tile-sweep.csv and oblivious.csv share no configuration")
    merged = merged.assign(diff=100 * (merged.median_ms_second - merged.median_ms_first) / merged.median_ms_first)
    sizes = sorted(merged.n.unique())

    fig, ax = plt.subplots(figsize=(6.4, 3.6), layout="constrained")
    for gi, n in enumerate(sizes):
        sub = merged[merged.n == n].reset_index(drop=True)
        offsets = np.linspace(-0.3, 0.3, max(len(sub), 2))[: len(sub)]
        for off, row in zip(offsets, sub.itertuples()):
            layout, kind = style.VERSIONS[row.algorithm]
            ax.plot(gi + off, row.diff, marker=style.KIND_STYLE[kind][1], color=style.LAYOUT_COLOR[layout],
                    linestyle="none", markersize=5)
    ax.axhline(0, color="black", linewidth=1)
    ax.axhspan(-100 * style.NOISE_BAND, 100 * style.NOISE_BAND, color="#BBBBBB", alpha=0.35, zorder=0)
    ax.set_xticks(range(len(sizes)), [f"n={n}" for n in sizes])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("difference between the two measurements (%)")
    ax.set_title("Repeatability: same configuration, measured twice in the same session")
    big = merged[merged.n >= 512]
    note = (f"{len(merged)} pairs; median |difference| {merged['diff'].abs().median():.1f}%"
            + (f", {big['diff'].abs().median():.1f}% for n >= 512" if len(big) else ""))
    ax.text(0.01, 0.02, note, transform=ax.transAxes, fontsize=7, color="#444444")
    present = {style.VERSIONS[v][0] for v in merged.algorithm}
    handles = _layout_legend_handles([l for l in ("row", "col", "tile") if l in present]) + [
        Line2D([], [], color="#444444", marker=style.KIND_STYLE[k][1], linestyle="none", label=style.KIND_STYLE[k][2])
        for k in ("plain", "aware")]
    ax.legend(handles=handles, frameon=False, ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=7)
    _finish_layout(fig)
    return fig


# name -> (function, tables needed). The name starts with the topic so the files sort by topic.
FIGURES = {
    # access order: naive (i,j,k) against row_wise (i,k,j)
    "overview_baseline": (fig_timings_gflops, ["timings"]),
    "access_power_of_two": (fig_power_of_two, ["timings"]),
    "transposed_b_vs_row_wise": (fig_transposed_b_vs_row_wise, ["timings"]),
    # all versions
    "overview_ranking": (fig_ranking, ["oblivious"]),
    "overview_gflops_vs_n": (fig_gflops_vs_matrix_size, ["oblivious"]),
    # tile size
    "tile_size_vs_time": (fig_tile_size_vs_time, ["tile-sweep"]),
    "tile_fit_regimes": (fig_tile_fit_regimes, ["tile-sweep"]),
    "tile_l3_sweep": (fig_l3_sweep, ["l3-sweep/timings"]),
    # cache-oblivious
    "oblivious_vs_aware": (fig_oblivious_vs_aware, ["oblivious"]),
    # transposition (O(n^2))
    "transpose_vs_n": (fig_transpose_vs_n, ["transpose"]),
    "transpose_cache_misses": (fig_transpose_cache_misses, ["cache-counters"]),
    # hardware counters and compiler
    "cache_misses": (fig_cache_misses, ["cache-counters"]),
    "simd_vectorization": (fig_vectorization, ["timings", "no-vectorization"]),
    # quality of the measurement
    "quality_noise_check": (fig_noise_check, ["tile-sweep", "oblivious"]),
}

DIAGRAMS = diagrams.DIAGRAMS
