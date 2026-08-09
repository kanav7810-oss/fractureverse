"""Two baselines the learned models must beat, or be honest about not beating.

1. Ridge regression on the static features. The dumb statistical floor.
2. Closed form Paris integral with constant geometry factor F = F(a0). Physics with
   no learning at all. It is strong, because the target was produced by numerically
   integrating the same law with a varying F. The gap it leaves is exactly the
   geometry factor drift, which is what a surrogate has to pick up.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import Ridge

from physics import lefm
from .data_gen import SWEEPS, load
from .feature_extract import prepared, tabular


def ridge_baseline(ds: dict, leaky: bool = False) -> dict:
    X = tabular(ds, leaky=leaky)
    tr = ds["split"]["train"]
    model = Ridge(alpha=1.0).fit(X[tr], ds["y"][tr])
    return {"name": "ridge_oracle" if leaky else "ridge",
            "notes": "leaky feature set, upper bound reference" if leaky
                     else "field feature set, no Paris coefficients",
            "pred": {k: model.predict(X[ds["split"][k]])
                     for k in ("train", "val", "test")}}


def closed_form_baseline(ds: dict) -> dict:
    """log10 N_f from the analytical Paris integral, F frozen at its value at a0."""
    metas = []
    for sweep in SWEEPS:
        metas += load(sweep.domain)[1]
    pred = np.empty(len(metas))
    for i, m in enumerate(metas):
        F = lefm.geometry_factor(m["a0"], m["W"], m["geometry"])
        n = lefm.cycles_to_failure_closed_form(
            m["a0"], m["a_c"], m["sigma_max"] * (1.0 - max(m["R"], 0.0)),
            m["paris_C"], m["paris_m"], F=F)
        pred[i] = np.log10(max(n, 1.0))
    return {"name": "paris_closed_form",
            "pred": {k: pred[ds["split"][k]] for k in ("train", "val", "test")}}


if __name__ == "__main__":
    from .evaluate import score
    ds = prepared()
    for b in (ridge_baseline(ds), ridge_baseline(ds, leaky=True), closed_form_baseline(ds)):
        s = score(ds, b["pred"]["test"], "test")
        print(b["name"], "R2", round(s["r2"], 4), "RMSE", round(s["rmse"], 4))
