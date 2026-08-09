"""Single entry point that routes (domain, material, theory) to an implementation.

The frontend and the FastAPI layer only ever talk to this module, so adding a
theory or a domain does not ripple through the application.

    solve(domain="aerospace", theory="lefm", ...)  ->  dict of results

Every theory returns a dict with a common core so the UI can render one set of
readouts: K_I, K_II, G, a, a_c, N_f where the theory can supply them, plus a
theory specific block.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import numpy as np

from . import epfm, lefm, peridynamic, xfem
from .materials import DEFAULT_MATERIAL, Material, domain_metadata, get_material
from .mesh import crack_aligned_mesh

Theory = Literal["lefm", "epfm", "xfem", "peridynamic"]

THEORY_BLURB = {
    "lefm": "Linear elastic fracture mechanics. One number, K_I, controls the whole "
            "crack tip field as long as the plastic zone stays small.",
    "epfm": "Elastic plastic fracture mechanics. The J integral measures the energy "
            "flowing to the tip when the plastic zone is no longer small.",
    "xfem": "Extended finite element method. Enrichment functions let the crack cut "
            "through elements, so the mesh never has to follow the crack.",
    "peridynamic": "Peridynamics. Bonds between material points break on their own, "
                   "so cracks nucleate and branch without any predefined path.",
}

THEORY_FOR_DOMAIN = {
    "aerospace": ["lefm", "epfm", "xfem", "peridynamic"],
    "biomedical": ["lefm", "epfm", "xfem", "peridynamic"],
    "civil": ["lefm", "epfm", "xfem", "peridynamic"],
}

RECOMMENDED_THEORY = {
    "aerospace": "lefm",
    "biomedical": "epfm",
    "civil": "peridynamic",
}


@dataclass
class LoadCase:
    sigma_max: float = 150e6      # Pa
    R: float = 0.1                # stress ratio
    mode: Literal["I", "II", "mixed"] = "I"
    beta_deg: float = 0.0         # crack inclination for mixed mode
    frequency_hz: float = 1.0

    @property
    def sigma_range(self) -> float:
        return self.sigma_max * (1.0 - max(self.R, 0.0))


@dataclass
class CrackConfig:
    a0: float = 1e-3                     # m
    geometry: str = "center"
    W: float = 0.1                       # m
    thickness: float = 0.005             # m
    orientation_deg: float = 0.0


@dataclass
class SolveRequest:
    domain: str = "aerospace"
    material: str | None = None
    theory: Theory = "lefm"
    load: LoadCase = field(default_factory=LoadCase)
    crack: CrackConfig = field(default_factory=CrackConfig)
    growth_law: str = "paris"
    mesh_nx: int = 61
    mesh_ny: int = 121

    def resolved_material(self) -> Material:
        return get_material(self.domain, self.material or DEFAULT_MATERIAL[self.domain])


def _common_block(mat: Material, req: SolveRequest) -> dict[str, Any]:
    return {
        "domain": req.domain,
        "material": mat.key,
        "material_name": mat.name,
        "theory": req.theory,
        "theory_blurb": THEORY_BLURB[req.theory],
        "E_GPa": mat.E / 1e9,
        "nu": mat.nu,
        "sigma_Y_MPa": mat.sigma_Y / 1e6,
        "K_IC": mat.K_IC,
        "paris_C": mat.paris_C,
        "paris_m": mat.paris_m,
        "sigma_max_MPa": req.load.sigma_max / 1e6,
        "R": req.load.R,
        "a_0": req.crack.a0,
        "geometry": req.crack.geometry,
        "W": req.crack.W,
    }


# ---------------------------------------------------------------------------
# Theory routers
# ---------------------------------------------------------------------------

def _solve_lefm(req: SolveRequest, mat: Material) -> dict[str, Any]:
    c, ld = req.crack, req.load
    if ld.mode == "II":
        beta = 90.0 - 1e-9
    elif ld.mode == "mixed":
        beta = ld.beta_deg if ld.beta_deg > 0 else 45.0
    else:
        beta = 0.0
    K_I, K_II = lefm.stress_intensity_mixed(ld.sigma_max, c.a0, beta, c.W, c.geometry)

    life = lefm.cycles_to_failure(c.a0, ld.sigma_max, ld.R, mat, c.W, c.geometry,
                                  law=req.growth_law)
    hist = lefm.crack_growth_history(c.a0, ld.sigma_max, ld.R, mat, c.W, c.geometry,
                                     law=req.growth_law, a_c=life["a_c"])
    dK = lefm.stress_intensity(ld.sigma_range, c.a0, c.W, c.geometry)
    rate = float(lefm.paris_rate(dK, mat.paris_C, mat.paris_m)) if req.growth_law == "paris" \
        else float(lefm.walker_rate(dK, ld.R, mat.paris_C, mat.paris_m, mat.walker_gamma))

    out = _common_block(mat, req)
    out.update({
        "K_I": K_I, "K_II": K_II,
        "G": lefm.energy_release_rate(K_I, K_II, mat=mat),
        "delta_K": dK, "da_dN": rate,
        "a_c": life["a_c"], "N_f": life["N_f"],
        "K_ratio": K_I / mat.K_IC,
        "plastic_zone": lefm.plastic_zone_size(K_I, mat),
        "ssy_valid": lefm.small_scale_yielding_ok(K_I, c.a0, mat),
        "years_to_failure": lefm.cycles_to_years(life["N_f"], req.domain),
        "history": {k: np.asarray(v).tolist() for k, v in hist.items()
                    if isinstance(v, np.ndarray)},
        "growth_law": req.growth_law,
    })
    return out


def _solve_epfm(req: SolveRequest, mat: Material) -> dict[str, Any]:
    c, ld = req.crack, req.load
    K_I = lefm.stress_intensity(ld.sigma_max, c.a0, c.W, c.geometry)
    J_el = epfm.J_from_K(K_I, mat)
    J_ep = epfm.j_elastic_plastic(K_I, ld.sigma_max, mat)
    R = epfm.jr_curve(mat)
    da = np.geomspace(1e-6, 0.02, 120)

    out = _common_block(mat, req)
    out.update({
        "K_I": K_I, "K_II": 0.0,
        "G": lefm.energy_release_rate(K_I, mat=mat),
        "J_elastic": J_el,
        "J_elastic_plastic": J_ep,
        "J_IC": mat.J_IC,
        "J_ratio": J_ep / mat.J_IC,
        "ctod": epfm.ctod(J_ep, mat),
        "ctod_critical": epfm.ctod_critical(mat),
        "jr_curve": {"delta_a": da.tolist(), "J": R.J(da).tolist(),
                     "J_IC": R.J_IC, "n": R.n, "delta_a_ref": R.delta_a_ref},
        "instability": epfm.instability_point(mat, ld.sigma_max, c.a0, c.W, c.geometry),
        "a_c": lefm.critical_crack_length(ld.sigma_max, mat.K_IC, c.W, c.geometry),
    })
    return out


def _solve_xfem(req: SolveRequest, mat: Material) -> dict[str, Any]:
    c, ld = req.crack, req.load
    W = c.W
    H = 2.0 * W
    mesh = crack_aligned_mesh(W, H, req.mesh_nx, req.mesh_ny)
    if c.geometry == "edge":
        crack = xfem.edge_crack(W, H, c.a0)
    else:
        crack = xfem.straight_center_crack(W, H, c.a0)
    solver = xfem.XFEMSolver(mesh, mat, crack, thickness=c.thickness)
    sol = solver.solve(ld.sigma_max)
    ii = solver.interaction_integral(sol.u, tip_id=0)
    jj = epfm.j_integral(solver, sol.u, tip_id=0)

    out = _common_block(mat, req)
    out.update({
        "K_I": ii["K_I"], "K_II": ii["K_II"],
        "K_I_analytical": lefm.stress_intensity(ld.sigma_max, c.a0, W, c.geometry),
        "G": lefm.energy_release_rate(ii["K_I"], ii["K_II"], mat=mat),
        "J_from_xfem": jj["J"],
        "kink_angle_deg": np.degrees(xfem.XFEMSolver.kink_angle(ii["K_I"], ii["K_II"])),
        "K_eff": xfem.XFEMSolver.effective_K(ii["K_I"], ii["K_II"]),
        "a_c": lefm.critical_crack_length(ld.sigma_max, mat.K_IC, W, c.geometry),
        "mesh": mesh.summary(),
        "xfem_info": sol.info,
        "interaction_integral": {k: v for k, v in ii.items()},
    })
    out["_solver"] = solver
    out["_u"] = sol.u
    return out


def _solve_peridynamic(req: SolveRequest, mat: Material) -> dict[str, Any]:
    G0 = mat.raw.get("G_f", mat.G_c)
    res = peridynamic.concrete_branching_panel(mat, G0=G0)
    model = res.pop("model")
    damage = res.pop("damage")
    res.pop("u", None)
    res.pop("frames", None)

    out = _common_block(mat, req)
    out.update({k: v for k, v in res.items()})
    out.update({
        "damage_grid_shape": list(damage.shape),
        "damage_max": float(damage.max()),
        "damage_mean": float(damage.mean()),
        "energy_check": model.verify_energy_release_rate(),
        "K_I": None, "K_II": None,
        "note": "Peridynamics does not use a stress intensity factor. The damage "
                "field and the bond breaking history replace it.",
    })
    out["_damage"] = damage
    return out


_ROUTER = {
    "lefm": _solve_lefm,
    "epfm": _solve_epfm,
    "xfem": _solve_xfem,
    "peridynamic": _solve_peridynamic,
}


def solve(req: SolveRequest | None = None, **kw) -> dict[str, Any]:
    """Route a request to the right theory implementation.

    Accepts either a SolveRequest or keyword arguments that build one.
    """
    if req is None:
        load = kw.pop("load", None) or LoadCase(**kw.pop("load_kw", {}))
        crack = kw.pop("crack", None) or CrackConfig(**kw.pop("crack_kw", {}))
        req = SolveRequest(load=load, crack=crack, **kw)
    if req.theory not in _ROUTER:
        raise ValueError(f"unknown theory {req.theory!r}, expected {list(_ROUTER)}")
    mat = req.resolved_material()
    return _ROUTER[req.theory](req, mat)


def capabilities() -> dict[str, Any]:
    """Everything the frontend needs to build its selectors, in one call."""
    return {
        "domains": {d: domain_metadata(d) for d in ("aerospace", "biomedical", "civil")},
        "theories": [{"key": k, "label": k.upper() if k != "peridynamic" else "Peridynamics",
                      "blurb": v} for k, v in THEORY_BLURB.items()],
        "theory_for_domain": THEORY_FOR_DOMAIN,
        "recommended_theory": RECOMMENDED_THEORY,
        "geometries": list(lefm.GEOMETRY_LABELS.keys()),
        "geometry_labels": lefm.GEOMETRY_LABELS,
        "growth_laws": ["paris", "walker", "forman"],
        "modes": ["I", "II", "mixed"],
    }


def request_from_dict(d: dict) -> SolveRequest:
    """Build a SolveRequest from a plain dict, which is what the API receives."""
    load = LoadCase(**d.get("load", {}))
    crack = CrackConfig(**d.get("crack", {}))
    rest = {k: v for k, v in d.items() if k not in ("load", "crack")}
    return SolveRequest(load=load, crack=crack, **rest)


def to_json_safe(d: dict) -> dict:
    """Strip solver objects and numpy arrays so a result can be serialised."""
    out = {}
    for k, v in d.items():
        if k.startswith("_"):
            continue
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, (np.floating, np.integer)):
            out[k] = v.item()
        elif isinstance(v, dict):
            out[k] = to_json_safe(v)
        else:
            out[k] = v
    return out


__all__ = ["solve", "capabilities", "SolveRequest", "LoadCase", "CrackConfig",
           "request_from_dict", "to_json_safe", "THEORY_BLURB", "Theory"]
