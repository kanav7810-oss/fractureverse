"""Elastic plastic fracture mechanics.

Three deliverables:

  J integral   Domain form of Rice's contour integral, evaluated on the same XFEM
               solution the LEFM and XFEM modules use. In the elastic limit it must
               return K_I^2 / E', which is the verification this module ships with.

  J-R curve    Tearing resistance as a power law, J = J_IC * (delta_a / delta_a_ref)^n,
               fitted to or generated from the material database. The crossing of
               the applied J and the J-R curve, together with the tearing modulus
               comparison, marks the onset of unstable tearing.

  CTOD         delta = J / (sigma_Y * m_factor). m_factor is 1 for plane stress and
               2 for plane strain, the usual engineering values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq, curve_fit

from .materials import Material
from .xfem import XFEMSolver


# ---------------------------------------------------------------------------
# J integral
# ---------------------------------------------------------------------------

def j_integral(solver: XFEMSolver, u: np.ndarray, tip_id: int = 0,
               r_factor: float = 3.0) -> dict:
    """Domain form J integral in J/m^2.

        J = integral_A [ sigma_ij du_i/dx1 - W delta_1j ] dq/dxj dA

    with W the strain energy density and q a plateau function that is one on a disc
    of radius r_d around the tip and zero outside. Only elements where grad q is
    non zero contribute, so the singular tip region is never integrated directly.
    """
    m, mat = solver.mesh, solver.mat
    tp = solver.tip_list[tip_id]
    tip_xy = np.asarray(tp["xy"], float)
    alpha = tp["alpha"]
    c, s = math.cos(alpha), math.sin(alpha)
    Q = np.array([[c, s], [-s, c]])

    dx = float(np.diff(m.x).mean())
    dy = float(np.diff(m.y).mean())
    r_d = r_factor * max(dx, dy)
    q_node = (np.linalg.norm(m.nodes - tip_xy, axis=1) <= r_d).astype(float)

    J = 0.0
    used = 0
    for e in range(m.n_elem):
        conn = m.elements[e]
        qn = q_node[conn]
        if qn.max() == 0.0 or qn.min() == 1.0:
            continue
        used += 1
        pts, wts = solver._element_quadrature(e)
        _, gx, gy, dofmap = solver._element_basis(e, pts)

        xlo, xhi, ylo, yhi = m.element_bounds(e)
        ex, ey = xhi - xlo, yhi - ylo
        xi = 2.0 * (pts[:, 0] - xlo) / ex - 1.0
        eta = 2.0 * (pts[:, 1] - ylo) / ey - 1.0
        sx = np.array([-1.0, 1.0, 1.0, -1.0])
        sy = np.array([-1.0, -1.0, 1.0, 1.0])
        dNdx = 0.25 * sx * (1.0 + sy * eta[:, None]) * (2.0 / ex)
        dNdy = 0.25 * sy * (1.0 + sx * xi[:, None]) * (2.0 / ey)
        dq_loc = np.column_stack([dNdx @ qn, dNdy @ qn]) @ Q.T

        ux, uy = u[dofmap[:, 0]], u[dofmap[:, 1]]
        g = np.empty((len(pts), 2, 2))
        g[:, 0, 0] = gx @ ux
        g[:, 0, 1] = gy @ ux
        g[:, 1, 0] = gx @ uy
        g[:, 1, 1] = gy @ uy
        g_loc = np.einsum("ik,pkl,jl->pij", Q, g, Q)

        eps = np.column_stack([g[:, 0, 0], g[:, 1, 1], g[:, 0, 1] + g[:, 1, 0]])
        sig = eps @ solver.D.T
        S = np.zeros((len(pts), 2, 2))
        S[:, 0, 0], S[:, 1, 1] = sig[:, 0], sig[:, 1]
        S[:, 0, 1] = S[:, 1, 0] = sig[:, 2]
        S_loc = np.einsum("ik,pkl,jl->pij", Q, S, Q)

        W_dens = 0.5 * (sig[:, 0] * eps[:, 0] + sig[:, 1] * eps[:, 1] + sig[:, 2] * eps[:, 2])

        t1 = S_loc[:, 0, 0] * g_loc[:, 0, 0] + S_loc[:, 1, 0] * g_loc[:, 1, 0] - W_dens
        t2 = S_loc[:, 0, 1] * g_loc[:, 0, 0] + S_loc[:, 1, 1] * g_loc[:, 1, 0]

        J += float(np.sum((t1 * dq_loc[:, 0] + t2 * dq_loc[:, 1]) * wts))

    e_eff = mat.E / (1.0 - mat.nu ** 2) if solver.plane_strain else mat.E
    return {"J": J, "J_units": "J/m^2", "r_domain": r_d, "r_factor": r_factor,
            "n_ring_elements": used,
            "K_from_J": math.sqrt(max(J, 0.0) * e_eff) / 1e6}


def J_from_K(K_I: float, mat: Material, K_II: float = 0.0) -> float:
    """Elastic J from stress intensity factors. K in MPa*sqrt(m), J in J/m^2."""
    return ((K_I * 1e6) ** 2 + (K_II * 1e6) ** 2) / mat.E_eff


def K_from_J(J: float, mat: Material) -> float:
    """Inverse of J_from_K, returning MPa*sqrt(m)."""
    return math.sqrt(max(J, 0.0) * mat.E_eff) / 1e6


def j_elastic_plastic(K_I: float, sigma_applied_pa: float, mat: Material) -> float:
    """Total J with an Irwin plastic zone correction to the elastic term.

    The effective crack length grows by the plastic zone radius, which raises J
    above the purely elastic value once the applied stress approaches yield.
    """
    Je = J_from_K(K_I, mat)
    ratio = min(sigma_applied_pa / mat.sigma_Y, 0.95)
    return Je / (1.0 - ratio ** 2)


# ---------------------------------------------------------------------------
# J-R tearing resistance curve
# ---------------------------------------------------------------------------

@dataclass
class JRCurve:
    J_IC: float          # J/m^2
    n: float             # power law exponent
    delta_a_ref: float   # m
    material: str = ""

    def J(self, delta_a):
        da = np.maximum(np.asarray(delta_a, dtype=float), 1e-12)
        return self.J_IC * (da / self.delta_a_ref) ** self.n

    def dJ_dda(self, delta_a):
        da = np.maximum(np.asarray(delta_a, dtype=float), 1e-12)
        return self.J_IC * self.n / self.delta_a_ref * (da / self.delta_a_ref) ** (self.n - 1.0)

    def tearing_modulus(self, delta_a, mat: Material):
        """T = (E / sigma_Y^2) * dJ/da, the dimensionless tearing modulus."""
        return mat.E / mat.sigma_Y ** 2 * self.dJ_dda(delta_a)


def jr_curve(mat: Material) -> JRCurve:
    return JRCurve(J_IC=mat.J_IC, n=mat.JR_exponent_n,
                   delta_a_ref=mat.JR_delta_a_ref, material=mat.key)


def fit_jr_curve(delta_a: np.ndarray, J: np.ndarray, delta_a_ref: float = 1e-3) -> JRCurve:
    """Least squares power law fit to measured or simulated J versus crack extension."""
    def model(da, J_IC, n):
        return J_IC * (da / delta_a_ref) ** n
    p, _ = curve_fit(model, np.asarray(delta_a, float), np.asarray(J, float),
                     p0=[float(np.median(J)), 0.5], maxfev=20000)
    return JRCurve(J_IC=float(p[0]), n=float(p[1]), delta_a_ref=delta_a_ref)


def instability_point(mat: Material, sigma_pa: float, a0: float, W: float = 1.0,
                      geometry: str = "center", da_max: float = 0.02) -> dict:
    """Find where the applied J curve becomes tangent to the J-R curve.

    Stable tearing continues while dJ_applied/da is below dJ_R/da. The crossing of
    those slopes is the onset of unstable crack growth under load control.
    """
    from .lefm import stress_intensity
    R = jr_curve(mat)

    def J_applied(da: float) -> float:
        a = a0 + da
        K = stress_intensity(sigma_pa, a, W, geometry)
        return j_elastic_plastic(K, sigma_pa, mat)

    def gap(da: float) -> float:
        return J_applied(da) - float(R.J(da))

    def slope_gap(da: float) -> float:
        h = max(da * 1e-4, 1e-9)
        dJa = (J_applied(da + h) - J_applied(max(da - h, 1e-12))) / (2.0 * h)
        return dJa - float(R.dJ_dda(da))

    lo, hi = 1e-7, da_max
    out = {"J_IC": mat.J_IC, "material": mat.key, "a_0": a0,
           "sigma_MPa": sigma_pa / 1e6, "geometry": geometry}
    try:
        da_init = brentq(gap, lo, hi, xtol=1e-12)
        out["delta_a_initiation"] = da_init
        out["J_initiation"] = J_applied(da_init)
    except ValueError:
        out["delta_a_initiation"] = None
        out["J_initiation"] = None
    try:
        da_inst = brentq(slope_gap, lo, hi, xtol=1e-12)
        out["delta_a_instability"] = da_inst
        out["J_instability"] = J_applied(da_inst)
        out["tearing_modulus"] = float(R.tearing_modulus(da_inst, mat))
    except ValueError:
        out["delta_a_instability"] = None
        out["J_instability"] = None
        out["tearing_modulus"] = None
    return out


# ---------------------------------------------------------------------------
# CTOD
# ---------------------------------------------------------------------------

def ctod(J: float, mat: Material, m_factor: float | None = None) -> float:
    """Crack tip opening displacement in m. delta = J / (sigma_Y * m)."""
    if m_factor is None:
        m_factor = 2.0 if mat.plane_strain else 1.0
    return J / (mat.sigma_Y * m_factor)


def ctod_from_K(K_I: float, mat: Material, m_factor: float | None = None) -> float:
    return ctod(J_from_K(K_I, mat), mat, m_factor)


def ctod_critical(mat: Material, m_factor: float | None = None) -> float:
    """Critical CTOD from J_IC, the quantity a BS 7910 assessment compares against."""
    return ctod(mat.J_IC, mat, m_factor)


def measured_ctod(solver: XFEMSolver, u: np.ndarray, tip_id: int = 0,
                  behind: float | None = None) -> dict:
    """CTOD read straight off the XFEM crack face opening.

    The opening is sampled a fixed distance behind the tip, on both faces, using the
    enriched displacement field. This is the 90 degree intercept style measurement.
    """
    m = solver.mesh
    tp = solver.tip_list[tip_id]
    tip = np.asarray(tp["xy"], float)
    alpha = tp["alpha"]
    dx = float(np.diff(m.x).mean())
    dy = float(np.diff(m.y).mean())
    d = behind if behind is not None else 2.0 * dx
    eps = 0.35 * dy

    back = tip - d * np.array([math.cos(alpha), math.sin(alpha)])
    nrm = np.array([-math.sin(alpha), math.cos(alpha)])
    up = solver.displacement_at(u, (back + eps * nrm)[None, :])[0]
    dn = solver.displacement_at(u, (back - eps * nrm)[None, :])[0]
    opening = float(np.dot(up - dn, nrm))
    return {"ctod_measured": abs(opening), "sample_distance_behind_tip": d,
            "face_offset": eps}
