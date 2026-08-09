"""Linear elastic fracture mechanics.

Stress intensity factors, geometry correction factors, Paris and Walker crack
growth laws, critical crack length and cycles to failure.

Unit convention used everywhere in this module:
  crack length a, plate width W, thickness B  -> metres
  applied stress sigma                        -> pascals on the API surface
  stress intensity factor K                   -> MPa*sqrt(m)
  Paris coefficient C, exponent m             -> da/dN in m/cycle for delta_K in MPa*sqrt(m)

Converting sigma from Pa to MPa happens inside the module so callers stay in SI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

from .materials import Material

Geometry = Literal["center", "edge", "compact", "through", "surface", "infinite"]

GEOMETRY_LABELS = {
    "infinite": "Infinite plate, F = 1",
    "center": "Center cracked tension panel, Feddersen secant",
    "edge": "Single edge notched tension, Tada polynomial",
    "compact": "Compact tension specimen, ASTM E399",
    "through": "Through thickness crack in a finite width plate",
    "surface": "Semi elliptical surface crack, Newman and Raju",
}


# ---------------------------------------------------------------------------
# Geometry correction factors F(a/W)
# ---------------------------------------------------------------------------

def F_center(a: float, W: float) -> float:
    """Center cracked tension panel. a is the HALF crack length, W the FULL width.

    Feddersen secant formula. Better than 0.3 percent for a/(W/2) below 0.7.
    """
    x = a / W
    if not 0.0 < x < 0.5:
        raise ValueError(f"center crack needs 0 < a/W < 0.5, got {x:.4f}")
    return math.sqrt(1.0 / math.cos(math.pi * x))


def F_edge(a: float, W: float) -> float:
    """Single edge notched tension. Tada, Paris and Irwin handbook polynomial."""
    x = a / W
    if not 0.0 < x < 0.7:
        raise ValueError(f"edge crack needs 0 < a/W < 0.7, got {x:.4f}")
    return 1.12 - 0.231 * x + 10.55 * x ** 2 - 21.72 * x ** 3 + 30.39 * x ** 4


def F_compact(a: float, W: float) -> float:
    """Compact tension, ASTM E399.

    The standard form is K = P / (B * sqrt(W)) * f(a/W). FRACTUREVERSE keeps a
    single K = sigma * sqrt(pi*a) * F signature everywhere, with the reference
    stress defined as sigma = P / (B*W). Equating the two gives
    F = f(a/W) * sqrt(W / (pi*a)).
    """
    x = a / W
    if not 0.2 <= x <= 0.8:
        raise ValueError(f"compact tension is standardised for 0.2 <= a/W <= 0.8, got {x:.4f}")
    f = ((2.0 + x) * (0.886 + 4.64 * x - 13.32 * x ** 2 + 14.72 * x ** 3 - 5.6 * x ** 4)
         / (1.0 - x) ** 1.5)
    return f * math.sqrt(W / (math.pi * a))


def F_through(a: float, W: float) -> float:
    """Through thickness crack in a finite width plate. Same secant family as center."""
    return F_center(a, W)


def F_surface(a: float, W: float, c_over_a: float = 1.0, thickness: float | None = None) -> float:
    """Semi elliptical surface crack, Newman and Raju shape factor at the deepest point.

    Reduced form valid for a/t below 0.8 and a/c between 0.2 and 1.0. The elliptic
    integral Q is the dominant term, the finite thickness term is the correction.
    """
    a_over_c = 1.0 / c_over_a if c_over_a > 0 else 1.0
    Q = 1.0 + 1.464 * min(a_over_c, 1.0) ** 1.65
    t = thickness if thickness is not None else W
    lam = min(a / t, 0.8)
    M = 1.13 - 0.09 * a_over_c + (0.89 / (0.2 + a_over_c) - 0.54) * lam ** 2
    return M / math.sqrt(Q)


_F_TABLE: dict[str, Callable[..., float]] = {
    "infinite": lambda a, W: 1.0,
    "center": F_center,
    "edge": F_edge,
    "compact": F_compact,
    "through": F_through,
    "surface": F_surface,
}


def geometry_factor(a: float, W: float, geometry: Geometry = "center", **kw) -> float:
    """Dispatch to the right F(a/W)."""
    if geometry not in _F_TABLE:
        raise ValueError(f"unknown geometry {geometry!r}, expected {list(_F_TABLE)}")
    return _F_TABLE[geometry](a, W, **kw)


# ---------------------------------------------------------------------------
# Stress intensity factor
# ---------------------------------------------------------------------------

def stress_intensity(sigma_pa: float, a: float, W: float = 1.0,
                     geometry: Geometry = "center", **kw) -> float:
    """K_I in MPa*sqrt(m). sigma_pa in Pa, a and W in m."""
    F = geometry_factor(a, W, geometry, **kw)
    return (sigma_pa / 1.0e6) * math.sqrt(math.pi * a) * F


def stress_intensity_mixed(sigma_pa: float, a: float, beta_deg: float,
                           W: float = 1.0, geometry: Geometry = "center", **kw
                           ) -> tuple[float, float]:
    """Mixed mode K_I and K_II for a crack inclined at beta from the loading normal.

    A crack at angle beta to the plane perpendicular to the remote tension resolves
    the far field stress into a normal and a shear component on the crack plane:
      K_I  = sigma * cos^2(beta) * sqrt(pi*a) * F
      K_II = sigma * sin(beta) * cos(beta) * sqrt(pi*a) * F
    beta = 0 is pure mode I, beta = 90 degrees is a crack parallel to the load.
    """
    b = math.radians(beta_deg)
    base = (sigma_pa / 1.0e6) * math.sqrt(math.pi * a) * geometry_factor(a, W, geometry, **kw)
    return base * math.cos(b) ** 2, base * math.sin(b) * math.cos(b)


def energy_release_rate(K_I: float, K_II: float = 0.0, K_III: float = 0.0,
                        *, mat: Material) -> float:
    """G in J/m^2 from K values in MPa*sqrt(m). G = K_I^2/E' + K_II^2/E' + K_III^2/(2*mu)."""
    e_prime = mat.E_eff
    mu = mat.G
    return ((K_I * 1e6) ** 2 / e_prime
            + (K_II * 1e6) ** 2 / e_prime
            + (K_III * 1e6) ** 2 / (2.0 * mu))


def plastic_zone_size(K_I: float, mat: Material) -> float:
    """Irwin plastic zone radius in m. Plane stress uses 1/(2pi), plane strain 1/(6pi)."""
    coeff = 1.0 / (6.0 * math.pi) if mat.plane_strain else 1.0 / (2.0 * math.pi)
    return coeff * ((K_I * 1e6) / mat.sigma_Y) ** 2


def small_scale_yielding_ok(K_I: float, a: float, mat: Material, ratio: float = 0.02) -> bool:
    """LEFM validity check. Plastic zone should stay small against the crack length."""
    return plastic_zone_size(K_I, mat) <= ratio * a


# ---------------------------------------------------------------------------
# Crack growth laws
# ---------------------------------------------------------------------------

def paris_rate(delta_K, C: float, m: float, delta_K_th: float = 0.0):
    """Paris Law da/dN in m/cycle. Growth is clipped to zero below the threshold."""
    dk = np.asarray(delta_K, dtype=float)
    rate = C * np.clip(dk, 1e-30, None) ** m
    return np.where(dk > delta_K_th, rate, 0.0)


def walker_rate(delta_K, R: float, C: float, m: float, gamma: float,
                delta_K_th: float = 0.0):
    """Walker equation. Collapses stress ratio effects onto a single Paris line.

    da/dN = C * ( delta_K / (1 - R)^(1 - gamma) )^m
    R below zero is clamped to zero because compressive excursions do not grow the crack.
    """
    r = min(max(R, 0.0), 0.95)
    dk_eff = np.asarray(delta_K, dtype=float) / (1.0 - r) ** (1.0 - gamma)
    return paris_rate(dk_eff, C, m, delta_K_th)


def forman_rate(delta_K, R: float, C: float, m: float, K_IC: float):
    """Forman equation. Adds the accelerating approach to K_IC that Paris misses."""
    r = min(max(R, 0.0), 0.95)
    dk = np.asarray(delta_K, dtype=float)
    denom = np.clip((1.0 - r) * K_IC - dk, 1e-6, None)
    return C * dk ** m / denom


# ---------------------------------------------------------------------------
# Critical crack length and life
# ---------------------------------------------------------------------------

def critical_crack_length(sigma_max_pa: float, K_IC: float, W: float = 1.0,
                          geometry: Geometry = "center", a_min: float = 1e-6,
                          **kw) -> float:
    """Solve K_I(a_c) = K_IC for a_c in m.

    F depends on a for every finite geometry, so this is an implicit root find
    rather than the textbook a_c = (1/pi)*(K_IC/(sigma*F))^2 closed form.
    """
    if sigma_max_pa <= 0.0:
        raise ValueError("sigma_max must be positive")

    upper = {"center": 0.499, "through": 0.499, "edge": 0.699, "compact": 0.799}.get(geometry, 0.95)
    a_hi = upper * W * 0.999

    def residual(a: float) -> float:
        return stress_intensity(sigma_max_pa, a, W, geometry, **kw) - K_IC

    if residual(a_min) >= 0.0:
        return a_min          # already critical at the smallest resolvable flaw
    if residual(a_hi) <= 0.0:
        return a_hi           # net section limited rather than toughness limited
    return brentq(residual, a_min, a_hi, xtol=1e-12, rtol=1e-12)


def cycles_to_failure(a0: float, sigma_max_pa: float, R: float, mat: Material,
                      W: float = 1.0, geometry: Geometry = "center",
                      law: Literal["paris", "walker", "forman"] = "paris",
                      a_c: float | None = None, **kw) -> dict:
    """Integrate da / (da/dN) from a0 to a_c numerically.

    Returns a dict with N_f, a_c, delta_K at both ends and the integration report.
    """
    if a_c is None:
        a_c = critical_crack_length(sigma_max_pa, mat.K_IC, W, geometry, **kw)
    if a0 >= a_c:
        return {"N_f": 0.0, "a_0": a0, "a_c": a_c, "already_critical": True,
                "law": law, "geometry": geometry}

    sigma_range_pa = sigma_max_pa * (1.0 - max(R, 0.0))

    def dadn(a: float) -> float:
        dK = stress_intensity(sigma_range_pa, a, W, geometry, **kw)
        if law == "paris":
            rate = float(paris_rate(dK, mat.paris_C, mat.paris_m))
        elif law == "walker":
            rate = float(walker_rate(dK, R, mat.paris_C, mat.paris_m, mat.walker_gamma))
        else:
            rate = float(forman_rate(dK, R, mat.paris_C, mat.paris_m, mat.K_IC))
        return max(rate, 1e-30)

    integrand = lambda a: 1.0 / dadn(a)
    N_f, abserr = quad(integrand, a0, a_c, limit=400, epsabs=1e-3, epsrel=1e-9)

    return {
        "N_f": float(N_f),
        "integration_abserr": float(abserr),
        "a_0": a0,
        "a_c": float(a_c),
        "delta_K_initial": stress_intensity(sigma_range_pa, a0, W, geometry, **kw),
        "delta_K_final": stress_intensity(sigma_range_pa, a_c * 0.999999, W, geometry, **kw),
        "K_max_final": stress_intensity(sigma_max_pa, a_c * 0.999999, W, geometry, **kw),
        "law": law,
        "geometry": geometry,
        "R": R,
        "sigma_max_MPa": sigma_max_pa / 1e6,
        "already_critical": False,
    }


def cycles_to_failure_closed_form(a0: float, a_c: float, sigma_range_pa: float,
                                  C: float, m: float, F: float = 1.0) -> float:
    """Analytical Paris integration for constant F and m not equal to 2.

    N_f = (a0^(1-m/2) - a_c^(1-m/2)) / ( C * (sigma*F)^m * pi^(m/2) * (m/2 - 1) )

    This exists purely as a verification target for the numerical integrator above.
    """
    if abs(m - 2.0) < 1e-12:
        return math.log(a_c / a0) / (C * (sigma_range_pa / 1e6 * F) ** 2 * math.pi)
    p = 1.0 - m / 2.0
    num = a0 ** p - a_c ** p
    den = C * (sigma_range_pa / 1e6 * F) ** m * math.pi ** (m / 2.0) * (m / 2.0 - 1.0)
    return num / den


def crack_growth_history(a0: float, sigma_max_pa: float, R: float, mat: Material,
                         W: float = 1.0, geometry: Geometry = "center",
                         law: str = "paris", n_points: int = 400,
                         a_c: float | None = None, **kw) -> dict:
    """Crack length versus cycle count, sampled geometrically in a for resolution near a_c.

    Returns arrays a, N, delta_K, da_dN and the K_I over K_IC ratio at each point.
    Cycle counts come from cumulative numerical integration of da / (da/dN), so the
    final entry equals cycles_to_failure to within the quadrature tolerance.
    """
    if a_c is None:
        a_c = critical_crack_length(sigma_max_pa, mat.K_IC, W, geometry, **kw)
    a_c = min(a_c, 0.999 * a_c + 1e-12)
    a = np.geomspace(a0, a_c * (1.0 - 1e-9), n_points)

    sigma_range_pa = sigma_max_pa * (1.0 - max(R, 0.0))
    dK = np.array([stress_intensity(sigma_range_pa, ai, W, geometry, **kw) for ai in a])
    Kmax = np.array([stress_intensity(sigma_max_pa, ai, W, geometry, **kw) for ai in a])

    if law == "paris":
        rate = paris_rate(dK, mat.paris_C, mat.paris_m)
    elif law == "walker":
        rate = walker_rate(dK, R, mat.paris_C, mat.paris_m, mat.walker_gamma)
    else:
        rate = forman_rate(dK, R, mat.paris_C, mat.paris_m, mat.K_IC)
    rate = np.clip(rate, 1e-30, None)

    inv = 1.0 / rate
    N = np.concatenate([[0.0], np.cumsum(0.5 * (inv[1:] + inv[:-1]) * np.diff(a))])

    return {
        "a": a, "N": N, "delta_K": dK, "K_max": Kmax, "da_dN": rate,
        "K_ratio": Kmax / mat.K_IC, "a_c": float(a_c), "N_f": float(N[-1]),
        "material": mat.key, "domain": mat.domain, "law": law, "geometry": geometry,
    }


def cycles_to_years(cycles: float, domain: str) -> float:
    """Convert a cycle count to calendar years using the domain duty cycle."""
    from .materials import domain_metadata
    return cycles / domain_metadata(domain)["cycle_frequency_per_year"]


@dataclass
class LEFMResult:
    """Compact container the API and the frontend consume."""
    K_I: float
    K_II: float
    G: float
    a: float
    a_c: float
    N_f: float
    da_dN: float
    K_ratio: float
    plastic_zone: float
    ssy_valid: bool
