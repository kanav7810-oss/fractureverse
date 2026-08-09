"""Scoring, per domain breakdown, and the one report every chart and the paper read.

Targets are log10(N_f), so RMSE is in decades. A ratio error is reported alongside
because "the model is within a factor of 1.2 on life" is what an engineer wants.
"""

from __future__ import annotations

import json

import numpy as np

from . import ARTIFACTS

RESEARCH = ARTIFACTS.parent.parent / "research"


def _metrics(y: np.ndarray, p: np.ndarray) -> dict:
    err = p - y
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": int(len(y)),
        "r2": 1.0 - ss_res / max(ss_tot, 1e-30),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mae": float(np.mean(np.abs(err))),
        "median_life_ratio_error": float(np.median(np.abs(10.0 ** err - 1.0))),
    }


def score(ds: dict, pred: np.ndarray, part: str = "test") -> dict:
    idx = ds["split"][part]
    y = ds["y"][idx]
    out = _metrics(y, pred)
    out["per_domain"] = {}
    dom = ds["domain"][idx]
    for d in np.unique(dom):
        m = dom == d
        out["per_domain"][str(d)] = _metrics(y[m], pred[m])
    return out


def report(ds: dict, models: dict[str, dict], extra: dict | None = None) -> dict:
    """models maps name -> {'pred': {'train':..,'val':..,'test':..}, ...}."""
    blob = {"target": "log10(N_f)", "window": ds["window"],
            "split_sizes": {k: int(len(v)) for k, v in ds["split"].items()},
            "models": {}}
    for name, m in models.items():
        blob["models"][name] = {
            part: score(ds, m["pred"][part], part) for part in ("train", "val", "test")
        }
        for k in ("wall_clock_s", "params", "notes"):
            if k in m:
                blob["models"][name][k] = m[k]
    if extra:
        blob.update(extra)
    (ARTIFACTS / "ml_report.json").write_text(json.dumps(blob, indent=1))
    RESEARCH.mkdir(exist_ok=True)
    (RESEARCH / "ml_report.json").write_text(json.dumps(blob, indent=1))
    return blob


def load_report() -> dict:
    return json.loads((ARTIFACTS / "ml_report.json").read_text())


def print_table(blob: dict) -> None:
    print(f"{'model':22s} {'split':6s} {'R2':>8s} {'RMSE':>8s} {'ratio err':>10s}")
    for name, per in blob["models"].items():
        for part in ("train", "val", "test"):
            s = per[part]
            print(f"{name:22s} {part:6s} {s['r2']:8.4f} {s['rmse']:8.4f} "
                  f"{s['median_life_ratio_error']:10.4f}")
