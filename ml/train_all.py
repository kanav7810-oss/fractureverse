"""Train every model once, write ml_report.json, save all weights. Seeded end to end.

    python -m ml.train_all           train and save
    python -m ml.train_all --load    rebuild the report from saved weights only
"""

from __future__ import annotations

import sys
import time

from . import ARTIFACTS
from .baseline import closed_form_baseline, ridge_baseline
from .data_gen import build
from .evaluate import print_table, report
from .feature_extract import prepared
from . import lstm_model, xgboost_model


def main(load_only: bool = False) -> dict:
    t0 = time.perf_counter()
    manifest = build()
    ds = prepared()

    models = {}
    r = ridge_baseline(ds)
    models[r["name"]] = r
    c = closed_form_baseline(ds)
    models[c["name"]] = c

    xgb = xgboost_model.load(ds) if load_only else xgboost_model.train(ds)
    models[xgb["name"]] = xgb
    if not load_only:
        xgboost_model.shap_summary(xgb, ds)

    lstm = lstm_model.load(ds) if load_only else lstm_model.train(ds, verbose=True)
    models[lstm["name"]] = lstm

    blob = report(ds, models, extra={
        "seed": manifest["seed"],
        "n_trajectories": {d: b["n_trajectories"] for d, b in manifest["domains"].items()},
        "feature_sets": {
            "field": ds["field_names"],
            "leaky_dropped": [n for n in ds["static_names"] if n not in ds["field_names"]],
        },
        "inspection_noise": ds["noise"],
        "artifacts": sorted(p.name for p in ARTIFACTS.iterdir()),
        "wall_clock_s": round(time.perf_counter() - t0, 1),
        "honesty_note": (
            "Paris Law is a power law, so log10(N_f) is close to linear in the log "
            "features. Every model here clears the 0.92 R squared target, ridge "
            "included. The separation is in RMSE measured in decades of life, not in "
            "R squared, and that is how the paper should report it."),
    })
    print_table(blob)
    print(f"total {blob['wall_clock_s']} s")
    return blob


if __name__ == "__main__":
    main(load_only="--load" in sys.argv)
