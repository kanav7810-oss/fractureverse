"""Material database loader for the three FRACTUREVERSE domains.

All properties are stored in SI base units inside data/<domain>/materials.json
with one exception that is universal in the fracture literature: fracture
toughness K_IC and stress intensity factors are carried in MPa*sqrt(m), and
Paris Law coefficient C is expressed so that da/dN comes out in m/cycle when
delta_K is supplied in MPa*sqrt(m). Every function in this package follows that
same convention, so no unit juggling is needed at call sites.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"

DOMAINS = ("aerospace", "biomedical", "civil")

DEFAULT_MATERIAL = {
    "aerospace": "Al2024-T3",
    "biomedical": "CorticalBone_healthy",
    "civil": "Concrete_normal",
}


@dataclass
class Material:
    """One material with everything the four theories need."""

    key: str
    domain: str
    name: str
    E: float                 # Young modulus, Pa
    nu: float                # Poisson ratio
    rho: float               # density, kg/m^3
    sigma_Y: float           # yield or tensile strength, Pa
    K_IC: float              # fracture toughness, MPa*sqrt(m)
    paris_C: float           # da/dN = C * delta_K^m, m/cycle with delta_K in MPa*sqrt(m)
    paris_m: float
    walker_gamma: float
    J_IC: float              # J/m^2
    JR_exponent_n: float
    JR_delta_a_ref: float
    plane_strain: bool
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def G(self) -> float:
        """Shear modulus, Pa."""
        return self.E / (2.0 * (1.0 + self.nu))

    @property
    def K_bulk(self) -> float:
        """Bulk modulus, Pa."""
        return self.E / (3.0 * (1.0 - 2.0 * self.nu))

    @property
    def E_eff(self) -> float:
        """Effective modulus E' used in G = K^2 / E', Pa."""
        if self.plane_strain:
            return self.E / (1.0 - self.nu ** 2)
        return self.E

    @property
    def G_c(self) -> float:
        """Critical energy release rate from K_IC, J/m^2. K_IC is in MPa*sqrt(m)."""
        k_pa = self.K_IC * 1.0e6
        return k_pa ** 2 / self.E_eff

    def kappa(self, plane_strain: bool | None = None) -> float:
        """Kolosov constant used by the crack tip asymptotic fields."""
        ps = self.plane_strain if plane_strain is None else plane_strain
        if ps:
            return 3.0 - 4.0 * self.nu
        return (3.0 - self.nu) / (1.0 + self.nu)


@lru_cache(maxsize=None)
def _load_domain(domain: str) -> dict[str, Any]:
    if domain not in DOMAINS:
        raise ValueError(f"unknown domain {domain!r}, expected one of {DOMAINS}")
    path = DATA_ROOT / domain / "materials.json"
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def domain_metadata(domain: str) -> dict[str, Any]:
    """Cycle frequency, inspection interval and real world impact anchors."""
    blob = _load_domain(domain)
    return {
        "domain": domain,
        "cycle_frequency_per_year": blob["cycle_frequency_per_year"],
        "cycle_frequency_note": blob["cycle_frequency_note"],
        "inspection_interval_note": blob["inspection_interval_note"],
        "impact": blob["impact"],
        "materials": list(blob["materials"].keys()),
    }


def list_materials(domain: str) -> list[str]:
    return list(_load_domain(domain)["materials"].keys())


def get_material(domain: str, key: str | None = None) -> Material:
    """Fetch a material. Passing key=None returns the domain default."""
    blob = _load_domain(domain)
    key = key or DEFAULT_MATERIAL[domain]
    if key not in blob["materials"]:
        raise KeyError(f"material {key!r} not in domain {domain!r}: {list_materials(domain)}")
    m = blob["materials"][key]
    return Material(
        key=key,
        domain=domain,
        name=m["name"],
        E=float(m["E"]),
        nu=float(m["nu"]),
        rho=float(m["rho"]),
        sigma_Y=float(m["sigma_Y"]),
        K_IC=float(m["K_IC"]),
        paris_C=float(m["paris_C"]),
        paris_m=float(m["paris_m"]),
        walker_gamma=float(m.get("walker_gamma", 0.5)),
        J_IC=float(m["J_IC"]),
        JR_exponent_n=float(m["JR_exponent_n"]),
        JR_delta_a_ref=float(m["JR_delta_a_ref"]),
        plane_strain=bool(m.get("plane_strain", False)),
        raw=m,
    )


def use_anchored_paris(mat: Material) -> Material:
    """Return a copy using the literature anchored Paris coefficient where one exists.

    The project specification pins 2024-T3 at C = 3.6e-10, which sits at the
    conservative top of the published scatter band. This helper swaps in the value
    that reproduces the commonly cited anchor da/dN = 2.0e-7 m/cycle at
    delta_K = 10 MPa*sqrt(m), so a study can report both and state which was used.
    """
    c_alt = mat.raw.get("paris_C_anchored")
    if c_alt is None:
        return mat
    import copy
    out = copy.replace(mat, paris_C=float(c_alt)) if hasattr(copy, "replace") else None
    if out is None:
        from dataclasses import replace
        out = replace(mat, paris_C=float(c_alt))
    return out


def all_materials() -> dict[str, Material]:
    """Every material across every domain, keyed 'domain/material'."""
    out: dict[str, Material] = {}
    for d in DOMAINS:
        for k in list_materials(d):
            out[f"{d}/{k}"] = get_material(d, k)
    return out


def keller_modulus(rho_apparent_g_cm3: float) -> float:
    """Keller 1994 power law. Apparent density in g/cm^3 to Young modulus in Pa."""
    if rho_apparent_g_cm3 <= 0.0:
        raise ValueError("apparent density must be positive")
    return 10.5 * rho_apparent_g_cm3 ** 2.29 * 1.0e9


def load_json(domain: str, filename: str) -> dict[str, Any]:
    """Read any auxiliary data file inside data/<domain>/."""
    with open(DATA_ROOT / domain / filename, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_reference(filename: str = "paris_law_reference.json") -> dict[str, Any]:
    with open(DATA_ROOT / "reference_charts" / filename, "r", encoding="utf-8") as fh:
        return json.load(fh)
