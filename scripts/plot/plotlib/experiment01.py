"""Figures for experiment 01 (matrix multiplication).

Every figure is a function `fig_<name>(run) -> matplotlib Figure`. FIGURES lists them with the
tables they need; make_figures.py skips a figure whose tables are not in the results folder.

Tables (file stems of the results folder): tile-sweep, oblivious, timings, cache-counters,
no-vectorization. Columns of the first four timing tables:
n, algorithm, tile_size, repetitions, median_ms, gflops, checksum.
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.colors import Normalize, to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from . import diagrams, style
from .data import NotApplicable, Run, best_per_group, fmt_bytes, matrix_bytes, speed_table

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
        ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
        ax.xaxis.set_minor_locator(mticker.NullLocator())
    else:
        ax.set_yscale("log", base=2)
        ax.set_yticks(values)
        ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
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


# ----------------------------------------------------------------------------- tile sweep

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


def fig_speedup_heatmap(run: Run):
    """Speed-up over row_wise for every tile size and matrix size, one panel per layout."""
    df = run.tables["tile-sweep"]
    versions = [v for v in TILE_VERSIONS if v in set(df.algorithm)]
    sizes = sorted(df.n.unique())
    tile_sizes = sorted(df[df.algorithm.isin(versions)].tile_size.unique())

    fig, axes = plt.subplots(len(versions), 1, figsize=(6.6, 1.9 * len(versions) + 0.9),
                             squeeze=False, layout="constrained")
    norm = Normalize(vmin=-2.5, vmax=2.5)  # on log2(speed-up): 0.18x ... 5.7x
    cmap = plt.get_cmap("RdBu").copy()
    cmap.set_bad("#DDDDDD")

    image = None
    for ax, v in zip(axes[:, 0], versions):
        grid = np.full((len(sizes), len(tile_sizes)), np.nan)
        for i, n in enumerate(sizes):
            base = _row_wise_time(df, n)
            for j, t in enumerate(tile_sizes):
                s = df[(df.n == n) & (df.algorithm == v) & (df.tile_size == t)]
                if len(s) and base is not None:
                    grid[i, j] = base / float(s.median_ms.iloc[0])
        image = ax.imshow(np.ma.masked_invalid(np.log2(grid)), cmap=cmap, norm=norm, aspect="auto")
        ax.grid(False)
        ax.set_xticks(range(len(tile_sizes)), [str(t) for t in tile_sizes])
        ax.set_yticks(range(len(sizes)), [f"n={n}" for n in sizes])
        ax.set_title(style.style_for(v)["label"], loc="left")
        for i in range(len(sizes)):
            for j in range(len(tile_sizes)):
                value = grid[i, j]
                if np.isnan(value):
                    ax.text(j, i, "n/a", ha="center", va="center", fontsize=6.5, color="#777777")
                else:
                    dark = abs(math.log2(value)) > 1.6
                    ax.text(j, i, f"{value:.2f}x" if value < 10 else f"{value:.0f}x", ha="center", va="center",
                            fontsize=7, color="white" if dark else "black")
        for spine in ax.spines.values():
            spine.set_visible(False)
    axes[-1, 0].set_xlabel("tile size T")

    cbar = fig.colorbar(image, ax=axes[:, 0], shrink=0.8, pad=0.02)
    ticks = [-2, -1, 0, 1, 2]
    cbar.set_ticks(ticks, labels=[f"{2.0 ** t:g}x" for t in ticks])
    cbar.set_label("speed-up over row_wise\n(>1x faster, <1x slower)")
    _finish_layout(fig)
    return fig


def fig_tile_wise_vs_row_major(run: Run):
    """Time of the tile-wise layout divided by the row-major time at the same tile size."""
    df = run.tables["tile-sweep"]
    if not {"tiled", "tiled_tile_wise"} <= set(df.algorithm):
        raise NotApplicable("needs both tiled and tiled_tile_wise rows in tile-sweep.csv")
    sizes = [n for n in sorted(df.n.unique())]
    palette = [style.BLUE, style.VERMILLION, style.GREEN, style.PINK, style.SKY]
    fig, ax = plt.subplots(figsize=(6.0, 3.6), layout="constrained")
    tile_sizes = sorted(df[df.algorithm == "tiled_tile_wise"].tile_size.unique())

    for color, n in zip(palette, sizes):
        sub = df[df.n == n]
        row = sub[sub.algorithm == "tiled"].set_index("tile_size").median_ms
        tile = sub[sub.algorithm == "tiled_tile_wise"].set_index("tile_size").median_ms
        common = sorted(set(row.index) & set(tile.index))
        if not common:
            continue
        ratio = [tile[t] / row[t] for t in common]
        ax.plot(common, ratio, marker="o", color=color, label=f"n = {n}")

    ax.axhline(1.0, color="black", linewidth=1)
    ax.axhspan(1 - style.NOISE_BAND, 1 + style.NOISE_BAND, color="#BBBBBB", alpha=0.35, zorder=0)
    ax.text(0.99, 1 + style.NOISE_BAND * 0.55, "grey band: within the noise (+-10%)",
            transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=6.5, color="#555555")
    _power_of_two_axis(ax, tile_sizes)
    ax.set_xlabel("tile size T")
    ax.set_ylabel("time(tile-wise) / time(row-major)\n(<1: tile-wise layout is faster)")
    ax.set_title("Same loops and tile size, only the memory layout differs")
    ax.legend(frameon=False, ncol=2)
    _finish_layout(fig)
    return fig


# ----------------------------------------------------------------------------- layouts, aware vs oblivious

def fig_gflops_vs_matrix_size(run: Run):
    """GFLOPS against matrix size for every version (best parameter), with the cache sizes marked."""
    df = run.tables["oblivious"]
    best = best_per_group(df, ["n", "algorithm"])
    sizes = sorted(best.n.unique())
    fig, ax = plt.subplots(figsize=(6.6, 4.0), layout="constrained")

    order = ["row_wise", "col_wise", "tiled", "tiled_col_major", "tiled_tile_wise",
             "oblivious_row_major", "oblivious_col_major", "oblivious_tile_wise"]
    for v in order:
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


def _best_version_times(df, n: int) -> dict[tuple[str, str], tuple[float, int | None]]:
    """(layout, kind) -> (best median ms, parameter) at one matrix size."""
    result = {}
    for (layout, kind), version in style.VERSION_OF.items():
        s = df[(df.n == n) & (df.algorithm == version)]
        if s.empty:
            continue
        row = s.loc[s.median_ms.idxmin()]
        param = int(row.tile_size) if kind != "plain" else None
        result[(layout, kind)] = (float(row.median_ms), param)
    return result


def fig_speedup_bars(run: Run):
    """Speed-up over row_wise: three layouts x (plain, cache-aware, cache-oblivious), per size."""
    df = run.tables["oblivious"]
    all_sizes = sorted(df.n.unique())
    sizes = [n for n in all_sizes if n >= 1024] or all_sizes
    fig, axes = plt.subplots(1, len(sizes), figsize=(3.4 * len(sizes) + 0.6, 3.9), sharey=True,
                             squeeze=False, layout="constrained")
    layouts = ["row", "col", "tile"]
    kinds = ["plain", "aware", "oblivious"]
    alpha = {"plain": 0.35, "aware": 0.7, "oblivious": 1.0}
    hatch = {"plain": "", "aware": "", "oblivious": "///"}
    width = 0.26

    for ax, n in zip(axes[0], sizes):
        base = _row_wise_time(df, n)
        times = _best_version_times(df, n)
        for gi, layout in enumerate(layouts):
            for ki, kind in enumerate(kinds):
                if (layout, kind) not in times or base is None:
                    continue
                ms, param = times[(layout, kind)]
                speedup = base / ms
                x = gi + (ki - 1) * width
                # white hatch lines on the cache-oblivious bars (hatch takes the edge colour)
                ax.bar(x, speedup, width * 0.92, color=style.LAYOUT_COLOR[layout], alpha=alpha[kind],
                       hatch=hatch[kind], edgecolor="white", linewidth=0.4)
                ax.text(x, speedup + 0.04, f"{speedup:.1f}x", ha="center", va="bottom", fontsize=7)
                if param is not None:
                    ax.text(x, 0.06, f"{param}", ha="center", va="bottom", fontsize=6, color="white" if kind != "plain" else "black",
                            rotation=90)
        ax.axhline(1.0, color="black", linewidth=1)
        ax.axhspan(1 - style.NOISE_BAND, 1 + style.NOISE_BAND, color="#BBBBBB", alpha=0.35, zorder=0)
        ax.set_xticks(range(len(layouts)), [style.LAYOUT_LABEL[l] for l in layouts])
        ax.set_title(f"n = {n}")
        ax.grid(axis="x", visible=False)
    axes[0, 0].set_ylabel("speed-up over row_wise (row-major plain loops)")

    handles = [Patch(facecolor="#555555", alpha=alpha[k], hatch=hatch[k], label=style.KIND_STYLE[k][2]) for k in kinds]
    handles.append(Patch(facecolor="#BBBBBB", alpha=0.6, label="noise (+-10%)"))
    fig.legend(handles=handles, loc="outside upper center", ncol=4, frameon=False)
    fig.text(0.5, 0.045, "number inside a bar = best parameter: tile size, or smallest recursion block (row-/column-major oblivious)",
             ha="center", fontsize=6.5, color="#555555")
    _finish_layout(fig, bottom=0.075)
    return fig


def fig_oblivious_parameter(run: Run):
    """Does cache-oblivious depend on its parameter? Aware vs oblivious time for each parameter."""
    df = run.tables["oblivious"]
    all_sizes = sorted(df.n.unique())
    sizes = [n for n in all_sizes if n >= 1024] or all_sizes
    layouts = ["row", "col", "tile"]
    fig, axes = plt.subplots(len(sizes), len(layouts), figsize=(7.0, 2.4 * len(sizes) + 0.7),
                             sharex="col", squeeze=False, layout="constrained")
    params = sorted(df[df.tile_size > 0].tile_size.unique())

    for r, n in enumerate(sizes):
        for c, layout in enumerate(layouts):
            ax = axes[r, c]
            for kind in ("aware", "oblivious"):
                version = style.VERSION_OF[(layout, kind)]
                s = df[(df.n == n) & (df.algorithm == version)].sort_values("tile_size")
                if not s.empty:
                    ax.plot(s.tile_size, s.median_ms, **style.style_for(version))
            plain = style.VERSION_OF[(layout, "plain")] if (layout, "plain") in style.VERSION_OF else None
            if plain:
                p = df[(df.n == n) & (df.algorithm == plain)]
                if len(p):
                    ax.axhline(float(p.median_ms.iloc[0]), color=style.GREY, linestyle="--", linewidth=1.0)
            _power_of_two_axis(ax, params)
            ax.set_ylim(bottom=0)
            if r == 0:
                ax.set_title(style.LAYOUT_LABEL[layout])
            if c == 0:
                ax.set_ylabel(f"n = {n}\nmedian time (ms)")
    axes[-1][1].set_xlabel("parameter: tile size T  /  smallest recursion block (base)")

    handles = [Line2D([], [], color="#444444", linestyle="-", marker="o"),
               Line2D([], [], color="#444444", linestyle="--", marker="s"),
               Line2D([], [], color=style.GREY, linestyle="--")]
    fig.legend(handles, ["cache-aware (tile size)", "cache-oblivious", "plain loops (no parameter)"],
               loc="outside upper center", ncol=3, frameon=False)
    _finish_layout(fig, bottom=0.075)  # room for the x label and the footnote
    return fig


# ----------------------------------------------------------------------------- October session

def fig_timings_gflops(run: Run):
    """GFLOPS against n for naive, row_wise and tiled (timings.csv)."""
    df = run.tables["timings"]
    sizes = sorted(df.n.unique())
    fig, ax = plt.subplots(figsize=(6.0, 3.8), layout="constrained")
    for v in ("naive", "row_wise", "tiled"):
        s = df[df.algorithm == v].sort_values("n")
        if s.empty:
            continue
        st = style.style_for(v)
        if v == "tiled":
            tile = int(s.tile_size.iloc[0])
            st = dict(st, label=f"tiled T={tile} (row-major)")
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


def _counter_frame(run: Run, tile: int | None = None):
    """The cache-counters rows to draw, and a note naming the tile size used.

    A counters session may hold several tile sizes per version (column tile_size). One figure shows
    one of them (default: the largest, which was the fastest in the timing sweep); the versions without
    a parameter (tile_size 0) are always included."""
    df = run.tables["cache-counters"]
    note = ""
    if "tile_size" in df.columns:
        tiles = sorted(int(t) for t in df.tile_size.unique() if t > 0)
        if tiles:
            chosen = tile if tile in tiles else max(tiles)
            df = df[(df.tile_size == 0) | (df.tile_size == chosen)]
            note = f"tile size / smallest recursion block = {chosen} for the cache-aware and cache-oblivious versions"
    return df, note


def fig_cache_misses(run: Run):
    """L1 miss rate and last-level cache misses per version (cache-counters.csv)."""
    df, note = _counter_frame(run)
    sizes = sorted(df.n.unique())
    order = ["naive"] + _VERSION_ORDER
    versions = [v for v in order if v in set(df.algorithm)]
    fig, axes = plt.subplots(1, 3, figsize=(10.0 if len(versions) <= 4 else 12.5, 3.9), layout="constrained")
    ax1, ax2, ax3 = axes
    width = 0.8 / len(versions)
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
        many = len(versions) > 5
        for x, value in zip(xs, rate):
            ax1.text(x, value + 1, f"{value:.0f}%" if not many else f"{value:.0f}", ha="center", va="bottom",
                     fontsize=6 if many else 7)
        for x, value in zip(xs, per_fma):
            ax2.text(x, value * 1.02, f"{value:.2f}", ha="center", va="bottom", fontsize=5.5 if many else 7,
                     rotation=90 if many else 0)
    for ax in axes:
        ax.set_xticks(range(len(sizes)), [f"n = {n}" for n in sizes])
        ax.grid(axis="x", visible=False)
    ax1.set_ylabel("L1 data cache load miss rate (%)")
    ax1.set_ylim(0, max(80, df.l1_miss_rate_pct.max() * 1.12))
    ax2.set_ylabel("L1 load misses per multiply-add")
    ax2.set_ylim(0, df.l1_load_misses_per_run.div(df.n.astype(float) ** 3).max() * 1.25)
    ax3.set_yscale("log")
    ax3.set_ylabel("last-level cache misses per multiplication")
    positive = df.cache_misses_per_run[df.cache_misses_per_run > 0]
    ax3.set_ylim(bottom=10 ** math.floor(math.log10(positive.min())) if len(positive) else 1)  # bars start here (log scale)
    ax1.set_title("L1 miss rate")
    ax2.set_title("L1 misses per multiply-add")
    ax3.set_title("Last-level cache misses (log scale)")
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


# ----------------------------------------------------------------------------- more views of the same data

_VERSION_ORDER = ["row_wise", "col_wise", "tiled", "tiled_col_major", "tiled_tile_wise",
                  "oblivious_row_major", "oblivious_col_major", "oblivious_tile_wise"]
_KIND_ALPHA = {"plain": 0.35, "aware": 0.7, "oblivious": 1.0}
_KIND_HATCH = {"plain": "", "aware": "", "oblivious": "///"}


def _bar_style(version: str) -> dict:
    """Bar colour (layout), transparency and hatching (kind of algorithm) of a version."""
    if version == "naive":
        return {"color": style.GREY, "alpha": 0.8, "hatch": "", "edgecolor": "white", "linewidth": 0.4}
    layout, kind = style.VERSIONS[version]
    return {"color": style.LAYOUT_COLOR[layout], "alpha": _KIND_ALPHA[kind], "hatch": _KIND_HATCH[kind],
            "edgecolor": "white", "linewidth": 0.4}


def _kind_legend_handles(kinds=("plain", "aware", "oblivious")) -> list:
    return [Patch(facecolor="#555555", alpha=_KIND_ALPHA[k], hatch=_KIND_HATCH[k], edgecolor="white",
                  label=style.KIND_STYLE[k][2]) for k in kinds]


def _layout_legend_handles(layouts=("row", "col", "tile")) -> list:
    return [Patch(facecolor=style.LAYOUT_COLOR[l], label=style.LAYOUT_LABEL[l]) for l in layouts]


def _shade(color: str, level: int, levels: int):
    """The layout colour, lighter for low `level` (small parameter) and full strength for the highest."""
    r, g, b = to_rgb(color)
    mix = 0.6 * (1 - level / max(levels - 1, 1))
    return (r + (1 - r) * mix, g + (1 - g) * mix, b + (1 - b) * mix)


def _param_text(version: str, param) -> str:
    if param is None or (isinstance(param, float) and math.isnan(param)) or int(param) == 0:
        return ""
    if version in ("oblivious_row_major", "oblivious_col_major"):
        return f"base {int(param)}"
    return f"T={int(param)}"


def _large_sizes(df, minimum: int = 1024) -> list[int]:
    sizes = sorted(df.n.unique())
    return [n for n in sizes if n >= minimum] or sizes


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


def fig_time_vs_n(run: Run):
    """Time against matrix size on log-log axes, with the n^3 growth of the work as a guide."""
    df = run.tables["oblivious"]
    best = best_per_group(df, ["n", "algorithm"])
    sizes = sorted(best.n.unique())
    fig, ax = plt.subplots(figsize=(6.6, 4.0), layout="constrained")
    for v in _VERSION_ORDER:
        s = best[best.algorithm == v].sort_values("n")
        if not s.empty:
            ax.plot(s.n, s.median_ms, **style.style_for(v))
    anchor = best[(best.algorithm == "tiled_tile_wise") & (best.n == sizes[0])]
    if anchor.empty:
        anchor = best[best.n == sizes[0]].nsmallest(1, "median_ms")
    xs = np.array(sizes, dtype=float)
    ax.plot(xs, float(anchor.median_ms.iloc[0]) * (xs / sizes[0]) ** 3, color="black", linewidth=0.9,
            alpha=0.5, label="work grows as n^3 (guide)")
    _plain_log_yaxis(ax, subs=(1.0, 2.0, 5.0))
    _power_of_two_axis(ax, sizes)
    ax.set_xlim(min(sizes) / 1.2, max(sizes) * 1.2)
    ax.set_xlabel("matrix dimension n")
    ax.set_ylabel("median time (ms, log scale)")
    ax.set_title("Time against matrix size (best parameter of each version)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
    _finish_layout(fig)
    return fig


def fig_layout_algorithms(run: Run):
    """One panel per layout: plain, cache-aware and cache-oblivious at every parameter against n."""
    df = run.tables["oblivious"]
    sizes = sorted(df.n.unique())
    params = sorted(df[df.tile_size > 0].tile_size.unique())
    layouts = ["row", "col", "tile"]
    fig, axes = plt.subplots(1, 3, figsize=(10.0, 3.7), sharex=True, sharey=True, layout="constrained")
    for ax, layout in zip(axes, layouts):
        color = style.LAYOUT_COLOR[layout]
        plain = style.VERSION_OF.get((layout, "plain"))
        if plain:
            s = df[df.algorithm == plain].sort_values("n")
            ax.plot(s.n, s.gflops, color=color, linestyle=":", marker="x", linewidth=1.8)
        else:  # tile-wise has no plain-loops version: show the row-major baseline for reference
            s = df[df.algorithm == "row_wise"].sort_values("n")
            ax.plot(s.n, s.gflops, color=style.GREY, linestyle=":", marker="x", linewidth=1.2, alpha=0.7)
        for kind in ("aware", "oblivious"):
            version = style.VERSION_OF[(layout, kind)]
            for k, p in enumerate(params):
                s = df[(df.algorithm == version) & (df.tile_size == p)].sort_values("n")
                ax.plot(s.n, s.gflops, color=_shade(color, k, len(params)), linestyle=style.KIND_STYLE[kind][0],
                        marker=style.KIND_STYLE[kind][1], markersize=4)
        marks = [(math.sqrt(size / 8), f"matrix = {name}") for name, size in run.machine.caches()[1:]]
        _vlines(ax, marks, min(sizes) / 1.3, max(sizes) * 1.3)
        _power_of_two_axis(ax, sizes)
        ax.set_xlim(min(sizes) / 1.2, max(sizes) * 1.2)
        ax.set_title(style.LAYOUT_LABEL[layout])
        ax.set_xlabel("matrix dimension n")
    axes[0].set_ylabel("GFLOPS (higher is better)")
    axes[0].set_ylim(bottom=0)

    handles = [Line2D([], [], color="#444444", linestyle=":", marker="x"),
               Line2D([], [], color="#444444", linestyle="-", marker="o"),
               Line2D([], [], color="#444444", linestyle="--", marker="s")]
    labels = ["plain loops (grey in the tile-wise panel = row-major plain loops)", "cache-aware", "cache-oblivious"]
    for k, p in enumerate(params):
        handles.append(Patch(facecolor=_shade("#444444", k, len(params))))
        labels.append(f"tile size / base {p}")
    fig.legend(handles, labels, loc="outside upper center", ncol=3, frameon=False)
    _finish_layout(fig)
    return fig


def fig_layout_comparison(run: Run):
    """Same kind of algorithm, three layouts side by side (best parameter), for every matrix size."""
    df = run.tables["oblivious"]
    sizes = sorted(df.n.unique())
    kinds = [("plain", "plain loops"), ("aware", "cache-aware (best tile size)"),
             ("oblivious", "cache-oblivious (best parameter)")]
    layouts = ["row", "col", "tile"]
    fig, axes = plt.subplots(1, 3, figsize=(10.0, 3.6), sharey=True, layout="constrained")
    top = 0.0
    for ax, (kind, title) in zip(axes, kinds):
        present = [l for l in layouts if (l, kind) in style.VERSION_OF]
        width = 0.8 / len(present)
        for gi, n in enumerate(sizes):
            for li, layout in enumerate(present):
                s = df[(df.n == n) & (df.algorithm == style.VERSION_OF[(layout, kind)])]
                if s.empty:
                    continue
                gflops = float(s.gflops.max())
                top = max(top, gflops)
                x = gi + (li - (len(present) - 1) / 2) * width
                ax.bar(x, gflops, width * 0.92, color=style.LAYOUT_COLOR[layout])
                ax.text(x, gflops + 0.1, f"{gflops:.1f}", ha="center", va="bottom", fontsize=6)
        ax.set_xticks(range(len(sizes)), [f"n={n}" for n in sizes])
        ax.grid(axis="x", visible=False)
        ax.set_title(title)
    axes[0].set_ylabel("GFLOPS (higher is better)")
    axes[0].set_ylim(0, top * 1.12)
    fig.legend(handles=_layout_legend_handles(), loc="outside upper center", ncol=3, frameon=False)
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


def fig_cache_misses_vs_speed(run: Run):
    """Do fewer cache misses mean faster? GFLOPS against the counters, one point per version, one column
    per matrix size. The speeds come from this session's timing tables or, for a counters-only session,
    from the newest earlier session with an oblivious.csv (named at the bottom of the figure)."""
    counters, note = _counter_frame(run)
    found = speed_table(run)
    if found is None:
        raise NotApplicable("no timing table (oblivious.csv, tile-sweep.csv, timings.csv) to take the speed from")
    speed, source = found
    keys = ["n", "algorithm", "tile_size"] if "tile_size" in counters.columns else ["n", "algorithm"]
    merged = counters.merge(speed[["n", "algorithm", "tile_size", "gflops"]].drop_duplicates(keys), on=keys, how="inner")
    if merged.empty:
        raise NotApplicable("the counters and the timing tables share no version / size / tile size")
    merged = merged.assign(ll_per_fma=merged.cache_misses_per_run / merged.n.astype(float) ** 3)
    sizes = sorted(merged.n.unique())
    versions = [v for v in ["naive"] + _VERSION_ORDER if v in set(merged.algorithm)]

    fig, axes = plt.subplots(2, len(sizes), figsize=(3.3 * len(sizes) + 0.6, 6.0), sharey=True, sharex="row",
                             squeeze=False, layout="constrained")
    for c, n in enumerate(sizes):
        for row_index in (0, 1):
            ax = axes[row_index, c]
            for row in merged[merged.n == n].itertuples():
                x = row.l1_miss_rate_pct if row_index == 0 else row.ll_per_fma
                if x <= 0:
                    continue  # a log axis cannot show it; the counter was below its noise level
                st = style.style_for(row.algorithm)
                ax.plot(x, row.gflops, marker=st["marker"], color=st["color"], linestyle="none", markersize=7,
                        markeredgecolor="white", markeredgewidth=0.4)
            ax.set_ylim(bottom=0)
            if row_index == 0:
                ax.set_title(f"n = {n}")
                ax.set_xlabel("L1 data cache load miss rate (%)")
                ax.set_xlim(left=0)
            else:
                ax.set_xscale("log")
                ax.set_xlabel("last-level misses per multiply-add (log)")
        axes[0, c].sharey  # shared y axis, label only on the first column
    for row_index in (0, 1):
        axes[row_index, 0].set_ylabel("GFLOPS (higher is better)")

    handles = [Line2D([], [], linestyle="none", marker=style.style_for(v)["marker"], color=style.style_for(v)["color"],
                      markersize=7, label=style.style_for(v)["label"]) for v in versions]
    fig.legend(handles=handles, loc="outside upper center", ncol=min(len(handles), 4), frameon=False)
    notes = [note] if note else []
    if source != run.name:
        notes.append(f"GFLOPS from the timing session {source}; counters from {run.name}")
    if notes:
        fig.text(0.5, 0.045, "   |   ".join(notes), ha="center", fontsize=6.5, color="#555555")
    _finish_layout(fig, bottom=0.075 if notes else 0.04)
    return fig


# name -> (function, tables needed). The name starts with the topic so the files sort by topic.
FIGURES = {
    # overview: everything in one picture
    "overview_ranking": (fig_ranking, ["oblivious"]),
    "overview_gflops_vs_n": (fig_gflops_vs_matrix_size, ["oblivious"]),
    "overview_time_vs_n": (fig_time_vs_n, ["oblivious"]),
    "overview_speedup_bars": (fig_speedup_bars, ["oblivious"]),
    "overview_baseline": (fig_timings_gflops, ["timings"]),
    # storage layout
    "layout_algorithms": (fig_layout_algorithms, ["oblivious"]),
    "layout_comparison": (fig_layout_comparison, ["oblivious"]),
    "layout_tile_wise_vs_row_major": (fig_tile_wise_vs_row_major, ["tile-sweep"]),
    # tile size
    "tile_size_vs_time": (fig_tile_size_vs_time, ["tile-sweep"]),
    "tile_fit_regimes": (fig_tile_fit_regimes, ["tile-sweep"]),
    "tile_speedup_heatmap": (fig_speedup_heatmap, ["tile-sweep"]),
    # cache-oblivious
    "oblivious_parameter": (fig_oblivious_parameter, ["oblivious"]),
    "oblivious_vs_aware": (fig_oblivious_vs_aware, ["oblivious"]),
    # hardware counters and compiler
    "cache_misses": (fig_cache_misses, ["cache-counters"]),
    "cache_misses_vs_speed": (fig_cache_misses_vs_speed, ["cache-counters"]),
    "simd_vectorization": (fig_vectorization, ["timings", "no-vectorization"]),
    # quality of the measurement
    "quality_noise_check": (fig_noise_check, ["tile-sweep", "oblivious"]),
}

DIAGRAMS = diagrams.DIAGRAMS
