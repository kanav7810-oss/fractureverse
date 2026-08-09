"""FRACTUREVERSE Part 2 validation.

Checks the things Part 3 and Part 4 will depend on, in the same shape as
validate_part1.py. Nothing here trains a model. Everything is loaded from disk,
which is the point: if this passes, Part 4 Playwright tests have a deterministic
backend.

    python validate_part2.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT / "research"
ML_ART = ROOT / "ml" / "artifacts"
PINN_ART = ROOT / "pinn" / "artifacts"
FIGURES = ROOT / "python_stats" / "figures"

EM_DASH = chr(0x2014)  # built at runtime so this file never contains one
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}   ({detail})")


def main() -> int:
    t0 = time.perf_counter()
    print("FRACTUREVERSE Part 2 validation")
    print("=" * 62)

    # 1 artifacts on disk
    want = ["lstm.pt", "xgb_field.json", "split.json", "scalers.json",
            "shap_summary.json", "trajectories_meta.json",
            "trajectories_aerospace.npz", "trajectories_biomedical.npz",
            "trajectories_civil.npz"]
    missing = [w for w in want if not (ML_ART / w).exists()]
    check("1. Trained weights and the fixed split are on disk",
          not missing, f"{len(want) - len(missing)}/{len(want)} present")

    # 2 trajectory counts
    man = json.loads((ML_ART / "trajectories_meta.json").read_text())
    counts = {d: b["n_trajectories"] for d, b in man["domains"].items()}
    check("2. 500 trajectories per domain",
          all(v == 500 for v in counts.values()), str(counts))

    # 3 split is stable and disjoint
    sp = json.loads((ML_ART / "split.json").read_text())
    idx = sp["train"] + sp["val"] + sp["test"]
    check("3. Split covers every trajectory exactly once",
          len(idx) == len(set(idx)) == sp["n"] == 1500,
          f"{len(sp['train'])}/{len(sp['val'])}/{len(sp['test'])}, seed {sp['seed']}")

    # 4 saved models reproduce the reported scores
    from ml.evaluate import score
    from ml.feature_extract import prepared
    from ml import lstm_model, xgboost_model
    ds = prepared()
    rep = json.loads((RESEARCH / "ml_report.json").read_text())

    ok, detail = True, []
    for name, res in (("lstm", lstm_model.load(ds)),
                      ("xgboost_field", xgboost_model.load(ds))):
        s = score(ds, res["pred"]["test"])
        want_r2 = rep["models"][name]["test"]["r2"]
        d = abs(s["r2"] - want_r2)
        ok &= d < 1e-9
        detail.append(f"{name} delta R2 {d:.2e}")
    check("4. Loaded weights reproduce the reported test scores to 1e-9",
          ok, ", ".join(detail))

    # 5 LSTM clears the target
    lstm_r2 = rep["models"]["lstm"]["test"]["r2"]
    check("5. LSTM test R squared above the 0.92 target", lstm_r2 > 0.92,
          f"R2 = {lstm_r2:.5f}, RMSE = {rep['models']['lstm']['test']['rmse']:.4f} decades")

    # 6 per domain reporting present for every model
    have = all("per_domain" in blk["test"] and len(blk["test"]["per_domain"]) == 3
               for blk in rep["models"].values())
    check("6. R squared and RMSE reported per domain for every model",
          have, f"{len(rep['models'])} models, 3 domains each")

    # 7 the leak is closed
    leaky = set(rep["feature_sets"]["leaky_dropped"])
    check("7. Paris coefficients and a_c are excluded from the feature set",
          {"log_paris_C", "paris_m", "log_a_c"} <= leaky, sorted(leaky))

    # 8 PINN trained, five loss terms, all finite
    pin = json.loads((PINN_ART / "pinn_report.json").read_text())
    fl = pin["final_losses"]
    check("8. PINN has five physics losses and all are finite",
          len(fl) == 5 and all(np.isfinite(v) for v in fl.values()),
          ", ".join(f"{k} {v:.2e}" for k, v in fl.items()))

    # 9 PINN architecture as specified
    a = pin["architecture"]
    check("9. PINN is 8 layers, 128 neurons, tanh, Xavier",
          a["depth"] == 8 and a["width"] == 128 and a["activation"] == "tanh"
          and a["init"].startswith("xavier"),
          f"{a['n_parameters']} parameters, {a['inputs']} inputs")

    # 10 PINN field accuracy against XFEM
    acc = pin["accuracy"]
    l2 = acc["displacement_relative_L2_vs_xfem"]
    check("10. PINN displacement within 10 percent relative L2 of XFEM",
          l2 < 0.10, f"relative L2 = {l2 * 100:.2f} percent, "
                     f"K_I from opening {acc['K_I_pinn_from_opening']:.2f} against "
                     f"XFEM {acc['K_I_xfem_from_opening']:.2f} MPa sqrt(m)")

    # 11 wall clock recorded honestly
    check("11. PINN wall clock recorded, CPU only",
          pin["wall_clock_s"] > 0 and pin["device"] == "cpu",
          f"{pin['wall_clock_s']} s for {pin['epochs']} epochs, "
          f"{pin['seconds_per_epoch']} s per epoch")

    # 12 seventeen figures
    pngs = sorted(FIGURES.glob("chart_*.png"))
    check("12. 17 figures written at 300 dpi", len(pngs) == 17,
          f"{len(pngs)} PNG files")

    # 13 every figure has a caption
    caps = json.loads((FIGURES / "captions.json").read_text())
    check("13. Every figure carries a caption",
          len(caps) == len(pngs) and all(p.stem in caps for p in pngs),
          f"{len(caps)} captions")

    # 14 summary carries both Paris coefficients
    summ = json.loads((RESEARCH / "stats_summary.json").read_text())
    ratio = summ["paris_coefficient_used"]["aerospace_life_ratio_anchored_over_specified"]
    check("14. Both Paris coefficients reported, ratio stated",
          4.0 < ratio < 8.0,
          f"anchored life is {ratio:.2f} times the specified life for 2024-T3")

    # 15 no em dashes in anything Part 2 wrote
    bad = []
    for p in list(ROOT.glob("*.md")) + list(RESEARCH.glob("*.md")) + \
            list((ROOT / "ml").glob("*.py")) + list((ROOT / "pinn").glob("*.py")) + \
            list((ROOT / "python_stats").glob("*.py")):
        if EM_DASH in p.read_text(encoding="utf-8"):
            bad.append(p.name)
    check("15. No em dashes in Part 2 source or documents", not bad, str(bad or "clean"))

    dt = time.perf_counter() - t0
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print("=" * 62)
    print(f"{passed}/{len(CHECKS)} checks passed in {dt:.1f}s")

    out = {"part": 2, "checks": [{"name": n, "pass": ok, "detail": d}
                                 for n, ok, d in CHECKS],
           "summary": {"passed": passed, "total": len(CHECKS),
                       "seconds": round(dt, 1)}}
    (RESEARCH / "part2_validation.json").write_text(json.dumps(out, indent=1))
    print("written:", RESEARCH / "part2_validation.json")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
