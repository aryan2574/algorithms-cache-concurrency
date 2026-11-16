"""One visual style for every figure, so the same thing always looks the same.

Colour = storage layout (row-major, column-major, tile-wise).
Line style and marker = kind of algorithm (plain loops, cache-aware, cache-oblivious).
The colours are the Okabe-Ito palette, which stays readable for colour-blind readers and in
grey-scale print.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

# Okabe-Ito
BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
VERMILLION = "#D55E00"
SKY = "#56B4E9"
PINK = "#CC79A7"
YELLOW = "#F0E442"
GREY = "#6E6E6E"

LAYOUT_COLOR = {"row": BLUE, "col": ORANGE, "tile": GREEN}
LAYOUT_LABEL = {"row": "row-major", "col": "column-major", "tile": "tile-wise"}

# kind: (line style, marker, label)
KIND_STYLE = {
    "plain": (":", "x", "plain loops"),
    "aware": ("-", "o", "cache-aware"),
    "oblivious": ("--", "s", "cache-oblivious"),
}

# version name used by the C++ program -> (layout, kind)
VERSIONS = {
    "naive": ("row", "plain"),
    "row_wise": ("row", "plain"),
    "col_wise": ("col", "plain"),
    "tiled": ("row", "aware"),
    "tiled_col_major": ("col", "aware"),
    "tiled_tile_wise": ("tile", "aware"),
    "oblivious_row_major": ("row", "oblivious"),
    "oblivious_col_major": ("col", "oblivious"),
    "oblivious_tile_wise": ("tile", "oblivious"),
    # matrix transposition (always row-major storage; layout key unused for colour choice)
    "transpose_naive": ("row", "plain"),
    "transpose_tiled": ("row", "aware"),
    "transpose_oblivious": ("row", "oblivious"),
    # A row-major, B stored as B^T (professor case b, literally)
    "transposed_b": ("row", "plain"),
    "tiled_transposed_b": ("row", "aware"),
}

# (layout, kind) -> multiply version name for experiment 01 layout comparisons.
# Built only from these names so transpose / other extras do not overwrite the map.
VERSION_OF = {
    VERSIONS[name]: name
    for name in (
        "row_wise",
        "col_wise",
        "tiled",
        "tiled_col_major",
        "tiled_tile_wise",
        "oblivious_row_major",
        "oblivious_col_major",
        "oblivious_tile_wise",
    )
}

NOISE_BAND = 0.10  # differences under 10% are within the run-to-run noise (see the experiment README)


def style_for(version: str) -> dict:
    """matplotlib keyword arguments (color, linestyle, marker) and a label for a version."""
    if version == "naive":
        return {"color": GREY, "linestyle": ":", "marker": "x", "label": "naive i,j,k (row-major)"}
    if version == "transpose_naive":
        return {"color": GREY, "linestyle": ":", "marker": "x", "label": "transpose naive (two loops)"}
    if version == "transpose_tiled":
        return {"color": BLUE, "linestyle": "-", "marker": "o", "label": "transpose tiled (cache-aware)"}
    if version == "transpose_oblivious":
        return {"color": BLUE, "linestyle": "--", "marker": "s", "label": "transpose recursive (oblivious)"}
    if version == "transposed_b":
        return {"color": ORANGE, "linestyle": ":", "marker": "x", "label": "A × Bᵀ (ijk, B transposed)"}
    if version == "tiled_transposed_b":
        return {"color": ORANGE, "linestyle": "-", "marker": "o", "label": "tiled A × Bᵀ (B transposed)"}
    if version == "recursive":
        return {"color": BLUE, "linestyle": "--", "marker": "s", "label": "recursive (top-down)"}
    if version == "iterative":
        return {"color": VERMILLION, "linestyle": "-", "marker": "o", "label": "iterative (bottom-up)"}
    layout, kind = VERSIONS[version]
    linestyle, marker, kind_label = KIND_STYLE[kind]
    return {
        "color": LAYOUT_COLOR[layout],
        "linestyle": linestyle,
        "marker": marker,
        "label": f"{kind_label}, {LAYOUT_LABEL[layout]}",
    }


def apply() -> None:
    """Sets the global matplotlib defaults (font sizes for a thesis page, embedded fonts in PDF)."""
    mpl.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 9,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linewidth": 0.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "lines.linewidth": 1.5,
            "lines.markersize": 5,
            "figure.dpi": 100,
            "pdf.fonttype": 42,  # real fonts in the PDF, not outlines
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
        }
    )


def save(fig, out_dir: Path, name: str, formats: list[str], footnote: str | None = None) -> list[Path]:
    """Saves a figure in every requested format. PDF/SVG are vector (for LaTeX), PNG for slides."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if footnote:
        fig.text(0.005, 0.004, footnote, fontsize=5.5, color="#555555", ha="left", va="bottom")
    written = []
    for fmt in formats:
        path = out_dir / f"{name}.{fmt}"
        fig.savefig(path, dpi=200 if fmt == "png" else None)
        written.append(path)
    return written
