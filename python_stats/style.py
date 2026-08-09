"""Shared figure style and small helpers. Import this before plotting anything."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import CACHE, FIGURES

DPI = 300
LABEL_SIZE = 12

DOMAIN_COLOR = {"aerospace": "#1f77b4", "biomedical": "#d62728", "civil": "#2ca02c"}
DOMAIN_LABEL = {"aerospace": "Aerospace, 2024-T3 aluminium",
                "biomedical": "Biomedical, cortical bone",
                "civil": "Civil, normal concrete"}

RC = {
    "figure.dpi": 110,
    "savefig.dpi": DPI,
    "font.size": 11,
    "axes.labelsize": LABEL_SIZE,
    "axes.titlesize": 13,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linewidth": 0.6,
    "legend.fontsize": 9,
    "legend.frameon": True,
    "legend.framealpha": 0.9,
    "lines.linewidth": 1.8,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.autolayout": False,
    "savefig.bbox": "tight",
}


def apply() -> None:
    plt.rcParams.update(RC)


def new(figsize=(8.0, 5.0), ncols: int = 1, nrows: int = 1, **kw):
    apply()
    return plt.subplots(nrows, ncols, figsize=figsize, **kw)


def finish(fig, number: int, slug: str, caption: str = "") -> Path:
    """Save as figures/chart_NN_slug.png and record the caption."""
    name = f"chart_{number:02d}_{slug}"
    path = FIGURES / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    if caption:
        cap = FIGURES / "captions.json"
        blob = json.loads(cap.read_text()) if cap.exists() else {}
        blob[name] = caption
        cap.write_text(json.dumps(blob, indent=1, sort_keys=True))
    return path


def cached(name: str, fn):
    """Run fn once, store its JSON safe result under python_stats/cache."""
    p = CACHE / f"{name}.json"
    if p.exists():
        return json.loads(p.read_text())
    out = fn()
    p.write_text(json.dumps(out))
    return out
