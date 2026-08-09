"""Train the centre cracked panel PINN on CPU, with NTK style adaptive weights.

Weighting rule: every REBALANCE epochs, take the gradient of each loss term with
respect to the network parameters and set

    lambda_i = sum_j ||grad L_j|| / ||grad L_i||

normalised so the weights average one. This is the gradient norm form of the NTK
balancing of Wang, Teng and Perdikaris, which equalises the rate at which each term
trains instead of leaving the boundary terms to be swamped by the residual.

Wall clock is measured and written out honestly. This machine has no usable GPU.
"""

from __future__ import annotations

import json
import math
import random
import time

import numpy as np
import torch

from physics import lefm, xfem
from physics.materials import get_material

from . import ARTIFACTS, SEED
from .model import LOSS_NAMES, PINN, Panel, loss_terms

W_PANEL = 0.10
A_HALF = 0.02
SIGMA = 100e6
NX, NY = 61, 121

N_INTERIOR = 1200
N_TOP = 150
N_SIDE = 200
N_CRACK = 200
N_DATA = 400

EPOCHS = 2000
LR = 1e-3
REBALANCE = 100


def seed_everything(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(4)


def _lefm_K() -> float:
    """Closed form K_I for the same panel, MPa*sqrt(m)."""
    return lefm.stress_intensity(SIGMA, A_HALF, W_PANEL, "center")


def xfem_reference() -> dict:
    """Solve the same panel with XFEM. This is the data term and the error yardstick."""
    mat = get_material("aerospace", "Al2024-T3")
    res = xfem.solve_center_crack(mat, A_HALF, SIGMA, W=W_PANEL, nx=NX, ny=NY)
    return {"mat": mat, "res": res, "solver": res["solution"].solver,
            "u": res["solution"].u}


def collocation(ref: dict, panel: Panel, rng: np.random.Generator) -> dict:
    W, H, a, yc = panel.W, panel.H, panel.a, panel.yc
    eps = 1e-4 * W

    interior = np.column_stack([rng.uniform(0, W, N_INTERIOR),
                                rng.uniform(0, H, N_INTERIOR)])
    # push points off the crack line, a PDE residual on the discontinuity is meaningless
    on_line = np.abs(interior[:, 1] - yc) < eps
    interior[on_line, 1] += eps * np.where(rng.random(on_line.sum()) < 0.5, -1.0, 1.0)

    top = np.column_stack([rng.uniform(0, W, N_TOP), np.full(N_TOP, H)])
    half = N_SIDE // 2
    side = np.vstack([
        np.column_stack([np.zeros(half), rng.uniform(0, H, half)]),
        np.column_stack([np.full(N_SIDE - half, W), rng.uniform(0, H, N_SIDE - half)]),
    ])
    xs = rng.uniform(panel.xc - a * 0.995, panel.xc + a * 0.995, N_CRACK // 2)
    crack = np.vstack([np.column_stack([xs, np.full(len(xs), yc + eps)]),
                       np.column_stack([xs, np.full(len(xs), yc - eps)])])

    dxy = np.column_stack([rng.uniform(0.02 * W, 0.98 * W, N_DATA),
                           rng.uniform(0.02 * H, 0.98 * H, N_DATA)])
    off = np.abs(dxy[:, 1] - yc) < eps
    dxy[off, 1] += eps * np.where(rng.random(off.sum()) < 0.5, -1.0, 1.0)
    duv = ref["solver"].displacement_at(ref["u"], dxy)

    t = lambda arr: torch.tensor(np.asarray(arr, dtype=np.float32))
    return {"interior": t(interior), "top": t(top), "side": t(side),
            "crack": t(crack), "data_xy": t(dxy), "data_uv": t(duv)}


def _grad_norm(loss: torch.Tensor, params) -> float:
    g = torch.autograd.grad(loss, params, retain_graph=True, allow_unused=True)
    return float(torch.sqrt(sum((x ** 2).sum() for x in g if x is not None)))


def k_from_opening(x: np.ndarray, v_open: np.ndarray, panel: Panel,
                   E: float) -> float:
    """K_I in MPa*sqrt(m) from the near tip crack opening, plane stress.

        delta_v(r) = (K_I / E) * sqrt(32 r / pi),  r measured back from the tip

    delta_v is the full opening, upper face minus lower face, plane stress.

    Fitted over 0.05 a to 0.30 a behind the right hand tip, where the singular term
    dominates but the mesh and the network still resolve the field.
    """
    tip = panel.xc + panel.a
    r = tip - x
    m = (r > 0.05 * panel.a) & (r < 0.30 * panel.a)
    if m.sum() < 3:
        return float("nan")
    slope = float(np.sum(v_open[m] * np.sqrt(r[m])) / np.sum(r[m]))
    return slope * E / math.sqrt(32.0 / math.pi) / 1e6


def crack_opening(model: PINN, panel: Panel, n: int = 120):
    eps = 1e-4 * panel.W
    x = np.linspace(panel.xc - 0.99 * panel.a, panel.xc + 0.99 * panel.a, n)
    up = torch.tensor(np.column_stack([x, np.full(n, panel.yc + eps)]), dtype=torch.float32)
    lo = torch.tensor(np.column_stack([x, np.full(n, panel.yc - eps)]), dtype=torch.float32)
    with torch.no_grad():
        v = (model(up)[:, 1] - model(lo)[:, 1]).numpy().astype(float)
    return x, v


def train(epochs: int = EPOCHS, save: bool = True, verbose: bool = True) -> dict:
    seed_everything()
    torch.set_default_dtype(torch.float32)
    ref = xfem_reference()
    mat = ref["mat"]
    panel = Panel(W_PANEL, 2.0 * W_PANEL, A_HALF, SIGMA, mat.E, mat.nu)
    rng = np.random.default_rng(SEED)
    pts = collocation(ref, panel, rng)

    model = PINN(panel)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.Adam(params, lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

    lam = torch.ones(len(LOSS_NAMES))
    hist = {"epoch": [], "total": [], "weights": [],
            **{n: [] for n in LOSS_NAMES}}
    t0 = time.perf_counter()
    for ep in range(epochs):
        opt.zero_grad()
        terms = loss_terms(model, pts)

        if ep % REBALANCE == 0:
            norms = torch.tensor([_grad_norm(t, params) for t in terms])
            norms = torch.clamp(norms, min=1e-12)
            lam = norms.sum() / norms
            lam = lam / lam.mean()

        total = sum(w * t for w, t in zip(lam, terms))
        total.backward()
        torch.nn.utils.clip_grad_norm_(params, 10.0)
        opt.step()
        sched.step()

        if ep % 10 == 0 or ep == epochs - 1:
            hist["epoch"].append(ep)
            hist["total"].append(float(total))
            hist["weights"].append([float(w) for w in lam])
            for n, t in zip(LOSS_NAMES, terms):
                hist[n].append(float(t))
        if verbose and ep % 250 == 0:
            print(f"  epoch {ep:5d}  total {float(total):.4e}  " +
                  "  ".join(f"{n} {float(t):.2e}" for n, t in zip(LOSS_NAMES, terms)))
    wall = time.perf_counter() - t0

    # accuracy against XFEM on a fresh set of points the network never saw
    rng2 = np.random.default_rng(SEED + 7)
    test_xy = np.column_stack([rng2.uniform(0.02 * panel.W, 0.98 * panel.W, 400),
                               rng2.uniform(0.02 * panel.H, 0.98 * panel.H, 400)])
    off = np.abs(test_xy[:, 1] - panel.yc) < 1e-4 * panel.W
    test_xy[off, 1] += 1e-4 * panel.W
    uv_ref = ref["solver"].displacement_at(ref["u"], test_xy)
    with torch.no_grad():
        uv_pinn = model(torch.tensor(test_xy, dtype=torch.float32)).numpy().astype(float)
    denom = np.linalg.norm(uv_ref)
    l2 = float(np.linalg.norm(uv_pinn - uv_ref) / denom)

    x_op, v_op = crack_opening(model, panel)
    k_pinn = k_from_opening(x_op, v_op, panel, mat.E)

    eps = 1e-4 * panel.W
    up = np.column_stack([x_op, np.full(len(x_op), panel.yc + eps)])
    lo = np.column_stack([x_op, np.full(len(x_op), panel.yc - eps)])
    v_xfem = (ref["solver"].displacement_at(ref["u"], up)[:, 1]
              - ref["solver"].displacement_at(ref["u"], lo)[:, 1])
    k_xfem_cod = k_from_opening(x_op, v_xfem, panel, mat.E)

    out = {
        "epochs": epochs, "wall_clock_s": round(wall, 1),
        "seconds_per_epoch": round(wall / epochs, 4),
        "dtype": "float32", "device": "cpu", "threads": torch.get_num_threads(),
        "architecture": {"depth": 8, "width": 128, "activation": "tanh",
                         "init": "xavier_normal", "inputs": 10,
                         "n_parameters": sum(p.numel() for p in params),
                         "enrichment": "4 Westergaard branch functions per tip",
                         "hard_constraint": "v = (y/H) * net_v, roller at y = 0 exact"},
        "loss_names": list(LOSS_NAMES),
        "final_losses": {n: hist[n][-1] for n in LOSS_NAMES},
        "final_weights": hist["weights"][-1],
        "panel": {"W": panel.W, "H": panel.H, "a": panel.a, "sigma_MPa": SIGMA / 1e6,
                  "material": mat.key, "E_GPa": mat.E / 1e9, "nu": mat.nu},
        "accuracy": {
            "displacement_relative_L2_vs_xfem": l2,
            "K_I_xfem_interaction_integral": ref["res"]["K_I"],
            "K_I_analytical": _lefm_K(),
            "K_I_pinn_from_opening": k_pinn,
            "K_I_xfem_from_opening": k_xfem_cod,
            "K_I_pinn_error_percent": 100.0 * (k_pinn - ref["res"]["K_I"]) / ref["res"]["K_I"],
            "cod_fit_note": "same near tip opening fit applied to both fields, "
                            "so the comparison isolates the network not the estimator",
        },
    }
    if save:
        torch.save({"state_dict": model.state_dict(),
                    "panel": {"W": panel.W, "H": panel.H, "a": panel.a,
                              "sigma": panel.sigma, "E": panel.E, "nu": panel.nu},
                    "seed": SEED}, ARTIFACTS / "pinn.pt")
        (ARTIFACTS / "pinn_history.json").write_text(json.dumps(hist))
        (ARTIFACTS / "pinn_report.json").write_text(json.dumps(out, indent=1))
        np.savez_compressed(ARTIFACTS / "pinn_fields.npz",
                            cod_x=x_op, cod_pinn=v_op, cod_xfem=v_xfem,
                            test_xy=test_xy, uv_pinn=uv_pinn, uv_xfem=uv_ref)
    out["model"], out["panel_obj"], out["history"] = model, panel, hist
    return out


def load() -> tuple[PINN, Panel]:
    blob = torch.load(ARTIFACTS / "pinn.pt", weights_only=True)
    p = blob["panel"]
    panel = Panel(p["W"], p["H"], p["a"], p["sigma"], p["E"], p["nu"])
    model = PINN(panel)
    model.load_state_dict(blob["state_dict"])
    model.eval()
    return model, panel


if __name__ == "__main__":
    r = train()
    print(json.dumps({k: v for k, v in r.items()
                      if k in ("wall_clock_s", "final_losses", "accuracy")}, indent=1))
