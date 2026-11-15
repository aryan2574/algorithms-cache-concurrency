"""Conceptual diagrams that do not depend on measurements.

memory_layouts   how the same 8 x 8 matrix is stored in memory in the three layouts, and how many
                 cache lines a walk along a row or down a column touches. The index formulas are
                 the ones in experiments/01-matrix-multiplication/main.cpp (at() and tile_index()).
recursion_steps  how the cache-oblivious algorithm splits C = A * B (i, then j, then k, ...).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from . import style

LINE_ELEMENTS = 8  # a 64-byte cache line holds 8 doubles


def layout_index(layout: str, r: int, c: int, n: int, tile: int) -> int:
    """Position of element (r, c) in memory. Same formulas as main.cpp."""
    if layout == "row":
        return r * n + c
    if layout == "col":
        return c * n + r
    if layout == "tile":
        tiles_per_row = n // tile
        tile_number = (r // tile) * tiles_per_row + c // tile
        return tile_number * tile * tile + (r % tile) * tile + c % tile
    raise ValueError(layout)


def check_layouts(n: int = 8, tile: int = 4) -> None:
    """Every layout must place the n*n elements on n*n different positions 0 .. n*n-1."""
    for layout in ("row", "col", "tile"):
        positions = sorted(layout_index(layout, r, c, n, tile) for r in range(n) for c in range(n))
        assert positions == list(range(n * n)), f"layout {layout} is not a permutation"


def fig_memory_layouts(n: int = 8, tile: int = 4):
    check_layouts(n, tile)
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 4.3), layout="constrained")
    pastel = plt.get_cmap("Pastel1").colors  # 9 soft colours, one per cache line
    marked_row, marked_col = 2, 2

    for ax, layout in zip(axes, ("row", "col", "tile")):
        for r in range(n):
            for c in range(n):
                idx = layout_index(layout, r, c, n, tile)
                line = idx // LINE_ELEMENTS
                ax.add_patch(Rectangle((c, n - 1 - r), 1, 1, facecolor=pastel[line % len(pastel)],
                                       edgecolor="white", linewidth=1.0))
                ax.text(c + 0.5, n - 1 - r + 0.5, str(idx), ha="center", va="center", fontsize=6.5)
        if layout == "tile":
            for tr in range(n // tile):
                for tc in range(n // tile):
                    ax.add_patch(Rectangle((tc * tile, n - (tr + 1) * tile), tile, tile, fill=False,
                                           edgecolor="black", linewidth=1.8))
        ax.add_patch(Rectangle((0, n - 1 - marked_row), n, 1, fill=False, edgecolor=style.BLUE, linewidth=2.4))
        ax.add_patch(Rectangle((marked_col, 0), 1, n, fill=False, edgecolor=style.VERMILLION, linewidth=2.4))

        lines_row = len({layout_index(layout, marked_row, c, n, tile) // LINE_ELEMENTS for c in range(n)})
        lines_col = len({layout_index(layout, r, marked_col, n, tile) // LINE_ELEMENTS for r in range(n)})
        ax.set_title(f"{style.LAYOUT_LABEL[layout]}\n"
                     f"along a row (blue): {lines_row} cache line{'s' if lines_row != 1 else ''}\n"
                     f"down a column (red): {lines_col} cache line{'s' if lines_col != 1 else ''}",
                     fontsize=9)
        ax.set_xlim(0, n)
        ax.set_ylim(0, n)
        ax.set_aspect("equal")
        ax.axis("off")

    fig.text(0.5, 0.012,
             f"Each cell shows the position of the element in memory. Cells with the same colour share one 64-byte "
             f"cache line ({LINE_ELEMENTS} doubles).\nTile-wise layout with {tile} x {tile} tiles (black frames): "
             f"each tile is one contiguous block. Fewer cache lines touched = faster.",
             ha="center", va="bottom", fontsize=7.5, color="#444444")
    fig.get_layout_engine().set(rect=(0, 0.09, 1, 0.91))
    return fig


def fig_recursion_steps():
    """The cache-oblivious recursion: split i (rows of A and C), then j, then k, and so on."""
    dims_order = ["i", "j", "k"]
    # matrix: (name, row dimension, column dimension)
    matrices = [("A", "i", "k"), ("B", "k", "j"), ("C", "i", "j")]
    titles = ["start: C += A x B", "split i\n(rows of A and C)", "then split j\n(columns of B and C)",
              "then split k\n(columns of A, rows of B)"]
    fig, axes = plt.subplots(1, 4, figsize=(12.0, 2.9), layout="constrained")

    for step, ax in enumerate(axes):
        active = {d: (0.0, 1.0) for d in dims_order}
        sibling = None  # (dimension, range) of the half that is done afterwards
        for s in range(step):
            d = dims_order[s]
            lo, hi = active[d]
            mid = (lo + hi) / 2
            active[d] = (lo, mid)
            sibling = (d, (mid, hi))

        for m, (name, row_dim, col_dim) in enumerate(matrices):
            x0 = m * 1.35
            ax.add_patch(Rectangle((x0, 0), 1, 1, facecolor="#F2F2F2", edgecolor="black", linewidth=1.0))
            r_lo, r_hi = active[row_dim]
            c_lo, c_hi = active[col_dim]
            if sibling is not None and sibling[0] in (row_dim, col_dim):
                d, (s_lo, s_hi) = sibling
                if d == row_dim:
                    ax.add_patch(Rectangle((x0 + c_lo, 1 - r_hi * 0 - s_hi), c_hi - c_lo, s_hi - s_lo,
                                           facecolor=style.ORANGE, alpha=0.55, edgecolor="none"))
                else:
                    ax.add_patch(Rectangle((x0 + s_lo, 1 - r_hi), s_hi - s_lo, r_hi - r_lo,
                                           facecolor=style.ORANGE, alpha=0.55, edgecolor="none"))
            ax.add_patch(Rectangle((x0 + c_lo, 1 - r_hi), c_hi - c_lo, r_hi - r_lo,
                                   facecolor=style.BLUE, alpha=0.8, edgecolor="none"))
            ax.add_patch(Rectangle((x0, 0), 1, 1, fill=False, edgecolor="black", linewidth=1.0))
            ax.text(x0 + 0.5, -0.12, f"{name}", ha="center", va="top", fontsize=9, fontweight="bold")
            ax.text(x0 - 0.04, 0.5, row_dim, ha="right", va="center", fontsize=7, color="#555555")
            ax.text(x0 + 0.5, 1.04, col_dim, ha="center", va="bottom", fontsize=7, color="#555555")
        ax.set_xlim(-0.2, 3.9)
        ax.set_ylim(-0.35, 1.2)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(titles[step], fontsize=9)

    handles = [Rectangle((0, 0), 1, 1, facecolor=style.BLUE, alpha=0.8),
               Rectangle((0, 0), 1, 1, facecolor=style.ORANGE, alpha=0.55)]
    fig.legend(handles, ["first half: done first (recursion goes on inside it)", "second half: done afterwards"],
               loc="outside upper center", ncol=2, frameon=False)
    fig.text(0.5, 0.012,
             "The recursion repeats until the block is small (the 'base'); at some depth the three blocks fit into every "
             "cache level, whatever its size.\nThe cache size is never used. For a block that is not a cube, the "
             "largest of the three dimensions is split.",
             ha="center", va="bottom", fontsize=7.5, color="#444444")
    fig.get_layout_engine().set(rect=(0, 0.14, 1, 0.86))
    return fig


# name -> function; no data tables needed
DIAGRAMS = {
    "memory_layouts": fig_memory_layouts,
    "recursion_steps": fig_recursion_steps,
}
