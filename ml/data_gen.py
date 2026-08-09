"""Trajectory generation for the fatigue life surrogates.

500 crack growth trajectories per domain from physics.lefm.crack_growth_history:
5 initial crack lengths x 5 stress amplitudes x 4 stress ratios x 5 material
parameter samples drawn inside the uncertainty ranges carried in materials.json.

Everything is seeded. Running this twice produces byte identical files.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace

import numpy as np

from physics import lefm
from physics.materials import Material, get_material

from . import ARTIFACTS, SEED

N_POINTS = 200          # samples per trajectory
N_MATERIAL_SAMPLES = 5  # sample 0 is always the nominal material


@dataclass(frozen=True)
class DomainSweep:
    domain: str
    material: str
    geometry: str
    W: float
    a0_mm: tuple
    sigma_MPa: tuple
    R: tuple = (0.0, 0.1, 0.3, 0.5)


SWEEPS = (
    DomainSweep("aerospace", "Al2024-T3", "center", 0.10,
                (0.5, 0.75, 1.0, 1.5, 2.0), (100.0, 125.0, 150.0, 175.0, 200.0)),
    DomainSweep("biomedical", "CorticalBone_healthy", "edge", 0.02,
                (0.05, 0.075, 0.10, 0.15, 0.20), (25.0, 32.5, 40.0, 47.5, 55.0)),
    DomainSweep("civil", "Concrete_normal", "edge", 0.20,
                (2.0, 3.5, 5.0, 7.5, 10.0), (1.0, 1.5, 2.0, 2.5, 3.0)),
)


def material_samples(mat: Material, n: int, rng: np.random.Generator) -> list[Material]:
    """Sample n materials inside the published uncertainty ranges. Sample 0 is nominal."""
    unc = mat.raw.get("uncertainty", {})
    c_lo, c_hi = unc.get("paris_C_range", (mat.paris_C, mat.paris_C))
    m_lo, m_hi = unc.get("paris_m_range", (mat.paris_m, mat.paris_m))
    e_lo, e_hi = unc.get("E_range", (mat.E, mat.E))
    out = [mat]
    for _ in range(n - 1):
        # C spans orders of magnitude in bone, so sample it log uniform
        c = float(np.exp(rng.uniform(np.log(c_lo), np.log(c_hi))))
        out.append(replace(mat, paris_C=c,
                           paris_m=float(rng.uniform(m_lo, m_hi)),
                           E=float(rng.uniform(e_lo, e_hi))))
    return out


def generate_domain(sweep: DomainSweep, rng: np.random.Generator) -> dict:
    mat = get_material(sweep.domain, sweep.material)
    mats = material_samples(mat, N_MATERIAL_SAMPLES, rng)

    seq, meta = [], []
    for si, m in enumerate(mats):
        for a0_mm in sweep.a0_mm:
            for s_MPa in sweep.sigma_MPa:
                for R in sweep.R:
                    a0 = a0_mm * 1e-3
                    sigma = s_MPa * 1e6
                    a_c = lefm.critical_crack_length(sigma, m.K_IC, sweep.W, sweep.geometry)
                    if not (a0 < 0.9 * a_c):
                        continue  # already unstable, no fatigue life to learn
                    h = lefm.crack_growth_history(a0, sigma, R, m, W=sweep.W,
                                                  geometry=sweep.geometry,
                                                  n_points=N_POINTS, a_c=a_c)
                    seq.append(np.stack([h["a"], h["N"], h["delta_K"],
                                         h["da_dN"], h["K_ratio"]], axis=1))
                    meta.append({
                        "domain": sweep.domain, "material": m.key,
                        "material_sample": si, "a0": a0, "sigma_max": sigma,
                        "R": R, "W": sweep.W, "geometry": sweep.geometry,
                        "paris_C": m.paris_C, "paris_m": m.paris_m, "E": m.E,
                        "K_IC": m.K_IC, "sigma_Y": m.sigma_Y, "nu": m.nu,
                        "a_c": h["a_c"], "N_f": h["N_f"],
                        "years_to_failure": lefm.cycles_to_years(h["N_f"], sweep.domain),
                    })
    return {"sequences": np.asarray(seq, dtype=np.float32), "meta": meta}


def build(force: bool = False) -> dict:
    """Generate every domain and write ml/artifacts/trajectories_<domain>.npz."""
    out_meta = ARTIFACTS / "trajectories_meta.json"
    if out_meta.exists() and not force:
        return json.loads(out_meta.read_text())

    t0 = time.perf_counter()
    manifest = {"seed": SEED, "n_points": N_POINTS, "domains": {}}
    for sweep in SWEEPS:
        rng = np.random.default_rng(SEED + hash(sweep.domain) % 10_000)
        d = generate_domain(sweep, rng)
        np.savez_compressed(ARTIFACTS / f"trajectories_{sweep.domain}.npz",
                            sequences=d["sequences"])
        manifest["domains"][sweep.domain] = {
            "n_trajectories": len(d["meta"]),
            "n_requested": len(sweep.a0_mm) * len(sweep.sigma_MPa) * len(sweep.R)
                           * N_MATERIAL_SAMPLES,
            "material": sweep.material, "geometry": sweep.geometry, "W": sweep.W,
            "channels": ["a", "N", "delta_K", "da_dN", "K_ratio"],
            "meta": d["meta"],
        }
    manifest["wall_clock_s"] = round(time.perf_counter() - t0, 2)
    out_meta.write_text(json.dumps(manifest))
    return manifest


def load(domain: str) -> tuple[np.ndarray, list[dict]]:
    man = json.loads((ARTIFACTS / "trajectories_meta.json").read_text())
    seq = np.load(ARTIFACTS / f"trajectories_{domain}.npz")["sequences"]
    return seq, man["domains"][domain]["meta"]


if __name__ == "__main__":
    man = build(force=True)
    for d, blk in man["domains"].items():
        print(f"{d}: {blk['n_trajectories']} / {blk['n_requested']} trajectories")
    print(f"wall clock {man['wall_clock_s']} s -> {ARTIFACTS}")
