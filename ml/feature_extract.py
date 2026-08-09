"""Features and the one fixed train / validation / test split every model uses.

Prognostics framing: an inspector sees the first WINDOW samples of a crack growth
trajectory plus the material and loading condition, and must predict the total
fatigue life. Target is log10(N_f) because lives span aerospace 1e3 to civil 1e9.

The split is written to ml/artifacts/split.json and never regenerated unless
forced, so Part 4 Playwright tests see the same test set forever.
"""

from __future__ import annotations

import json

import numpy as np

from . import ARTIFACTS, SEED
from .data_gen import SWEEPS, load

WINDOW = 20            # early samples visible to the model
DOMAIN_CODE = {"aerospace": 0, "biomedical": 1, "civil": 2}
GEOM_CODE = {"center": 0, "edge": 1, "compact": 2, "through": 3, "surface": 4}

STATIC_NAMES = [
    "log_a0", "log_sigma_max", "R", "log_W", "log_paris_C", "paris_m",
    "log_E", "K_IC", "log_sigma_Y", "nu", "geometry", "domain",
    "log_a_c", "a0_over_ac", "log_dK0", "K_ratio_0", "log_dadn_0",
]
SEQ_NAMES = ["log_a", "log_N1", "log_delta_K", "log_da_dN", "K_ratio"]

# The field setting: an inspector knows the geometry, the load and the material
# class, but not that specimen's Paris coefficients, and certainly not a_c. Those
# have to be inferred from the observed early growth. Keeping them in the feature
# vector makes the target a closed form function of the inputs and every model,
# ridge included, scores R2 above 0.999. That is a leak, not a result.
LEAKY_NAMES = ["log_paris_C", "paris_m", "log_a_c", "a0_over_ac", "log_dadn_0"]
FIELD_NAMES = [n for n in STATIC_NAMES if n not in LEAKY_NAMES]
FIELD_COLS = [STATIC_NAMES.index(n) for n in FIELD_NAMES]


def _static_row(m: dict, seq: np.ndarray) -> list[float]:
    return [
        np.log10(m["a0"]), np.log10(m["sigma_max"]), m["R"], np.log10(m["W"]),
        np.log10(m["paris_C"]), m["paris_m"], np.log10(m["E"]), m["K_IC"],
        np.log10(m["sigma_Y"]), m["nu"], GEOM_CODE[m["geometry"]],
        DOMAIN_CODE[m["domain"]], np.log10(m["a_c"]), m["a0"] / m["a_c"],
        np.log10(max(seq[0, 2], 1e-12)), seq[0, 4],
        np.log10(max(seq[0, 3], 1e-30)),
    ]


def _seq_window(seq: np.ndarray) -> np.ndarray:
    """Early window, log scaled where the quantity spans decades."""
    w = seq[:WINDOW]
    return np.stack([
        np.log10(np.maximum(w[:, 0], 1e-12)),                    # a
        np.log10(np.maximum(w[:, 1], 0.0) + 1.0),                # N, shifted, starts at 0
        np.log10(np.maximum(w[:, 2], 1e-12)),                    # delta_K
        np.log10(np.maximum(w[:, 3], 1e-30)),                    # da/dN
        w[:, 4],                                                 # K_ratio
    ], axis=1)


def build_dataset() -> dict:
    X_static, X_seq, y, domains, index = [], [], [], [], []
    for sweep in SWEEPS:
        seqs, meta = load(sweep.domain)
        for i, (s, m) in enumerate(zip(seqs, meta)):
            X_static.append(_static_row(m, s))
            X_seq.append(_seq_window(s))
            y.append(np.log10(max(m["N_f"], 1.0)))
            domains.append(m["domain"])
            index.append(f"{m['domain']}:{i}")
    return {
        "X_static": np.asarray(X_static, dtype=np.float64),
        "X_seq": np.asarray(X_seq, dtype=np.float32),
        "y": np.asarray(y, dtype=np.float64),
        "domain": np.asarray(domains),
        "index": np.asarray(index),
        "static_names": STATIC_NAMES, "seq_names": SEQ_NAMES, "window": WINDOW,
    }


