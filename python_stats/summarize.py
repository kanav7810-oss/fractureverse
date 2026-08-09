"""Collect Part 1 validation, the ML report, the PINN report and the figure list
into research/stats_summary.json, the single file the paper and Part 3 read.

    python -m python_stats.summarize
"""

from __future__ import annotations

import json

import numpy as np

from physics import lefm
from physics.materials import domain_metadata, get_material, use_anchored_paris

from . import FIGURES, RESEARCH
from .charts import ANCHOR, DOMAINS


def domain_lives() -> dict:
    """Anchor life per domain under the specified and the anchored Paris coefficient."""
    out = {}
    for d in DOMAINS:
        cfg = ANCHOR[d]
        m = get_material(d, cfg["material"])
        blk = {"material": m.key, "sigma_max_MPa": cfg["sigma"] / 1e6, "R": cfg["R"],
               "a0_mm": cfg["a0"] * 1e3, "geometry": cfg["geometry"],
               "W_mm": cfg["W"] * 1e3,
               "cycles_per_year": domain_metadata(d)["cycle_frequency_per_year"]}
        for tag, mm in (("specified", m), ("anchored", use_anchored_paris(m))):
            r = lefm.cycles_to_failure(cfg["a0"], cfg["sigma"], cfg["R"], mm,
                                       W=cfg["W"], geometry=cfg["geometry"])
            blk[tag] = {"paris_C": mm.paris_C, "N_f": r["N_f"],
                        "a_c_mm": r["a_c"] * 1e3,
                        "years_to_failure": lefm.cycles_to_years(r["N_f"], d)}
        blk["anchored_differs"] = abs(blk["anchored"]["paris_C"] - blk["specified"]["paris_C"]) > 0
        out[d] = blk
    return out


def build() -> dict:
    part1 = json.loads((RESEARCH / "part1_validation.json").read_text())
    ml = json.loads((RESEARCH / "ml_report.json").read_text())
    pinn_path = RESEARCH.parent / "pinn" / "artifacts" / "pinn_report.json"
    pinn = json.loads(pinn_path.read_text()) if pinn_path.exists() else None
    caps_path = FIGURES / "captions.json"
    caps = json.loads(caps_path.read_text()) if caps_path.exists() else {}

    lives = domain_lives()
    summary = {
        "part": 2,
        "title": "FRACTUREVERSE Part 2, surrogates, physics informed learning and figures",
        "units": {
            "K": "MPa*sqrt(m)", "stress": "Pa at every API boundary",
            "J": "J/m^2", "length": "m", "da_dN": "m/cycle",
        },
        "domain_lives": lives,
        "paris_coefficient_used": {
            "value_used_everywhere_in_part2": "specified",
            "statement": (
                "Every life number in Part 2 uses the specified Paris coefficient from "
                "the project brief. For 2024-T3 that is C = 3.6e-10, which is a factor "
                "5.7 above the commonly cited anchor of da/dN = 2.0e-7 m/cycle at "
                "delta_K = 10 MPa*sqrt(m). Lives computed with it are therefore short by "
                "roughly that factor. The anchored value is reported alongside in "
                "domain_lives so both are on the record."),
            "aerospace_life_ratio_anchored_over_specified":
                lives["aerospace"]["anchored"]["N_f"] / lives["aerospace"]["specified"]["N_f"],
        },
        "machine_learning": {
            "target": ml["target"], "window_samples": ml["window"],
            "split_sizes": ml["split_sizes"],
            "n_trajectories": ml["n_trajectories"],
            "inspection_noise_applied": ml["inspection_noise"],
            "test_scores": {name: {"r2": blk["test"]["r2"],
                                   "rmse_decades": blk["test"]["rmse"],
                                   "median_life_ratio_error":
                                       blk["test"]["median_life_ratio_error"],
                                   "per_domain_r2": {k: v["r2"] for k, v
                                                     in blk["test"]["per_domain"].items()}}
                            for name, blk in ml["models"].items()},
            "lstm_target_r2": 0.92,
            "lstm_target_met": ml["models"]["lstm"]["test"]["r2"] > 0.92,
            "honesty_note": ml["honesty_note"],
        },
        "pinn": None if pinn is None else {
            "architecture": pinn["architecture"], "epochs": pinn["epochs"],
            "wall_clock_s": pinn["wall_clock_s"],
            "seconds_per_epoch": pinn["seconds_per_epoch"],
            "device": pinn["device"], "dtype": pinn.get("dtype"),
            "loss_names": pinn["loss_names"], "final_losses": pinn["final_losses"],
            "final_weights": pinn["final_weights"], "accuracy": pinn["accuracy"],
            "panel": pinn["panel"],
        },
        "part1_headline_numbers": {
            "xfem_K_I_error_percent": [c["error_percent"] for c
                                       in part1["xfem"]["cases"]],
            "epfm_J_error_percent": part1["epfm"]["J_error_percent"],
            "pure_mode_II_kink_angle_deg": part1["xfem_mixed_mode"]["cases"][-1]["kink_angle_deg"],
            "peridynamic_crack_advance_m": part1["peridynamic_branching"]["crack_advance"],
            "peridynamic_pd_strength_MPa": part1["peridynamic_branching"]["pd_strength_MPa"],
            "peridynamic_applied_MPa": part1["peridynamic_branching"]["sigma_MPa"],
        },
        "figures": {name: {"file": f"python_stats/figures/{name}.png",
                           "caption": cap} for name, cap in sorted(caps.items())},
        "figure_count": len(caps),
    }
    (RESEARCH / "stats_summary.json").write_text(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    s = build()
    print(f"figures: {s['figure_count']}")
    print("lstm test R2:",
          s["machine_learning"]["test_scores"]["lstm"]["r2"])
    if s["pinn"]:
        print("pinn displacement L2:",
              s["pinn"]["accuracy"]["displacement_relative_L2_vs_xfem"])
    print("written:", RESEARCH / "stats_summary.json")
