"""Single sample inference. The helper Part 1 to 3 never needed and Part 4 does.

The training set is 1500 trajectories built by ml/data_gen.py at n_points 200. A live
request has to reproduce that pipeline exactly or the scalers mean nothing, so this
module rebuilds one trajectory with lefm.crack_growth_history at the same n_points,
takes the same WINDOW of 20 early samples, builds the same static row, applies the
train fitted scalers from ml/artifacts/scalers.json and runs the saved LSTM.

Inspection noise is not applied. Training added it so the task was not log linear,
a live caller is handing us their own measurement and we take it as given.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import torch

from physics import lefm
from physics.materials import get_material

from . import ARTIFACTS
from .feature_extract import FIELD_COLS, WINDOW, _seq_window, _static_row
from .lstm_model import CrackLSTM

N_POINTS = 200  # must equal ml/data_gen.py, the window is 20 of these


@lru_cache(maxsize=1)
def _loaded():
    scalers = json.loads((ARTIFACTS / "scalers.json").read_text(encoding="utf-8"))
    blob = torch.load(ARTIFACTS / "lstm.pt", weights_only=True)
    model = CrackLSTM(blob["n_seq"], blob["n_static"], blob["hidden"], blob["layers"])
    model.load_state_dict(blob["state_dict"])
    model.eval()
    return model, blob, scalers


def features(domain: str, material: str | None, a0: float, sigma_max: float, R: float,
             W: float, geometry: str, law: str) -> dict:
    """The 20 sample window and the 17 static features for one crack."""
    mat = get_material(domain, material)
    h = lefm.crack_growth_history(a0, sigma_max, R, mat, W=W, geometry=geometry,
                                  law=law, n_points=N_POINTS)
    seq = np.stack([h["a"], h["N"], h["delta_K"], h["da_dN"], h["K_ratio"]],
                   axis=1).astype(np.float32)
    meta = {"domain": domain, "material": mat.key, "a0": a0, "sigma_max": sigma_max,
            "R": R, "W": W, "geometry": geometry, "paris_C": mat.paris_C,
            "paris_m": mat.paris_m, "E": mat.E, "K_IC": mat.K_IC,
            "sigma_Y": mat.sigma_Y, "nu": mat.nu, "a_c": h["a_c"], "N_f": h["N_f"]}
    return {"window": _seq_window(seq), "static": np.asarray(_static_row(meta, seq)),
            "history": h, "meta": meta}


def predict(domain: str = "aerospace", material: str | None = None, a0: float = 1e-3,
            sigma_max: float = 150e6, R: float = 0.1, W: float = 0.1,
            geometry: str = "center", law: str = "paris") -> dict:
    """Predicted total fatigue life for one crack, in cycles and in log10 cycles."""
    model, blob, sc = _loaded()
    f = features(domain, material, a0, sigma_max, R, W, geometry, law)

    seq_mu, seq_sd = np.asarray(sc["seq"]["mu"]), np.asarray(sc["seq"]["sd"])
    st_mu, st_sd = np.asarray(sc["static"]["mu"]), np.asarray(sc["static"]["sd"])
    seq_z = ((f["window"] - seq_mu) / seq_sd).astype(np.float32)
    static_z = ((f["static"] - st_mu) / st_sd)[FIELD_COLS].astype(np.float32)

    with torch.no_grad():
        out = model(torch.tensor(seq_z)[None], torch.tensor(static_z)[None])
    log_life = float(out.item() * blob["y_sd"] + blob["y_mu"])

    closed = f["meta"]["N_f"]
    return {
        "log10_N_f": log_life,
        "N_f_predicted": float(10.0 ** log_life),
        "N_f_closed_form": float(closed),
        "log10_error": float(log_life - np.log10(max(closed, 1.0))),
        "life_ratio_error": float(abs(10.0 ** log_life - closed) / max(closed, 1.0)),
        "a_c": float(f["meta"]["a_c"]),
        "window": {
            "n": WINDOW,
            "a": f["history"]["a"][:WINDOW].tolist(),
            "N": f["history"]["N"][:WINDOW].tolist(),
            "delta_K": f["history"]["delta_K"][:WINDOW].tolist(),
            "da_dN": f["history"]["da_dN"][:WINDOW].tolist(),
        },
        "inputs": {"domain": domain, "material": f["meta"]["material"], "a0": a0,
                   "sigma_max": sigma_max, "R": R, "W": W, "geometry": geometry,
                   "law": law},
        "model": "lstm",
        "note": ("Prediction from the first 20 observed samples only. The closed form "
                 "life uses the full Paris integration and is shown for comparison, "
                 "not as ground truth the model saw."),
    }