def get_split(n: int, domain: np.ndarray, force: bool = False) -> dict:
    """Fixed 70 / 15 / 15 split, stratified by domain. Written once, reused forever."""
    path = ARTIFACTS / "split.json"
    if path.exists() and not force:
        s = json.loads(path.read_text())
        if s["n"] == n:
            return {k: np.asarray(s[k]) for k in ("train", "val", "test")}

    rng = np.random.default_rng(SEED)
    train, val, test = [], [], []
    for d in np.unique(domain):
        idx = np.where(domain == d)[0]
        rng.shuffle(idx)
        n_tr, n_va = int(0.70 * len(idx)), int(0.15 * len(idx))
        train += idx[:n_tr].tolist()
        val += idx[n_tr:n_tr + n_va].tolist()
        test += idx[n_tr + n_va:].tolist()
    out = {"train": sorted(train), "val": sorted(val), "test": sorted(test)}
    path.write_text(json.dumps({"n": n, "seed": SEED, **out}))
    return {k: np.asarray(v) for k, v in out.items()}


def standardize(X: np.ndarray, train_idx: np.ndarray) -> tuple[np.ndarray, dict]:
    mu = X[train_idx].mean(axis=0)
    sd = X[train_idx].std(axis=0)
    sd[sd < 1e-12] = 1.0
    return (X - mu) / sd, {"mu": mu.tolist(), "sd": sd.tolist()}


# Inspection noise, in decades, applied to the observed window only. Crack length
# from an eddy current or replica reading, and a differenced growth rate, are not
# clean. Without this the task is log linear and every model including ridge scores
# R2 above 0.999, which says more about Paris Law than about the model.
NOISE_DECADES = {"log_a": 0.02, "log_N1": 0.0, "log_delta_K": 0.02,
                 "log_da_dN": 0.08, "K_ratio": 0.0}
NOISE_KRATIO_ABS = 0.01


def add_inspection_noise(X_seq: np.ndarray, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed + 991)
    out = X_seq.copy()
    for c, name in enumerate(SEQ_NAMES):
        s = NOISE_KRATIO_ABS if name == "K_ratio" else NOISE_DECADES[name]
        if s > 0:
            out[:, :, c] += rng.normal(0.0, s, size=out.shape[:2]).astype(np.float32)
    return out


def prepared(noise: bool = True) -> dict:
    """Dataset plus split plus train fitted scalers. The single entry point."""
    ds = build_dataset()
    ds["noise"] = bool(noise)
    if noise:
        ds["X_seq"] = add_inspection_noise(ds["X_seq"])
        for i, nm in enumerate(("log_dK0", "K_ratio_0", "log_dadn_0")):
            col = STATIC_NAMES.index(nm)
            ds["X_static"][:, col] = ds["X_seq"][:, 0, (2, 4, 3)[i]]
    split = get_split(len(ds["y"]), ds["domain"])
    ds["split"] = split
    ds["X_static_z"], ds["static_scaler"] = standardize(ds["X_static"], split["train"])
    flat = ds["X_seq"].reshape(-1, ds["X_seq"].shape[-1])
    tr_flat = ds["X_seq"][split["train"]].reshape(-1, ds["X_seq"].shape[-1])
    mu, sd = tr_flat.mean(axis=0), tr_flat.std(axis=0)
    sd[sd < 1e-12] = 1.0
    ds["X_seq_z"] = ((flat - mu) / sd).reshape(ds["X_seq"].shape).astype(np.float32)
    ds["seq_scaler"] = {"mu": mu.tolist(), "sd": sd.tolist()}
    ds["X_field_z"] = ds["X_static_z"][:, FIELD_COLS]
    ds["field_names"] = FIELD_NAMES
    return ds


def tabular(ds: dict, leaky: bool = False) -> np.ndarray:
    """Field static features plus the flattened observation window, for tree and
    linear models. Set leaky=True to include the Paris coefficients and a_c."""
    base = ds["X_static_z"] if leaky else ds["X_field_z"]
    return np.hstack([base, ds["X_seq_z"].reshape(len(base), -1)])


def tabular_names(ds: dict, leaky: bool = False) -> list[str]:
    base = STATIC_NAMES if leaky else FIELD_NAMES
    return list(base) + [f"{n}_t{t}" for t in range(WINDOW) for n in SEQ_NAMES]


if __name__ == "__main__":
    ds = prepared()
    print("X_static", ds["X_static"].shape, "X_seq", ds["X_seq"].shape)
    print("split", {k: len(v) for k, v in ds["split"].items()})
    print("y log10 N_f range", ds["y"].min().round(3), ds["y"].max().round(3))
