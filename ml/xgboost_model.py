"""Gradient boosted trees on the field feature set, plus SHAP attribution.

Weights go to ml/artifacts/xgb_<tag>.json so Part 4 never retrains.
"""

from __future__ import annotations

import json
import time

import numpy as np
import xgboost as xgb

from . import ARTIFACTS, SEED
from .feature_extract import prepared, tabular, tabular_names

PARAMS = dict(n_estimators=600, max_depth=5, learning_rate=0.05,
              subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
              random_state=SEED, n_jobs=4, tree_method="hist")


def train(ds: dict, leaky: bool = False, save: bool = True) -> dict:
    tag = "oracle" if leaky else "field"
    X = tabular(ds, leaky=leaky)
    tr, va = ds["split"]["train"], ds["split"]["val"]
    model = xgb.XGBRegressor(early_stopping_rounds=40, **PARAMS)
    t0 = time.perf_counter()
    model.fit(X[tr], ds["y"][tr], eval_set=[(X[va], ds["y"][va])], verbose=False)
    wall = time.perf_counter() - t0
    if save:
        model.save_model(ARTIFACTS / f"xgb_{tag}.json")
    return {"name": f"xgboost_{tag}", "model": model, "X": X,
            "wall_clock_s": round(wall, 2),
            "params": {**PARAMS, "best_iteration": int(model.best_iteration)},
            "pred": {k: model.predict(X[ds["split"][k]]) for k in ("train", "val", "test")}}


def load(ds: dict, leaky: bool = False) -> dict:
    tag = "oracle" if leaky else "field"
    model = xgb.XGBRegressor()
    model.load_model(ARTIFACTS / f"xgb_{tag}.json")
    X = tabular(ds, leaky=leaky)
    return {"name": f"xgboost_{tag}", "model": model, "X": X,
            "pred": {k: model.predict(X[ds["split"][k]]) for k in ("train", "val", "test")}}


def shap_summary(res: dict, ds: dict, top: int = 15) -> dict:
    """Mean absolute SHAP value per feature on the test split. Feeds chart 14."""
    import shap
    te = ds["split"]["test"]
    ex = shap.TreeExplainer(res["model"])
    vals = ex.shap_values(res["X"][te])
    names = tabular_names(ds, leaky=res["name"].endswith("oracle"))
    mean_abs = np.abs(vals).mean(axis=0)
    order = np.argsort(mean_abs)[::-1][:top]
    out = {"features": [names[i] for i in order],
           "mean_abs_shap": mean_abs[order].tolist(),
           "base_value": float(np.asarray(ex.expected_value).ravel()[0])}
    (ARTIFACTS / "shap_summary.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    from .evaluate import score
    ds = prepared()
    res = train(ds)
    s = score(ds, res["pred"]["test"])
    print(res["name"], "R2", round(s["r2"], 5), "RMSE", round(s["rmse"], 4),
          "in", res["wall_clock_s"], "s")
    sh = shap_summary(res, ds)
    print("top features", sh["features"][:5])
