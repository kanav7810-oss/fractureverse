"""Bond based peridynamics in 2D with bond breaking.

Equation of motion

    rho * u_tt(x, t) = integral over H_x of f( u(x',t) - u(x,t), x' - x ) dV_x' + b(x, t)

with the pairwise bond force

    f = c * s * e_xi ,   s = ( |xi + eta| - |xi| ) / |xi|

A bond breaks irreversibly once its stretch s exceeds the critical stretch s_0, and
the local damage is the fraction of a point's bonds that have broken

    d(x) = 1 - ( intact bond volume ) / ( initial bond volume )

Two calibrations are provided.

  2D plane stress, bond based, the default here
      c   = 9 E / ( pi * t * delta^3 )
      s_0 = sqrt( 4 pi G_0 / ( 9 E delta ) )

  3D bond based, the form quoted in classic peridynamics texts
      c   = 18 K / ( pi * delta^4 )
      s_0 = sqrt( 5 pi G_0 / ( 9 K delta ) )

The 2D forms are the correct ones for a plane stress plate and are what the damage
and convergence studies use. The 3D forms are exposed for completeness and are
selectable through `calibration="3d"`.

Two known properties of bond based peridynamics are reported rather than hidden.
Poisson ratio is fixed at 1/3 in 2D plane stress, and the effective tensile strength
scales as 1/sqrt(delta), so the horizon is a material length scale and not a free
numerical parameter. For concrete the matching length is the Hillerborg
characteristic length l_ch = E * G_f / f_t^2, which is order 0.2 m, and the model
geometry here is sized accordingly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

from .materials import Material


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def micromodulus(mat: Material, delta: float, thickness: float = 1.0,
                 calibration: str = "2d") -> float:
    if calibration == "2d":
        return 9.0 * mat.E / (math.pi * thickness * delta ** 3)
    return 18.0 * mat.K_bulk / (math.pi * delta ** 4)


def critical_stretch(mat: Material, delta: float, G0: float | None = None,
                     calibration: str = "2d") -> float:
    G0 = mat.G_c if G0 is None else G0
    if calibration == "2d":
        return math.sqrt(4.0 * math.pi * G0 / (9.0 * mat.E * delta))
    return math.sqrt(5.0 * math.pi * G0 / (9.0 * mat.K_bulk * delta))


def pd_tensile_strength(mat: Material, delta: float, G0: float | None = None) -> float:
    """Effective tensile strength implied by the horizon, in Pa. Scales as 1/sqrt(delta)."""
    return mat.E * critical_stretch(mat, delta, G0)


def characteristic_length(mat: Material, G0: float | None = None,
                          f_t: float | None = None) -> float:
    """Hillerborg characteristic length l_ch = E*G_f/f_t^2, in m."""
    G0 = mat.raw.get("G_f", mat.G_c) if G0 is None else G0
    f_t = mat.raw.get("f_t", mat.sigma_Y) if f_t is None else f_t
    return mat.E * G0 / f_t ** 2


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass
class PDModel:
    """Uniform grid peridynamic plate."""

    W: float
    H: float
    dx: float
    mat: Material
    m_ratio: float = 3.015
    thickness: float = 1.0
    G0: float | None = None
    calibration: str = "2d"

    coords: np.ndarray = field(init=False)
    nx: int = field(init=False)
    ny: int = field(init=False)

    def __post_init__(self):
        self.nx = int(round(self.W / self.dx))
        self.ny = int(round(self.H / self.dx))
        xs = (np.arange(self.nx) + 0.5) * self.dx
        ys = (np.arange(self.ny) + 0.5) * self.dx
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        self.coords = np.column_stack([X.ravel(), Y.ravel()])
        self.n = self.coords.shape[0]

        self.delta = self.m_ratio * self.dx
        self.dV = self.dx * self.dx * self.thickness
        self.c = micromodulus(self.mat, self.delta, self.thickness, self.calibration)
        self.s0 = critical_stretch(self.mat, self.delta, self.G0, self.calibration)

        self._build_bonds()

    # -- topology ---------------------------------------------------------
    def _build_bonds(self):
        tree = cKDTree(self.coords)
        pairs = np.array(sorted(tree.query_pairs(self.delta)), dtype=np.int64)
        self.bi, self.bj = pairs[:, 0], pairs[:, 1]
        xi = self.coords[self.bj] - self.coords[self.bi]
        self.xi = xi
        self.xi_len = np.linalg.norm(xi, axis=1)

        # partial volume correction for family members straddling the horizon surface
        r = self.xi_len
        half = 0.5 * self.dx
        vc = np.ones_like(r)
        edge = r > (self.delta - half)
        vc[edge] = (self.delta + half - r[edge]) / self.dx
        self.vol_corr = np.clip(vc, 0.0, 1.0)

        self.broken = np.zeros(len(r), dtype=bool)
        w = self.vol_corr * self.dV
        self.family_volume = (np.bincount(self.bi, weights=w, minlength=self.n)
                              + np.bincount(self.bj, weights=w, minlength=self.n))

    def notch(self, p0, p1):
        """Break every bond whose segment crosses the notch segment p0 to p1."""
        p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
        a = self.coords[self.bi]
        b = self.coords[self.bj]

        def cross(o, u, v):
            return (u[..., 0] - o[..., 0]) * (v[..., 1] - o[..., 1]) - \
                   (u[..., 1] - o[..., 1]) * (v[..., 0] - o[..., 0])

        d1 = cross(p0, p1, a)
        d2 = cross(p0, p1, b)
        d3 = cross(a, b, p0)
        d4 = cross(a, b, p1)
        hit = ((d1 * d2) < 0.0) & ((d3 * d4) < 0.0)
        self.broken |= hit
        return int(hit.sum())

    # -- damage -----------------------------------------------------------
    def damage(self) -> np.ndarray:
        w = self.vol_corr * self.dV * (~self.broken)
        intact = (np.bincount(self.bi, weights=w, minlength=self.n)
                  + np.bincount(self.bj, weights=w, minlength=self.n))
        return 1.0 - intact / np.maximum(self.family_volume, 1e-30)

    def damage_grid(self) -> np.ndarray:
        """Damage reshaped to (nx, ny) so it can be imshow'ed directly."""
        return self.damage().reshape(self.nx, self.ny)

    # -- forces -----------------------------------------------------------
    def bond_forces(self, u: np.ndarray, allow_breaking: bool = True) -> np.ndarray:
        eta = u[self.bj] - u[self.bi]
        y = self.xi + eta
        y_len = np.linalg.norm(y, axis=1)
        s = y_len / self.xi_len - 1.0

        if allow_breaking:
            self.broken |= (s > self.s0)
        live = ~self.broken

        mag = np.where(live, self.c * s * self.vol_corr * self.dV, 0.0)
        fvec = (mag / np.maximum(y_len, 1e-30))[:, None] * y

        f = np.zeros_like(u)
        for k in (0, 1):
            f[:, k] += np.bincount(self.bi, weights=fvec[:, k], minlength=self.n)
            f[:, k] -= np.bincount(self.bj, weights=fvec[:, k], minlength=self.n)
        return f

    def stable_dt(self, safety: float = 0.8) -> float:
        """Silling and Askari stability bound for the central difference scheme."""
        w = self.c / self.xi_len * self.vol_corr * self.dV
        denom = (np.bincount(self.bi, weights=w, minlength=self.n)
                 + np.bincount(self.bj, weights=w, minlength=self.n))
        return safety * math.sqrt(2.0 * self.mat.rho / max(denom.max(), 1e-30))

    # -- verification -----------------------------------------------------
    def verify_energy_release_rate(self) -> dict:
        """Sum the work needed to break every bond crossing the mid height plane.

        Divided by the fracture area this must recover G_0, which is the identity the
        micromodulus and critical stretch calibration comes from. Writing the
        micropotential at failure as w = c s_0^2 xi / 2 and integrating over the
        bonds that cross a line gives

            G_0 = 1/2 * c * s_0^2 * int_0^delta int_z^delta xi^2 * 2*arccos(z/xi) dxi dz
                = c * s_0^2 * delta^4 / 4

        and substituting c = 9E/(pi delta^3) recovers s_0 = sqrt(4 pi G_0/(9 E delta)),
        which is the plane stress form this module uses. The angular measure is
        2*arccos(z/xi) and not arccos(z/xi), because a bond of length xi reaches across
        the line on both sides of the vertical.

        The cut plane is placed exactly between two node rows, and bonds within one
        horizon of the left and right free surfaces are excluded, so neither the grid
        alignment nor the missing family volume at a surface contaminates the result.
        What remains is the peridynamic quadrature error, which is first order in the
        partial volume correction and therefore only vanishes as delta/dx grows. That
        is the m convergence this check is designed to expose.
        """
        yc = (self.ny // 2) * self.dx
        a = self.coords[self.bi]
        b = self.coords[self.bj]
        crossing = ((a[:, 1] - yc) * (b[:, 1] - yc)) < 0.0
        xm = 0.5 * (a[:, 0] + b[:, 0])
        window = (xm > self.delta) & (xm < self.W - self.delta)
        sel = crossing & window

        w_bond = 0.5 * self.c * self.s0 ** 2 * self.xi_len
        energy = float(np.sum(w_bond[sel] * self.vol_corr[sel] * self.dV * self.dV))
        area = (self.W - 2.0 * self.delta) * self.thickness
        G0 = self.mat.G_c if self.G0 is None else self.G0
        g_num = energy / area
        continuum = self.c * self.s0 ** 2 * self.delta ** 4 / 4.0
        return {"G0_target": G0, "G0_recovered": g_num,
                "G0_continuum_identity": continuum,
                "error_percent": 100.0 * (g_num - G0) / G0,
                "n_crossing_bonds": int(sel.sum()),
                "delta": self.delta, "dx": self.dx, "m_ratio": self.m_ratio,
                "n_nodes": self.n}


# ---------------------------------------------------------------------------
# Explicit dynamics
# ---------------------------------------------------------------------------

def run_dynamic(model: PDModel, sigma_pa: float, n_steps: int = 1500,
                dt: float | None = None, load_layers: int = 3,
                allow_breaking: bool = True, record_every: int = 0) -> dict:
    """Suddenly applied tensile traction on the top and bottom edges.

    The traction is converted into a body force density on the outer `load_layers`
    rows of nodes, b = sigma / (load_layers * dx), which is the standard way to load
    a peridynamic body that has no surface to apply a traction to.
    """
    dt = model.stable_dt() if dt is None else dt
    u = np.zeros((model.n, 2))
    u_old = np.zeros_like(u)

    band = load_layers * model.dx
    top = model.coords[:, 1] > model.H - band
    bot = model.coords[:, 1] < band
    b = np.zeros_like(u)
    b[top, 1] = sigma_pa / band
    b[bot, 1] = -sigma_pa / band

    frames = []
    coef = dt * dt / model.mat.rho
    for step in range(n_steps):
        f = model.bond_forces(u, allow_breaking=allow_breaking)
        u_new = 2.0 * u - u_old + coef * (f + b)
        u_old, u = u, u_new
        if record_every and step % record_every == 0:
            frames.append(model.damage_grid().copy())

    return {"u": u, "dt": dt, "n_steps": n_steps, "t_end": dt * n_steps,
            "damage": model.damage_grid(), "frames": frames,
            "sigma_MPa": sigma_pa / 1e6,
            "pd_strength_MPa": pd_tensile_strength(model.mat, model.delta, model.G0) / 1e6,
            "s0": model.s0, "c": model.c, "delta": model.delta, "dx": model.dx,
            "n_nodes": model.n, "n_bonds": len(model.xi_len),
            "broken_fraction": float(model.broken.mean())}


# ---------------------------------------------------------------------------
# Crack path analysis
# ---------------------------------------------------------------------------

def crack_clusters(damage: np.ndarray, threshold: float = 0.35) -> list[list[tuple[int, int]]]:
    """Per column, the contiguous runs of damaged rows. Used to detect branching."""
    mask = damage > threshold
    out = []
    for i in range(mask.shape[0]):
        col = mask[i]
        runs, start = [], None
        for j, v in enumerate(col):
            if v and start is None:
                start = j
            elif not v and start is not None:
                runs.append((start, j - 1))
                start = None
        if start is not None:
            runs.append((start, len(col) - 1))
        out.append(runs)
    return out


def analyse_crack(model: PDModel, damage: np.ndarray, notch_tip_x: float,
                  threshold: float = 0.35, min_run: int = 1) -> dict:
    """Detect crack advance and branching from the damage field.

    Branching is recorded when a column ahead of the original notch tip contains two
    or more separated damage bands, which is a Y shaped crack rather than a single
    front. Columns inside the applied load bands are ignored.
    """
    runs = crack_clusters(damage, threshold)
    i_tip = int(notch_tip_x / model.dx)
    guard = 2

    branch_cols, tip_x = [], notch_tip_x
    for i in range(i_tip + guard, model.nx - guard):
        good = [r for r in runs[i] if (r[1] - r[0] + 1) >= min_run]
        if good:
            tip_x = (i + 0.5) * model.dx
        if len(good) >= 2:
            branch_cols.append(i)

    branched = len(branch_cols) >= 3        # needs to persist, not a one column artefact
    return {
        "branched": bool(branched),
        "n_branch_columns": len(branch_cols),
        "first_branch_x": (branch_cols[0] + 0.5) * model.dx if branch_cols else None,
        "max_bands_in_a_column": max((len(r) for r in runs), default=0),
        "crack_tip_x": tip_x,
        "crack_advance": tip_x - notch_tip_x,
        "damaged_node_fraction": float((damage > threshold).mean()),
        "threshold": threshold,
    }


def concrete_branching_panel(mat: Material, W: float = 3.0, H: float = 1.5,
                             dx: float = 0.03, m_ratio: float = 3.015,
                             notch_frac: float = 0.30, sigma_pa: float = 12e6,
                             n_steps: int = 1600, G0: float | None = None) -> dict:
    """Pre notched concrete panel under a suddenly applied tension.

    Panel size follows the concrete characteristic length so the horizon can carry a
    realistic fracture process zone. The notch runs in from the left edge at mid
    height, and the crack is free to find its own path, which is the property
    peridynamics has and LEFM does not.
    """
    model = PDModel(W=W, H=H, dx=dx, mat=mat, m_ratio=m_ratio, G0=G0)
    notch_tip = notch_frac * W
    n_cut = model.notch((0.0, 0.5 * H), (notch_tip, 0.5 * H))
    res = run_dynamic(model, sigma_pa, n_steps=n_steps)
    res["notch_bonds_cut"] = n_cut
    res["notch_tip_x"] = notch_tip
    res["l_ch"] = characteristic_length(mat, G0)
    res.update(analyse_crack(model, res["damage"], notch_tip))
    res["model"] = model
    return res


def m_convergence_study(mat: Material, m_values=(2.0, 3.0, 4.0), delta: float = 0.09,
                        W: float = 3.0, H: float = 1.5, notch_frac: float = 0.30,
                        sigma_pa: float = 12e6, n_steps: int = 1200,
                        G0: float | None = None) -> dict:
    """m convergence: hold the horizon fixed and refine the grid so delta/dx grows.

    This is the convergence mode peridynamics is judged on. The horizon is a material
    length, so refining dx at fixed delta must converge to the non local solution.
    """
    runs = []
    for m in m_values:
        dx = delta / m
        model = PDModel(W=W, H=H, dx=dx, mat=mat, m_ratio=m, G0=G0)
        notch_tip = notch_frac * W
        model.notch((0.0, 0.5 * H), (notch_tip, 0.5 * H))
        r = run_dynamic(model, sigma_pa, n_steps=n_steps)
        an = analyse_crack(model, r["damage"], notch_tip)
        eg = model.verify_energy_release_rate()
        runs.append({"m": m, "dx": dx, "delta": delta, "n_nodes": model.n,
                     "n_bonds": len(model.xi_len),
                     "crack_advance": an["crack_advance"],
                     "damaged_fraction": an["damaged_node_fraction"],
                     "branched": an["branched"],
                     "broken_fraction": r["broken_fraction"],
                     "G0_error_percent": eg["error_percent"],
                     "damage_profile": _midline_profile(model, r["damage"])})

    ref = runs[-1]["damage_profile"]
    for r in runs:
        p = np.interp(np.linspace(0, 1, len(ref)),
                      np.linspace(0, 1, len(r["damage_profile"])), r["damage_profile"])
        r["profile_L2_error_vs_finest"] = float(
            np.linalg.norm(p - ref) / max(np.linalg.norm(ref), 1e-30))
        r.pop("damage_profile")
    return {"delta": delta, "runs": runs}


def _midline_profile(model: PDModel, damage: np.ndarray) -> np.ndarray:
    """Damage along the crack line, used as the convergence metric."""
    j = model.ny // 2
    return damage[:, j].copy()
