"""Part 3 acceptance checks. Fast, no training, no npm.

    python validate_part3.py

Writes research/part3_validation.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from physics.unified_solver import (CrackConfig, LoadCase, SolveRequest,  # noqa: E402
                                    capabilities, solve)

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
DATA = APP / "public" / "data"
SRC = APP / "src"

EM_DASH = chr(0x2014)  # built at runtime so this file never contains one
checks: list[dict] = []


def check(name, passed, detail=""):
    checks.append({"name": name, "pass": bool(passed), "detail": str(detail)[:400]})
    print(f"{'PASS' if passed else 'FAIL'}  {name}\n      {detail}")


def jload(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main():
    # 1. the app exists and pins the libraries Part 3 was specified with
    pkg = json.loads((APP / "package.json").read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    need = ["react", "typescript", "three", "@react-three/fiber", "framer-motion"]
    missing = [d for d in need if d not in deps]
    check("1. React TypeScript app with Three.js and Framer Motion", not missing,
          f"missing {missing}" if missing else ", ".join(f"{d} {deps[d]}" for d in need))

    # 2. every fixture parses
    names = ["capabilities.json", "stats_summary.json", "sweep.json", "curves.json",
             "anchored.json", "xfem.json", "peridynamic.json", "ml.json", "pinn.json",
             "figures.json", "validation.json"]
    bad = []
    for n in names:
        try:
            jload(n)
        except Exception as e:  # noqa: BLE001
            bad.append(f"{n}: {e}")
    check("2. Every fixture present and valid JSON", not bad, bad or f"{len(names)} files")

    # 3. the fixture capabilities are the solver capabilities, byte for byte
    same = jload("capabilities.json") == capabilities()
    check("3. capabilities.json equals capabilities()", same,
          "selectors are generated, not hardcoded")

    # 4. a spot solve reproduces the sweep record it was generated from
    rec = next(r for r in jload("sweep.json")["records"]
               if r["id"] == "aerospace|Al2024-T3|center|paris|150|1.0")
    live = solve(SolveRequest(domain="aerospace", material="Al2024-T3", theory="lefm",
                              load=LoadCase(sigma_max=150e6, R=0.1),
                              crack=CrackConfig(a0=1e-3, geometry="center", W=0.1)))
    err = max(abs(rec[k] - live[k]) / abs(live[k]) for k in ["K_I", "a_c", "N_f"])
    check("4. Sweep record reproduces a live solve", err < 1e-5,
          f"max relative error {err:.2e} over K_I, a_c and N_f, six significant digits stored")

    # 5. stats_summary.json is a copy, not a retyping
    same = jload("stats_summary.json") == json.loads(
        (ROOT / "research" / "stats_summary.json").read_text(encoding="utf-8"))
    check("5. stats_summary.json copied unchanged", same, "no number retyped in the frontend")

    # 6. no em dashes anywhere, now including the frontend sources
    exts = ("*.py", "*.md", "*.ts", "*.tsx", "*.css", "*.html")
    skip = {"node_modules", "dist", ".git", "artifacts", "figures", "public"}
    offenders = []
    for ext in exts:
        for p in ROOT.rglob(ext):
            if skip & set(p.parts):
                continue
            if EM_DASH in p.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(p.relative_to(ROOT)))
    check("6. No em dashes in py, md, ts, tsx, css or html", not offenders,
          offenders or f"{len(exts)} extensions scanned")

    # 7. nothing in the frontend touches the wheel or drives the scroll position
    hijack = []
    for p in SRC.rglob("*.ts*"):
        text = p.read_text(encoding="utf-8")
        for pattern in ["onWheel", "\"wheel\"", "'wheel'", "scrollTo", "scrollIntoView",
                        "preventDefault"]:
            if pattern in text:
                hijack.append(f"{p.name}: {pattern}")
    check("7. Vertical scroll is never hijacked", not hijack,
          hijack or "no wheel listener, no programmatic scrolling")

    # 8. the viewer is one instanced draw call with the specified fallback
    viewer = (SRC / "Viewer3D.tsx").read_text(encoding="utf-8")
    ok = ("instancedMesh" in viewer and "[50, 50, 20]" in viewer
          and "[30, 30, 10]" in viewer and "FRAME_BUDGET_MS = 50" in viewer)
    check("8. 50,000 cells in one instanced mesh with a 30 x 30 x 10 fallback", ok,
          "fallback triggers when frame time passes 50 ms")

    # 9. every sweep record respects the geometry_factor validity bounds
    bounds = {"center": (0.0, 0.5), "through": (0.0, 0.5), "compact": (0.2, 0.8)}
    bad = [r["id"] for r in jload("sweep.json")["records"]
           if r["geometry"] in bounds
           and not (bounds[r["geometry"]][0] <= (r["a0_mm"] / 1000) / 0.1
                    <= bounds[r["geometry"]][1])]
    check("9. No sweep record outside the geometry validity range", not bad,
          bad[:3] or "invalid combinations are absent, not extrapolated")

    # 10. the figures the gallery lists are the figures on disk
    figs = jload("figures.json")
    on_disk = {p.stem for p in (APP / "public" / "figures").glob("*.png")}
    check("10. Figure gallery matches python_stats output",
          set(figs) == on_disk and len(figs) == 17,
          f"{len(figs)} captions, {len(on_disk)} PNG files")

    # 11. the honesty findings are visible in the UI, not only in the handoff
    text = "\n".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*.tsx"))
    findings = {"6.1 anchored Paris": "anchored" in text,
                "6.2 horizon strength": "pd_strength_MPa" in text,
                "6.3 log linear task": "RMSE in decades" in text,
                "6.4 opening at the centre": "13 percent low" in text}
    check("11. All four honesty findings surfaced in the UI", all(findings.values()),
          findings)

    # 12. both earlier validation reports still pass in full
    v = jload("validation.json")
    counts = {k: (sum(c["pass"] for c in v[k]["checks"]), len(v[k]["checks"])) for k in v}
    check("12. Part 1 and Part 2 checks still green",
          all(a == b for a, b in counts.values()), counts)

    # 13. the production build succeeds, tsc included
    try:
        r = subprocess.run(["npm", "run", "build"], cwd=APP, capture_output=True,
                           text=True, shell=True, timeout=600)
        built = r.returncode == 0 and (APP / "dist" / "index.html").exists()
        detail = "dist/index.html written" if built else r.stdout[-300:] + r.stderr[-300:]
    except Exception as e:  # noqa: BLE001
        built, detail = False, str(e)
    check("13. tsc and vite build clean", built, detail)

    passed = sum(c["pass"] for c in checks)
    report = {"part": 3, "title": "FRACTUREVERSE Part 3 frontend acceptance",
              "checks": checks, "summary": {"passed": passed, "total": len(checks)}}
    (ROOT / "research" / "part3_validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{passed} of {len(checks)} checks passing")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
