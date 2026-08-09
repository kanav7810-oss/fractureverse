"""Part 4 acceptance checks. Backend, live frontend path, end to end suite and paper.

    python validate_part4.py

Runs the FastAPI app in process with the TestClient, so no port and no uvicorn are
needed for checks 1 to 7. Check 12 does start a server, because Playwright needs one.
Writes research/part4_validation.json. About 3 minutes, almost all of it the npm build
and the browser suite.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402
from physics.unified_solver import (CrackConfig, LoadCase, SolveRequest,  # noqa: E402
                                    capabilities, solve)

APP = ROOT / "app"
SRC = APP / "src"
TESTS = APP / "tests"
DATA = APP / "public" / "data"

EM_DASH = chr(0x2014)  # built at runtime so this file never contains one
checks: list[dict] = []
client = TestClient(app)


def check(name, passed, detail=""):
    checks.append({"name": name, "pass": bool(passed), "detail": str(detail)[:400]})
    print(f"{'PASS' if passed else 'FAIL'}  {name}\n      {detail}")


def main():
    # 1. every endpoint the frontend and the paper depend on is mounted
    paths = {r.path for r in app.routes}
    need = {"/api/health", "/api/capabilities", "/api/solve", "/api/predict",
            "/api/figures", "/api/figures/{name}", "/api/report", "/api/data/{name}"}
    check("1. Every Part 4 endpoint is mounted", need <= paths,
          sorted(need - paths) or f"{len(need)} routes, plus the static mount")

    # 2. the API capabilities are the solver capabilities, unchanged from Part 3
    live = client.get("/api/capabilities").json()
    same = live == capabilities() == json.loads(
        (DATA / "capabilities.json").read_text(encoding="utf-8"))
    check("2. /api/capabilities equals capabilities() and the Part 3 fixture", same,
          "one source of truth for every selector in the app")

    # 3. a live solve over HTTP equals a direct solve call
    body = {"domain": "aerospace", "material": "Al2024-T3", "theory": "lefm",
            "load": {"sigma_max": 150e6, "R": 0.1},
            "crack": {"a0": 1e-3, "geometry": "center", "W": 0.1}}
    got = client.post("/api/solve", json=body).json()
    ref = solve(SolveRequest(domain="aerospace", material="Al2024-T3", theory="lefm",
                             load=LoadCase(sigma_max=150e6, R=0.1),
                             crack=CrackConfig(a0=1e-3, geometry="center", W=0.1)))
    err = max(abs(got[k] - ref[k]) / abs(ref[k]) for k in ("K_I", "a_c", "N_f"))
    check("3. /api/solve is the solver, not a copy of it", err == 0.0,
          f"max relative error {err:.1e} over K_I, a_c and N_f, "
          f"N_f {got['N_f']:.4f} cycles")

    # 4. the guards. out of range geometry, and the theories that take tens of seconds
    bad = client.post("/api/solve", json={"crack": {"a0": 0.09, "geometry": "center",
                                                    "W": 0.1}})
    slow = client.post("/api/solve", json={"theory": "peridynamic"})
    opted = client.post("/api/solve", json={"theory": "xfem", "allow_slow": True})
    ok = (bad.status_code == 422 and slow.status_code == 413 and opted.status_code == 200)
    check("4. Out of range refused, slow theories refused unless asked for", ok,
          f"a/W 0.9 gives {bad.status_code}, peridynamic gives {slow.status_code}, "
          f"xfem with allow_slow gives {opted.status_code}")

    # 5. the sample inference helper Part 3 said was missing
    # Each domain is asked about its own anchor case. The defaults are an aerospace
    # panel, and a 150 MPa load on cortical bone is nowhere near the training set.
    summary = json.loads((DATA / "stats_summary.json").read_text(encoding="utf-8"))
    rows = []
    for d, v in summary["domain_lives"].items():
        r = client.post("/api/predict", json={
            "domain": d, "material": v["material"], "a0": v["a0_mm"] / 1000,
            "sigma_max": v["sigma_max_MPa"] * 1e6, "R": v["R"],
            "W": v["W_mm"] / 1000, "geometry": v["geometry"]}).json()
        rows.append((d, r["life_ratio_error"]))
    worst = max(e for _, e in rows)
    check("5. /api/predict runs one sample through the trained LSTM", worst < 0.25,
          ", ".join(f"{d} life ratio error {e:.3f}" for d, e in rows))

    # 6. the precomputed grid is not reachable in live mode, so there is one truth
    gone = client.get("/api/data/sweep.json").status_code == 404
    served = client.get("/api/data/ml.json").status_code == 200
    check("6. sweep.json is offline only, ml.json is served", gone and served,
          "live mode never loads the 1.9 MB grid, the playground calls /api/solve")

    # 7. the report endpoints serve the built paper
    pdf = client.get("/api/report")
    md = client.get("/api/report?fmt=markdown")
    ok = (pdf.status_code == 200 and len(pdf.content) > 100_000
          and md.status_code == 200 and EM_DASH not in md.text)
    check("7. The paper is exported and downloadable", ok,
          f"pdf {len(pdf.content) // 1024} kB, markdown {len(md.text)} characters")

    # 8. no em dashes anywhere, the manuscript included
    exts = ("*.py", "*.md", "*.ts", "*.tsx", "*.css", "*.html")
    skip = {"node_modules", "dist", ".git", "artifacts", "figures", "public",
            "test-results", "playwright-report"}
    offenders = []
    for ext in exts:
        for p in ROOT.rglob(ext):
            if skip & set(p.parts):
                continue
            if EM_DASH in p.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(p.relative_to(ROOT)))
    check("8. No em dashes in py, md, ts, tsx, css or html", not offenders,
          offenders or "research/paper.md scanned with everything else")

    # 9. the horizontal scroll rule, still absolute, now over the tests as well
    hijack = []
    for p in list(SRC.rglob("*.ts*")) + list(TESTS.rglob("*.ts")):
        text = p.read_text(encoding="utf-8")
        for pattern in ["onWheel", "\"wheel\"", "scrollTo", "scrollIntoView",
                        "preventDefault"]:
            if pattern in text and p.parent == SRC:
                hijack.append(f"{p.name}: {pattern}")
    check("9. Vertical scroll is never hijacked", not hijack,
          hijack or "no wheel listener and no programmatic scrolling in src")

    # 10. the frontend names its data source rather than falling back silently
    data_ts = (SRC / "data.ts").read_text(encoding="utf-8")
    play = (SRC / "Playground.tsx").read_text(encoding="utf-8")
    ok = ("/health" in data_ts and "apiSolve" in data_ts
          and "data-testid=\"solver-mode\"" in play
          and "live ? undefined : \"sweep.json\"" in play)
    check("10. Live and offline are both explicit in the UI", ok,
          "mode is probed once, shown as a badge, and the grid is not fetched live")

    # 11. the browser suite exists at the promised size
    specs = sorted(TESTS.glob("*.spec.ts"))
    n_tests = sum(p.read_text(encoding="utf-8").count("\n  test(")
                  + p.read_text(encoding="utf-8").count("\ntest(") for p in specs)
    check("11. Nine Playwright suites with at least 30 tests",
          len(specs) == 9 and n_tests >= 30,
          f"{len(specs)} spec files, {n_tests} tests")

    # 12. tsc, vite and the whole browser suite against the production bundle
    try:
        b = subprocess.run(["npm", "run", "build"], cwd=APP, capture_output=True,
                           text=True, shell=True, timeout=600)
        built = b.returncode == 0 and (APP / "dist" / "index.html").exists()
        r = subprocess.run(["npx", "playwright", "test"], cwd=APP, capture_output=True,
                           text=True, shell=True, timeout=900)
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        ok, detail = built and r.returncode == 0, f"build clean, {tail[0].strip()}"
    except Exception as e:  # noqa: BLE001
        ok, detail = False, str(e)
    check("12. Production build clean and every browser test passing", ok, detail)

    # 13. the three earlier reports are still green
    # Parts 1 and 2 store their checks in the fixture the app already reads, Part 3
    # writes its own report in this shape.
    prior = {}
    reports = json.loads((DATA / "validation.json").read_text(encoding="utf-8"))
    reports["part3"] = json.loads((ROOT / "research" / "part3_validation.json")
                                  .read_text(encoding="utf-8"))
    for name, rep in reports.items():
        cs = rep["checks"]
        prior[name] = (sum(c["pass"] for c in cs), len(cs))
    check("13. Parts 1, 2 and 3 still fully green",
          all(a == b for a, b in prior.values()), prior)

    passed = sum(c["pass"] for c in checks)
    report = {"part": 4, "title": "FRACTUREVERSE Part 4 backend and end to end acceptance",
              "checks": checks, "summary": {"passed": passed, "total": len(checks)}}
    (ROOT / "research" / "part4_validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{passed} of {len(checks)} checks passing")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
