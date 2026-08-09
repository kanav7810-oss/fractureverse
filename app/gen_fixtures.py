"""Build the static JSON fixtures the Part 3 frontend reads.

Run from the repo root:

    python app/gen_fixtures.py

Everything written here comes from the Part 1 solver or the Part 2 artifacts.
No number is retyped by hand. Part 4 replaces the sweep fixture with a live
FastAPI /solve endpoint, the shapes below are what the frontend already expects.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from physics import lefm
from physics.materials import get_material, use_anchored_paris
from physics.unified_solver import (CrackConfig, LoadCase, SolveRequest,
                                    capabilities, solve, to_json_safe)

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "public" / "data"
FIGS_OUT = Path(__file__).resolve().parent / "public" / "figures"

SIGMA_MPA = [40, 60, 80, 100, 125, 150, 180, 220, 260]
A0_MM = [0.5, 1.0, 2.0, 4.0, 8.0]
CURVE_POINTS = 40


def r6(x):
    """Round for transport. Keeps six significant digits, kills JSON bloat."""
    if isinstance(x, (list, tuple)):
        return [r6(v) for v in x]
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(f"{float(x):.6g}")
    return x


def downsample(values, n=CURVE_POINTS):
    values = np.asarray(values, dtype=float)
    if values.size <= n:
        return r6(values.tolist())
    idx = np.linspace(0, values.size - 1, n).round().astype(int)
    return r6(values[idx].tolist())


def write(name, payload):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.0f} kB")


def material_index(caps):
    out = []
    for domain, meta in caps["domains"].items():
        for key in meta["materials"]:
            mat = get_material(domain, key)
            out.append((domain, key, mat))
    return out


def sweep(caps):
    """LEFM and EPFM over the selector grid. Both are closed form and instant."""
    records = []
    curves = {}
    for domain, key, mat in material_index(caps):
        for geometry in ["infinite", "center", "edge", "compact", "through", "surface"]:
            for sigma in SIGMA_MPA:
                for a0_mm in A0_MM:
                    crack = CrackConfig(a0=a0_mm * 1e-3, geometry=geometry, W=0.1)
                    load = LoadCase(sigma_max=sigma * 1e6, R=0.1)
                    added = []
                    for law in ["paris", "walker", "forman"]:
                        try:
                            res = solve(SolveRequest(domain=domain, material=key,
                                                     theory="lefm", load=load,
                                                     crack=crack, growth_law=law))
                        except ValueError:
                            continue  # geometry_factor guards a/W, skip the invalid corner
                        rid = f"{domain}|{key}|{geometry}|{law}|{sigma}|{a0_mm}"
                        added.append({
                            "id": rid, "domain": domain, "material": key,
                            "geometry": geometry, "law": law,
                            "sigma_MPa": sigma, "a0_mm": a0_mm,
                            "K_I": r6(res["K_I"]), "K_IC": r6(res["K_IC"]),
                            "K_ratio": r6(res["K_ratio"]), "G": r6(res["G"]),
                            "delta_K": r6(res["delta_K"]), "da_dN": r6(res["da_dN"]),
                            "a_c": r6(res["a_c"]), "N_f": r6(res["N_f"]),
                            "years_to_failure": r6(res["years_to_failure"]),
                            "plastic_zone": r6(res["plastic_zone"]),
                            "ssy_valid": bool(res["ssy_valid"]),
                        })
                        hist = res.get("history") or {}
                        if geometry == "center" and law == "paris" and hist:
                            curves[rid] = {"a": downsample(hist["a"]),
                                           "N": downsample(hist["N"])}
                    if not added:
                        continue
                    try:
                        ep = solve(SolveRequest(domain=domain, material=key,
                                                theory="epfm", load=load, crack=crack))
                    except ValueError:
                        ep = None
                    if ep is not None:
                        # J and CTOD do not depend on the growth law, so every law shares them
                        for rec in added:
                            rec["J_elastic"] = r6(ep["J_elastic"])
                            rec["J_elastic_plastic"] = r6(ep["J_elastic_plastic"])
                            rec["J_IC"] = r6(ep["J_IC"])
                            rec["J_ratio"] = r6(ep["J_ratio"])
                            rec["ctod"] = r6(ep["ctod"])
                            rec["ctod_critical"] = r6(ep["ctod_critical"])
                    records.extend(added)
    return records, curves


def anchored_lives(caps):
    """Finding 6.1. Every life the UI shows must say which Paris C produced it."""
    out = []
    for domain, key, mat in material_index(caps):
        base = solve(SolveRequest(domain=domain, material=key, theory="lefm"))
        row = {"domain": domain, "material": key,
               "paris_C": r6(mat.paris_C), "N_f_specified": r6(base["N_f"]),
               "years_specified": r6(base["years_to_failure"])}
        anchored = getattr(mat, "paris_C_anchored", None)
        if anchored:
            # solve() reloads the material, so integrate with the anchored C directly
            alt = use_anchored_paris(mat)
            n = lefm.cycles_to_failure(alt, sigma_max=150e6, R=0.1, a0=1e-3,
                                       geometry="center", W=0.1)
            row["paris_C_anchored"] = r6(alt.paris_C)
            row["N_f_anchored"] = r6(n["N_f"])
            row["ratio"] = r6(n["N_f"] / base["N_f"])
        out.append(row)
    return out


def xfem_fixture(caps):
    """One XFEM solve per domain plus the cached 30 degree propagation path."""
    out = {}
    for domain in caps["domains"]:
        res = to_json_safe(solve(SolveRequest(domain=domain, theory="xfem")))
        out[domain] = {k: r6(v) for k, v in res.items()
                       if k not in ("mesh", "history") and not isinstance(v, dict)}
        out[domain]["interaction_integral"] = r6(res["interaction_integral"])
        out[domain]["mesh"] = {k: r6(v) for k, v in res["mesh"].items()
                               if not isinstance(v, (list, dict))}
    cache = json.loads((ROOT / "python_stats" / "cache"
                        / "xfem_propagate_30deg.json").read_text())
    out["propagation"] = {k: r6(v) for k, v in cache.items()
                          if k != "final_crack"}
    return out


def peridynamic_fixture():
    """Damage field from the Part 1 branching run plus the horizon strength note."""
    damage = np.load(ROOT / "research" / "part1_peridynamic_damage.npy")
    res = to_json_safe(solve(SolveRequest(domain="civil", theory="peridynamic")))
    scalars = {k: r6(v) for k, v in res.items() if not isinstance(v, (dict, list))}
    return {"scalars": scalars,
            "energy_check": r6(res["energy_check"]),
            "damage_shape": list(damage.shape),
            "damage": r6(np.asarray(damage, dtype=float).ravel().tolist())}


def ml_fixture():
    report = json.loads((ROOT / "research" / "ml_report.json").read_text())
    shap = json.loads((ROOT / "ml" / "artifacts" / "shap_summary.json").read_text())
    hist = json.loads((ROOT / "ml" / "artifacts" / "lstm_history.json").read_text())
    preds = json.loads((ROOT / "python_stats" / "cache" / "ml_predictions.json").read_text())
    return {"report": report, "shap": shap,
            "lstm_history": {k: r6(v) for k, v in hist.items()},
            "parity": {"y": r6(preds["y"]), "domain": preds["domain"],
                       "models": {k: r6(v) for k, v in preds["models"].items()}}}


def pinn_fixture():
    report = json.loads((ROOT / "pinn" / "artifacts" / "pinn_report.json").read_text())
    hist = json.loads((ROOT / "pinn" / "artifacts" / "pinn_history.json").read_text())
    z = np.load(ROOT / "pinn" / "artifacts" / "pinn_fields.npz")
    return {"report": report,
            "history": {k: r6(v) for k, v in hist.items() if k != "weights"},
            "cod": {"x": r6(z["cod_x"].tolist()),
                    "pinn": r6(z["cod_pinn"].tolist()),
                    "xfem": r6(z["cod_xfem"].tolist())},
            "field": {"xy": r6(z["test_xy"].tolist()),
                      "uv_pinn": r6(z["uv_pinn"].tolist()),
                      "uv_xfem": r6(z["uv_xfem"].tolist())}}


def checks(name):
    """Part 1 uses `passed` and a nested detail object, Part 2 uses `pass` and a string.
    Flatten both to one shape so the frontend does not carry the difference."""
    report = json.loads((ROOT / "research" / name).read_text())
    out = []
    for c in report["checks"]:
        detail = c.get("detail", "")
        if not isinstance(detail, str):
            detail = json.dumps(detail, separators=(",", ":"))
        out.append({"name": c["name"],
                    "pass": bool(c.get("pass", c.get("passed"))),
                    "target": str(c.get("target", "")),
                    "detail": detail[:400]})
    return {"checks": out}


def copy_figures():
    src = ROOT / "python_stats" / "figures"
    FIGS_OUT.mkdir(parents=True, exist_ok=True)
    for png in sorted(src.glob("*.png")):
        shutil.copyfile(png, FIGS_OUT / png.name)
    captions = json.loads((src / "captions.json").read_text())
    return captions


def main():
    caps = capabilities()
    write("capabilities.json", caps)
    write("stats_summary.json",
          json.loads((ROOT / "research" / "stats_summary.json").read_text()))
    records, curves = sweep(caps)
    write("sweep.json", {"sigma_MPa": SIGMA_MPA, "a0_mm": A0_MM, "records": records})
    write("curves.json", curves)
    write("anchored.json", anchored_lives(caps))
    write("xfem.json", xfem_fixture(caps))
    write("peridynamic.json", peridynamic_fixture())
    write("ml.json", ml_fixture())
    write("pinn.json", pinn_fixture())
    write("figures.json", copy_figures())
    write("validation.json", {"part1": checks("part1_validation.json"),
                              "part2": checks("part2_validation.json")})
    print(f"{len(records)} sweep records, {len(curves)} growth curves")


if __name__ == "__main__":
    main()
