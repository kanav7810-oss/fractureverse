"""FRACTUREVERSE Part 4 backend.

    uvicorn api.main:app --port 8000

Everything under /api. Static fixtures that are genuinely precomputed artifacts, the
ML report, the PINN report, the figure captions, are served from disk. The solver
grid is not: /api/solve runs the real solver, which is why sweep.json disappears
from the live path. Stateless, every request builds a fresh solver.

Slow theories are refused unless the caller opts in. xfem propagation is about 21 s
and a peridynamic solve about 24 s, both past a browser default timeout, so the
frontend never asks for them and the precomputed xfem.json and peridynamic.json
fixtures stay the source for those two views.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.infer import predict as predict_life  # noqa: E402
from physics.unified_solver import (capabilities, request_from_dict,  # noqa: E402
                                    solve, to_json_safe)

DATA = ROOT / "app" / "public" / "data"
FIGURES = ROOT / "app" / "public" / "figures"
DIST = ROOT / "app" / "dist"
PAPER_PDF = ROOT / "research" / "fractureverse.pdf"
PAPER_MD = ROOT / "research" / "paper.md"

SLOW_THEORIES = {"xfem", "peridynamic"}

# Fixtures that are precomputed artifacts of Part 1 and Part 2, not solver output.
# sweep.json and curves.json are deliberately absent, the live solver replaces them.
STATIC_FIXTURES = {"capabilities.json", "stats_summary.json", "anchored.json",
                   "xfem.json", "peridynamic.json", "ml.json", "pinn.json",
                   "figures.json", "validation.json"}

app = FastAPI(title="FRACTUREVERSE", version="4.0",
              description="Fracture mechanics solver, surrogate models and figures.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


class LoadIn(BaseModel):
    sigma_max: float = Field(150e6, description="peak stress in pascals")
    R: float = 0.1
    mode: str = "I"
    beta_deg: float = 0.0
    frequency_hz: float = 1.0


class CrackIn(BaseModel):
    a0: float = Field(1e-3, description="initial crack length in metres")
    geometry: str = "center"
    W: float = 0.1
    thickness: float = 0.005
    orientation_deg: float = 0.0


class SolveIn(BaseModel):
    domain: str = "aerospace"
    material: str | None = None
    theory: str = "lefm"
    growth_law: str = "paris"
    load: LoadIn = LoadIn()
    crack: CrackIn = CrackIn()
    mesh_nx: int = 61
    mesh_ny: int = 121
    allow_slow: bool = False


class PredictIn(BaseModel):
    domain: str = "aerospace"
    material: str | None = None
    a0: float = 1e-3
    sigma_max: float = 150e6
    R: float = 0.1
    W: float = 0.1
    geometry: str = "center"
    law: str = "paris"


def _fail(status: int, message: str, hint: str = "") -> HTTPException:
    return HTTPException(status_code=status, detail={"error": message, "hint": hint})


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "fractureverse", "part": 4,
            "live_solver": True, "figures": len(list(FIGURES.glob("*.png")))}


@app.get("/api/capabilities")
def get_capabilities() -> dict[str, Any]:
    return capabilities()


def _thin(history: dict, n: int) -> dict:
    """Growth history at n evenly indexed points. The solver returns 400."""
    if n <= 0:
        return history
    total = len(history["a"])
    if total <= n:
        return history
    step = (total - 1) / (n - 1)
    idx = [round(i * step) for i in range(n)]
    return {k: [v[i] for i in idx] if isinstance(v, list) else v
            for k, v in history.items()}


@app.post("/api/solve")
def post_solve(body: SolveIn,
               history_points: int = Query(40, ge=0, le=400)) -> dict[str, Any]:
    """One fresh solve. Blocking work runs in the threadpool because this is def."""
    if body.theory in SLOW_THEORIES and not body.allow_slow:
        raise _fail(413, f"theory {body.theory} takes tens of seconds",
                    "send allow_slow true if you really want to wait, or read the "
                    "precomputed xfem and peridynamic fixtures")
    payload = body.model_dump(exclude={"allow_slow"})
    try:
        result = solve(request_from_dict(payload))
    except (KeyError, ValueError) as e:
        raise _fail(422, str(e), "geometry_factor rejects a over W outside its valid "
                    "range, center and through below 0.5, compact 0.2 to 0.8")
    out = to_json_safe(result)
    if isinstance(out.get("history"), dict):
        out["history"] = _thin(out["history"], history_points)
    out["request"] = payload
    return out


@app.post("/api/predict")
def post_predict(body: PredictIn) -> dict[str, Any]:
    try:
        return predict_life(**body.model_dump())
    except (KeyError, ValueError) as e:
        raise _fail(422, str(e), "check domain, material and the a over W range")


@app.get("/api/figures")
def list_figures() -> dict[str, Any]:
    return json.loads((DATA / "figures.json").read_text(encoding="utf-8"))


@app.get("/api/figures/{name}")
def get_figure(name: str) -> FileResponse:
    path = (FIGURES / name).with_suffix(".png")
    if path.parent != FIGURES or not path.exists():
        raise _fail(404, f"no figure {name}", "GET /api/figures lists the 17 keys")
    return FileResponse(path, media_type="image/png")


@app.get("/api/report")
def get_report(fmt: str = Query("pdf", pattern="^(pdf|markdown)$")) -> FileResponse:
    path = PAPER_PDF if fmt == "pdf" else PAPER_MD
    if not path.exists():
        raise _fail(503, "the paper has not been built",
                    "run python make_paper.py from the repository root")
    return FileResponse(path, media_type="application/pdf" if fmt == "pdf"
                        else "text/markdown", filename=path.name)


@app.get("/api/data/{name}")
def get_fixture(name: str) -> JSONResponse:
    """Precomputed artifacts only. Solver output comes from /api/solve."""
    if name not in STATIC_FIXTURES:
        raise _fail(404, f"{name} is not served",
                    "sweep.json and curves.json are offline only, the live app calls "
                    "/api/solve instead")
    return JSONResponse(json.loads((DATA / name).read_text(encoding="utf-8")))


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="app")
