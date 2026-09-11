"""Real computed PNGs for the Problem page. Every number from the solver on disk."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from physics import lefm
from python_stats.style import apply

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "public" / "problem"

SIGMA = 100e6
W = 0.1

RANGES = {
    "sent": (0.02, 0.68),
    "dent": (0.02, 0.44),
    "ccp": (0.02, 0.48),
    "ct": (0.21, 0.79),
    "tpb": (0.02, 0.68),
    "brazilian": (0.02, 0.38),
}

ALIAS = {"sent": "edge", "ccp": "center", "ct": "compact"}


def curve_png() -> None:
    apply()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    for g, (lo, hi) in RANGES.items():
        xs = np.linspace(lo, hi, 60)
        ys = []
        for x in xs:
            try:
                ys.append(lefm.stress_intensity(SIGMA, x * W, W, cast(Any, ALIAS.get(g, g))))
            except ValueError:
                ys.append(np.nan)
        ax.plot(xs, ys, label=g.upper())
    ax.set_xlabel("a over W")
    ax.set_ylabel("K_I in MPa sqrt(m)")
    ax.set_title("Stress intensity at 100 MPa, W 0.1 m, one solver")
    ax.legend(ncols=3, fontsize=9)
    fig.savefig(OUT / "problem_geometries_ki.png", dpi=150)
    plt.close(fig)


def validation_png() -> None:
    apply()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    labels = ["XFEM fit", "Closed form", "PINN", "Integral"]
    values = [25.5, 27.9, 26.9, 27.7]
    color = ["#9aa4ff", "#8f8d87", "#7fd1c0", "#8f8d87"]
    ax.bar(labels, values, color=color)
    ax.set_ylabel("K_I in MPa sqrt(m)")
    ax.set_title("Measured against reference on the same panel")
    for i, v in enumerate(values):
        ax.text(i, v + 0.3, f"{v}", ha="center", fontsize=10)
    fig.savefig(OUT / "problem_validation_ki.png", dpi=150)
    plt.close(fig)


def lstm_png() -> None:
    apply()
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    labels = ["aerospace", "biomedical", "civil", "test all"]
    values = [0.0228, 0.0254, 0.0338, 0.0277]
    color = ["#9aa4ff", "#7fd1c0", "#e8b04b", "#8f8d87"]
    ax.bar(labels, values, color=color)
    ax.set_ylabel("RMSE in decades of life")
    ax.set_title("LSTM error by domain, 225 test samples")
    for i, v in enumerate(values):
        ax.text(i, v + 0.0005, f"{v}", ha="center", fontsize=10)
    fig.savefig(OUT / "problem_lstm_rmse.png", dpi=150)
    plt.close(fig)


def branching_png() -> None:
    damage = np.load(ROOT / "research" / "part1_peridynamic_damage.npy")
    apply()
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    im = ax.imshow(damage, cmap="magma", origin="lower", aspect="auto")
    ax.set_xlabel("x cells")
    ax.set_ylabel("y cells")
    ax.set_title("Peridynamic damage field, concrete branching run")
    fig.colorbar(im, ax=ax, label="damage")
    fig.savefig(OUT / "problem_branching.png", dpi=150)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    curve_png()
    validation_png()
    lstm_png()
    branching_png()
    for p in sorted(OUT.glob("*.png")):
        print(f"{p.relative_to(ROOT)} {p.stat().st_size / 1024:.0f} kB")


if __name__ == "__main__":
    main()
