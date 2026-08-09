"""LSTM sequence model: read the early crack growth window, predict log10(N_f).

Two layer LSTM over the WINDOW samples, last hidden state concatenated with the
field static features, then a small MLP head. CPU only, which is all this machine
has. Weights and scalers go to ml/artifacts/lstm.pt.
"""

from __future__ import annotations

import json
import random
import time

import numpy as np
import torch
import torch.nn as nn

from . import ARTIFACTS, SEED
from .feature_extract import prepared

HIDDEN = 64
LAYERS = 2
EPOCHS = 400
BATCH = 64
LR = 3e-3


def seed_everything(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(4)


class CrackLSTM(nn.Module):
    def __init__(self, n_seq: int, n_static: int, hidden: int = HIDDEN,
                 layers: int = LAYERS):
        super().__init__()
        self.lstm = nn.LSTM(n_seq, hidden, num_layers=layers, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden + n_static, 64), nn.Tanh(),
            nn.Linear(64, 32), nn.Tanh(),
            nn.Linear(32, 1),
        )

    def forward(self, seq: torch.Tensor, static: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(seq)
        return self.head(torch.cat([out[:, -1], static], dim=1)).squeeze(-1)


def _tensors(ds: dict, part: str):
    idx = ds["split"][part]
    return (torch.tensor(ds["X_seq_z"][idx], dtype=torch.float32),
            torch.tensor(ds["X_field_z"][idx], dtype=torch.float32),
            torch.tensor(ds["y"][idx], dtype=torch.float32))


def train(ds: dict, epochs: int = EPOCHS, save: bool = True, verbose: bool = True) -> dict:
    seed_everything()
    # y is standardized for training, then mapped back, so the loss is well scaled
    tr_idx = ds["split"]["train"]
    y_mu, y_sd = float(ds["y"][tr_idx].mean()), float(ds["y"][tr_idx].std())

    xs_tr, st_tr, y_tr = _tensors(ds, "train")
    xs_va, st_va, y_va = _tensors(ds, "val")
    y_tr_z = (y_tr - y_mu) / y_sd

    model = CrackLSTM(xs_tr.shape[-1], st_tr.shape[-1])
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    lossf = nn.MSELoss()
    g = torch.Generator().manual_seed(SEED)

    hist = {"epoch": [], "train_loss": [], "val_rmse": []}
    best = {"rmse": float("inf"), "state": None, "epoch": -1}
    t0 = time.perf_counter()
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(y_tr_z), generator=g)
        tot = 0.0
        for i in range(0, len(perm), BATCH):
            b = perm[i:i + BATCH]
            opt.zero_grad()
            loss = lossf(model(xs_tr[b], st_tr[b]), y_tr_z[b])
            loss.backward()
            opt.step()
            tot += float(loss) * len(b)
        sched.step()
        model.eval()
        with torch.no_grad():
            pv = model(xs_va, st_va) * y_sd + y_mu
            rmse = float(torch.sqrt(((pv - y_va) ** 2).mean()))
        hist["epoch"].append(ep)
        hist["train_loss"].append(tot / len(perm))
        hist["val_rmse"].append(rmse)
        if rmse < best["rmse"]:
            best = {"rmse": rmse, "epoch": ep,
                    "state": {k: v.clone() for k, v in model.state_dict().items()}}
        if verbose and ep % 50 == 0:
            print(f"  epoch {ep:4d}  train {tot / len(perm):.5f}  val RMSE {rmse:.4f}")
    wall = time.perf_counter() - t0

    model.load_state_dict(best["state"])
    model.eval()
    pred = {}
    with torch.no_grad():
        for part in ("train", "val", "test"):
            xs, st, _ = _tensors(ds, part)
            pred[part] = (model(xs, st) * y_sd + y_mu).numpy().astype(np.float64)

    if save:
        torch.save({"state_dict": model.state_dict(), "y_mu": y_mu, "y_sd": y_sd,
                    "n_seq": xs_tr.shape[-1], "n_static": st_tr.shape[-1],
                    "hidden": HIDDEN, "layers": LAYERS, "seed": SEED,
                    "best_epoch": best["epoch"]}, ARTIFACTS / "lstm.pt")
        (ARTIFACTS / "lstm_history.json").write_text(json.dumps(hist))
        (ARTIFACTS / "scalers.json").write_text(json.dumps({
            "static": ds["static_scaler"], "seq": ds["seq_scaler"],
            "y_mu": y_mu, "y_sd": y_sd, "field_names": ds["field_names"]}))

    return {"name": "lstm", "model": model, "pred": pred, "history": hist,
            "wall_clock_s": round(wall, 2), "best_epoch": best["epoch"],
            "params": {"hidden": HIDDEN, "layers": LAYERS, "epochs": epochs,
                       "batch": BATCH, "lr": LR,
                       "n_parameters": sum(p.numel() for p in model.parameters())}}


def load(ds: dict) -> dict:
    blob = torch.load(ARTIFACTS / "lstm.pt", weights_only=True)
    model = CrackLSTM(blob["n_seq"], blob["n_static"], blob["hidden"], blob["layers"])
    model.load_state_dict(blob["state_dict"])
    model.eval()
    pred = {}
    with torch.no_grad():
        for part in ("train", "val", "test"):
            xs, st, _ = _tensors(ds, part)
            pred[part] = (model(xs, st) * blob["y_sd"] + blob["y_mu"]).numpy().astype(np.float64)
    return {"name": "lstm", "model": model, "pred": pred}


if __name__ == "__main__":
    from .evaluate import score
    ds = prepared()
    res = train(ds)
    s = score(ds, res["pred"]["test"])
    print("lstm R2", round(s["r2"], 5), "RMSE", round(s["rmse"], 4),
          "in", res["wall_clock_s"], "s")
    print("per domain", {k: round(v["r2"], 4) for k, v in s["per_domain"].items()})
