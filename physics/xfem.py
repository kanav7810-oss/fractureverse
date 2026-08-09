"""Extended finite element method for 2D cracks.

Enriched displacement approximation:

    u(x) = sum_I N_I(x) u_I
         + sum_J N_J(x) [ H(x) - H(x_J) ] a_J
         + sum_K sum_alpha N_K(x) [ F_alpha(x) - F_alpha(x_K) ] b_K_alpha

H is the Heaviside jump across the crack face and F_alpha are the four Westergaard
branch functions

    F_1 = sqrt(r) sin(theta/2)
    F_2 = sqrt(r) cos(theta/2)
    F_3 = sqrt(r) sin(theta) sin(theta/2)
    F_4 = sqrt(r) sin(theta) cos(theta/2)

which is the Belytschko and Black basis. It spans the full mode I and mode II
asymptotic field, and F_1 alone reproduces the crack face opening.

Both enrichments are shifted by their nodal value, so the approximation keeps the
Kronecker delta property at nodes. Displacement boundary conditions can then be
applied to standard degrees of freedom only.

Elements crossed by the crack are integrated by exact polygon partition: the
element rectangle is clipped by the crack line into two polygons, each polygon is
fan triangulated, and a degree four triangle rule is used on every triangle. Crack
tip elements subdivide those triangles further to resolve the sqrt(r) singularity.

Stress intensity factors come from the domain form of the interaction integral,
which is the standard route and is far more accurate than reading stresses at the
tip. K_I and K_II are returned in MPa*sqrt(m).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import spsolve

from .materials import Material
from .mesh import (StructuredMesh, crack_aligned_mesh, dshape_q4, gauss_2d,
                   shape_q4, to_parent)

# ---------------------------------------------------------------------------
# Triangle quadrature, degree 4, six points, weights sum to one
# ---------------------------------------------------------------------------

_TRI_BARY = np.array([
    [0.108103018168070, 0.445948490915965, 0.445948490915965],
    [0.445948490915965, 0.108103018168070, 0.445948490915965],
    [0.445948490915965, 0.445948490915965, 0.108103018168070],
    [0.816847572980459, 0.091576213509771, 0.091576213509771],
    [0.091576213509771, 0.816847572980459, 0.091576213509771],
    [0.091576213509771, 0.091576213509771, 0.816847572980459],
])
_TRI_W = np.array([0.223381589678011] * 3 + [0.109951743655322] * 3)


def _tri_area(t: np.ndarray) -> float:
    return 0.5 * abs((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1])
                     - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1]))


def _tri_points(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Physical quadrature points and weights (already carrying the area) for a triangle."""
    pts = _TRI_BARY @ t
    return pts, _TRI_W * _tri_area(t)


def _subdivide(t: np.ndarray, n: int) -> list[np.ndarray]:
    """Split a triangle into n^2 similar sub triangles by uniform barycentric refinement."""
    if n <= 1:
        return [t]
    out = []
    for i in range(n):
        for j in range(n - i):
            k = n - i - j
            # upward triangle
            b = np.array([[i + 1, j, k - 1], [i, j + 1, k - 1], [i, j, k]], float) / n
            out.append(b @ t)
            if k >= 2:
                b2 = np.array([[i + 1, j, k - 1], [i, j + 1, k - 1], [i + 1, j + 1, k - 2]],
                              float) / n
                out.append(b2 @ t)
    return out


def clip_polygon(poly: np.ndarray, p0: np.ndarray, d: np.ndarray,
                 keep_positive: bool) -> np.ndarray:
    """Sutherland Hodgman clip of a convex polygon against the line through p0 along d."""
    def side(p):
        return d[0] * (p[1] - p0[1]) - d[1] * (p[0] - p0[0])

    sgn = 1.0 if keep_positive else -1.0
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        sa, sb = sgn * side(a), sgn * side(b)
        if sa >= -1e-15:
            out.append(a)
        if sa * sb < 0.0:
            t = sa / (sa - sb)
            out.append(a + t * (b - a))
    return np.array(out) if len(out) >= 3 else np.zeros((0, 2))


def fan_triangles(poly: np.ndarray) -> list[np.ndarray]:
    return [poly[[0, i, i + 1]] for i in range(1, len(poly) - 1)]


# ---------------------------------------------------------------------------
# Crack geometry
# ---------------------------------------------------------------------------

@dataclass
class Crack:
    """A crack as an ordered polyline with one or two active tips."""

    points: np.ndarray                 # (n, 2)
    tip_start: bool = True             # is points[0] a growing tip
    tip_end: bool = True               # is points[-1] a growing tip

    def __post_init__(self):
        self.points = np.asarray(self.points, dtype=float)
        if self.points.shape[0] < 2:
            raise ValueError("a crack needs at least two points")

    @property
    def segments(self) -> np.ndarray:
        return np.stack([self.points[:-1], self.points[1:]], axis=1)   # (nseg, 2, 2)

    def tips(self) -> list[dict]:
        """Tip position and the angle alpha of the local x1 axis, which points ahead."""
        out = []
        if self.tip_end:
            d = self.points[-1] - self.points[-2]
            out.append({"xy": self.points[-1], "alpha": math.atan2(d[1], d[0]), "which": "end"})
        if self.tip_start:
            d = self.points[0] - self.points[1]
            out.append({"xy": self.points[0], "alpha": math.atan2(d[1], d[0]), "which": "start"})
        return out

    def nearest_segment(self, p: np.ndarray) -> int:
        segs = self.segments
        a, b = segs[:, 0], segs[:, 1]
        ab = b - a
        t = np.clip(np.einsum("ij,ij->i", p - a, ab) / np.einsum("ij,ij->i", ab, ab), 0.0, 1.0)
        proj = a + t[:, None] * ab
        return int(np.argmin(np.linalg.norm(proj - p, axis=1)))

    def signed_side(self, pts: np.ndarray, seg: int) -> np.ndarray:
        """+1 above the local crack line, -1 below. Used as the Heaviside value."""
        a, b = self.segments[seg]
        d = b - a
        c = d[0] * (pts[:, 1] - a[1]) - d[1] * (pts[:, 0] - a[0])
        return np.where(c >= 0.0, 1.0, -1.0)

    def total_length(self) -> float:
        return float(np.sum(np.linalg.norm(np.diff(self.points, axis=0), axis=1)))


def straight_center_crack(W: float, H: float, half_length: float) -> Crack:
    """Horizontal crack of total length 2a centred in the panel, tips at both ends."""
    yc = 0.5 * H
    return Crack(np.array([[0.5 * W - half_length, yc], [0.5 * W + half_length, yc]]),
                 tip_start=True, tip_end=True)


def edge_crack(W: float, H: float, length: float) -> Crack:
    """Horizontal crack growing in from the left edge. Only the right end is a tip."""
    yc = 0.5 * H
    return Crack(np.array([[0.0, yc], [length, yc]]), tip_start=False, tip_end=True)


def _seg_hits_rect(a, b, xlo, xhi, ylo, yhi, tol=1e-12) -> bool:
    """Liang Barsky test for a segment intersecting the open rectangle."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - xlo), (dx, xhi - a[0]), (-dy, a[1] - ylo), (dy, yhi - a[1])):
        if abs(p) < tol:
            if q < 0.0:
                return False
        else:
            r = q / p
            if p < 0.0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t1 - t0 > tol


# ---------------------------------------------------------------------------
# Branch functions
# ---------------------------------------------------------------------------

def branch_functions(pts: np.ndarray, tip_xy: np.ndarray, alpha: float
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """F_alpha and their global gradients at a set of points.

    Returns F (n, 4), dFdx (n, 4), dFdy (n, 4).
    """
    c, s = math.cos(alpha), math.sin(alpha)
    d = pts - tip_xy
    x1 = c * d[:, 0] + s * d[:, 1]
    x2 = -s * d[:, 0] + c * d[:, 1]

    r = np.sqrt(x1 ** 2 + x2 ** 2)
    r = np.maximum(r, 1e-14)
    th = np.arctan2(x2, x1)

    sr = np.sqrt(r)
    st2, ct2 = np.sin(0.5 * th), np.cos(0.5 * th)
    st, ct = np.sin(th), np.cos(th)

    F = np.column_stack([sr * st2, sr * ct2, sr * st * st2, sr * st * ct2])

    dFdr = np.column_stack([
        0.5 / sr * st2,
        0.5 / sr * ct2,
        0.5 / sr * st * st2,
        0.5 / sr * st * ct2,
    ])
    dFdt = np.column_stack([
        0.5 * sr * ct2,
        -0.5 * sr * st2,
        sr * (ct * st2 + 0.5 * st * ct2),
        sr * (ct * ct2 - 0.5 * st * st2),
    ])

    d1 = ct[:, None] * dFdr - (st / r)[:, None] * dFdt      # d/dx1 local
    d2 = st[:, None] * dFdr + (ct / r)[:, None] * dFdt      # d/dx2 local

    dFdx = c * d1 - s * d2
    dFdy = s * d1 + c * d2
    return F, dFdx, dFdy


# ---------------------------------------------------------------------------
# Auxiliary (Westergaard) fields used by the interaction integral
# ---------------------------------------------------------------------------

def aux_fields(r: np.ndarray, th: np.ndarray, mode: int, mu: float, kappa: float):
    """Unit K auxiliary stress and displacement gradient in LOCAL crack coordinates.

    Returns sig (n, 3) as [s11, s22, s12] and dudx1 (n, 2) as [du1/dx1, du2/dx1].
    """
    r = np.maximum(r, 1e-14)
    sqr = np.sqrt(r)
    inv = 1.0 / np.sqrt(2.0 * math.pi * r)
    st2, ct2 = np.sin(0.5 * th), np.cos(0.5 * th)
    s3t2, c3t2 = np.sin(1.5 * th), np.cos(1.5 * th)
    st, ct = np.sin(th), np.cos(th)

    if mode == 1:
        s11 = inv * ct2 * (1.0 - st2 * s3t2)
        s22 = inv * ct2 * (1.0 + st2 * s3t2)
        s12 = inv * ct2 * st2 * c3t2
        g = ct2 * (kappa - 1.0 + 2.0 * st2 ** 2)
        h = st2 * (kappa + 1.0 - 2.0 * ct2 ** 2)
        dg = -0.5 * st2 * (kappa - 1.0 + 2.0 * st2 ** 2) + 2.0 * st2 * ct2 ** 2
        dh = 0.5 * ct2 * (kappa + 1.0 - 2.0 * ct2 ** 2) + 2.0 * st2 ** 2 * ct2
    else:
        s11 = -inv * st2 * (2.0 + ct2 * c3t2)
        s22 = inv * st2 * ct2 * c3t2
        s12 = inv * ct2 * (1.0 - st2 * s3t2)
        g = st2 * (kappa + 1.0 + 2.0 * ct2 ** 2)
        h = -ct2 * (kappa - 1.0 - 2.0 * st2 ** 2)
        dg = 0.5 * ct2 * (kappa + 1.0 + 2.0 * ct2 ** 2) - 2.0 * st2 ** 2 * ct2
        dh = 0.5 * st2 * (kappa - 1.0 - 2.0 * st2 ** 2) + 2.0 * st2 * ct2 ** 2

    pref = 1.0 / (2.0 * mu) / math.sqrt(2.0 * math.pi)
    dsqr_dx1 = 0.5 / sqr * ct
    dth_dx1 = -st / r

    du1 = pref * (dsqr_dx1 * g + sqr * dg * dth_dx1)
    du2 = pref * (dsqr_dx1 * h + sqr * dh * dth_dx1)
    return np.column_stack([s11, s22, s12]), np.column_stack([du1, du2])


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

@dataclass
class XFEMSolution:
    u: np.ndarray
    solver: "XFEMSolver"
    K_I: float = 0.0
    K_II: float = 0.0
    info: dict = field(default_factory=dict)


class XFEMSolver:
    """Plane stress or plane strain XFEM on a structured rectangular mesh."""

    def __init__(self, mesh: StructuredMesh, mat: Material, crack: Crack,
                 thickness: float = 1.0, plane_strain: bool | None = None):
        self.mesh = mesh
        self.mat = mat
        self.crack = crack
        self.t = thickness
        self.plane_strain = mat.plane_strain if plane_strain is None else plane_strain
        self.D = self._constitutive()
        self._classify()
        self._number_dofs()

    # -- setup ------------------------------------------------------------
    def _constitutive(self) -> np.ndarray:
        E, nu = self.mat.E, self.mat.nu
        if self.plane_strain:
            f = E / ((1.0 + nu) * (1.0 - 2.0 * nu))
            return f * np.array([[1.0 - nu, nu, 0.0],
                                 [nu, 1.0 - nu, 0.0],
                                 [0.0, 0.0, 0.5 - nu]])
        f = E / (1.0 - nu ** 2)
        return f * np.array([[1.0, nu, 0.0],
                             [nu, 1.0, 0.0],
                             [0.0, 0.0, 0.5 * (1.0 - nu)]])

    def _classify(self):
        """Split elements into standard, cut and tip, then pick the enriched nodes."""
        m, cr = self.mesh, self.crack
        tips = cr.tips()
        self.tip_list = tips
        self.cut_elems: dict[int, int] = {}      # element -> segment index
        self.tip_elems: dict[int, int] = {}      # element -> tip index

        segs = cr.segments
        for e in range(m.n_elem):
            xlo, xhi, ylo, yhi = m.element_bounds(e)
            hit = -1
            for si, (a, b) in enumerate(segs):
                if _seg_hits_rect(a, b, xlo, xhi, ylo, yhi):
                    hit = si
                    break
            if hit < 0:
                continue
            owns_tip = -1
            for ti, tp in enumerate(tips):
                tx, ty = tp["xy"]
                if xlo - 1e-12 <= tx <= xhi + 1e-12 and ylo - 1e-12 <= ty <= yhi + 1e-12:
                    owns_tip = ti
                    break
            if owns_tip >= 0:
                self.tip_elems[e] = owns_tip
            else:
                self.cut_elems[e] = hit

        self.tip_nodes: dict[int, int] = {}
        for e, ti in self.tip_elems.items():
            for n in m.elements[e]:
                self.tip_nodes[int(n)] = ti
        self.heav_nodes: dict[int, int] = {}
        for e, si in self.cut_elems.items():
            for n in m.elements[e]:
                n = int(n)
                if n not in self.tip_nodes:
                    self.heav_nodes[n] = si

    def _number_dofs(self):
        m = self.mesh
        self.n_std = 2 * m.n_nodes
        self.heav_index = {n: k for k, n in enumerate(sorted(self.heav_nodes))}
        self.tip_index = {n: k for k, n in enumerate(sorted(self.tip_nodes))}
        self.base_heav = self.n_std
        self.base_tip = self.base_heav + 2 * len(self.heav_index)
        self.n_dof = self.base_tip + 8 * len(self.tip_index)

        # elements that must be integrated with the enriched basis
        enriched_nodes = set(self.heav_nodes) | set(self.tip_nodes)
        self.enriched_elems = [e for e in range(m.n_elem)
                               if enriched_nodes.intersection(m.elements[e].tolist())]
        self.enriched_set = set(self.enriched_elems)
        self.standard_elems = sorted(set(range(m.n_elem)) - self.enriched_set)

    # -- basis ------------------------------------------------------------
    def _element_basis(self, e: int, pts: np.ndarray):
        """Effective shape function gradients and dof map for element e at physical pts.

        Returns N (npts, nslot), gx, gy (npts, nslot) and dof (nslot, 2).
        """
        m = self.mesh
        xlo, xhi, ylo, yhi = m.element_bounds(e)
        dx, dy = xhi - xlo, yhi - ylo
        conn = m.elements[e]

        xi = 2.0 * (pts[:, 0] - xlo) / dx - 1.0
        eta = 2.0 * (pts[:, 1] - ylo) / dy - 1.0
        N = 0.25 * (1.0 + np.array([-1.0, 1.0, 1.0, -1.0]) * xi[:, None]) * \
            (1.0 + np.array([-1.0, -1.0, 1.0, 1.0]) * eta[:, None])
        dNdxi = 0.25 * np.array([-1.0, 1.0, 1.0, -1.0]) * \
            (1.0 + np.array([-1.0, -1.0, 1.0, 1.0]) * eta[:, None])
        dNdeta = 0.25 * np.array([-1.0, -1.0, 1.0, 1.0]) * \
            (1.0 + np.array([-1.0, 1.0, 1.0, -1.0]) * xi[:, None])
        dNdx = dNdxi * (2.0 / dx)
        dNdy = dNdeta * (2.0 / dy)

        Nl, gxl, gyl, dofs = [N], [dNdx], [dNdy], [np.array([[2 * n, 2 * n + 1] for n in conn])]

        # Heaviside slots
        h_local = [k for k, n in enumerate(conn) if int(n) in self.heav_nodes]
        if h_local:
            seg = self.cut_elems.get(e)
            if seg is None:
                seg = self.crack.nearest_segment(np.array([0.5 * (xlo + xhi), 0.5 * (ylo + yhi)]))
            Hg = self.crack.signed_side(pts, seg)
            node_xy = m.nodes[conn[h_local]]
            Hn = self.crack.signed_side(node_xy, seg)
            shift = Hg[:, None] - Hn[None, :]
            Nl.append(N[:, h_local] * shift)
            gxl.append(dNdx[:, h_local] * shift)
            gyl.append(dNdy[:, h_local] * shift)
            dofs.append(np.array([[self.base_heav + 2 * self.heav_index[int(conn[k])],
                                   self.base_heav + 2 * self.heav_index[int(conn[k])] + 1]
                                  for k in h_local]))

        # branch slots
        t_local = [k for k, n in enumerate(conn) if int(n) in self.tip_nodes]
        if t_local:
            by_tip: dict[int, list[int]] = {}
            for k in t_local:
                by_tip.setdefault(self.tip_nodes[int(conn[k])], []).append(k)
            for ti, ks in by_tip.items():
                tp = self.tip_list[ti]
                Fg, dFx, dFy = branch_functions(pts, tp["xy"], tp["alpha"])
                Fn, _, _ = branch_functions(m.nodes[conn[ks]], tp["xy"], tp["alpha"])
                for a in range(4):
                    sh = Fg[:, a][:, None] - Fn[:, a][None, :]
                    Nl.append(N[:, ks] * sh)
                    gxl.append(dNdx[:, ks] * sh + N[:, ks] * dFx[:, a][:, None])
                    gyl.append(dNdy[:, ks] * sh + N[:, ks] * dFy[:, a][:, None])
                    dofs.append(np.array(
                        [[self.base_tip + 8 * self.tip_index[int(conn[k])] + 2 * a,
                          self.base_tip + 8 * self.tip_index[int(conn[k])] + 2 * a + 1]
                         for k in ks]))

        return (np.hstack(Nl), np.hstack(gxl), np.hstack(gyl), np.vstack(dofs))

    # -- quadrature -------------------------------------------------------
    def _element_quadrature(self, e: int) -> tuple[np.ndarray, np.ndarray]:
        """Physical quadrature points and weights (area already folded in)."""
        m = self.mesh
        corners = m.element_corners(e)
        dx, dy = m.element_size(e)

        if e in self.cut_elems or e in self.tip_elems:
            if e in self.cut_elems:
                si = self.cut_elems[e]
                sub = 1
            else:
                ti = self.tip_elems[e]
                si = self.crack.nearest_segment(self.tip_list[ti]["xy"])
                sub = 4
            a, b = self.crack.segments[si]
            d = b - a
            polys = [clip_polygon(corners, a, d, True), clip_polygon(corners, a, d, False)]
            pts, wts = [], []
            for poly in polys:
                if len(poly) < 3:
                    continue
                for tri in fan_triangles(poly):
                    for st in _subdivide(tri, sub):
                        p, w = _tri_points(st)
                        pts.append(p)
                        wts.append(w)
            if pts:
                return np.vstack(pts), np.concatenate(wts)

        n = 4 if e in self.enriched_set else 2
        gp, gw = gauss_2d(n)
        xlo, xhi, ylo, yhi = m.element_bounds(e)
        px = xlo + 0.5 * (gp[:, 0] + 1.0) * dx
        py = ylo + 0.5 * (gp[:, 1] + 1.0) * dy
        return np.column_stack([px, py]), gw * 0.25 * dx * dy

    # -- assembly ---------------------------------------------------------
    def _standard_ke(self, dx: float, dy: float) -> np.ndarray:
        key = (round(dx, 14), round(dy, 14))
        cache = getattr(self, "_ke_cache", None)
        if cache is None:
            cache = self._ke_cache = {}
        if key in cache:
            return cache[key]
        gp, gw = gauss_2d(2)
        Ke = np.zeros((8, 8))
        for (xi, eta), w in zip(gp, gw):
            dN = dshape_q4(xi, eta)
            dNdx, dNdy = dN[0] * (2.0 / dx), dN[1] * (2.0 / dy)
            B = np.zeros((3, 8))
            B[0, 0::2] = dNdx
            B[1, 1::2] = dNdy
            B[2, 0::2] = dNdy
            B[2, 1::2] = dNdx
            Ke += B.T @ self.D @ B * w * 0.25 * dx * dy * self.t
        cache[key] = Ke
        return Ke

    def assemble(self) -> csr_matrix:
        m = self.mesh
        rows, cols, vals = [], [], []

        for e in self.standard_elems:
            dx, dy = m.element_size(e)
            Ke = self._standard_ke(dx, dy)
            conn = m.elements[e]
            dof = np.empty(8, dtype=np.int64)
            dof[0::2] = 2 * conn
            dof[1::2] = 2 * conn + 1
            R, C = np.meshgrid(dof, dof, indexing="ij")
            rows.append(R.ravel())
            cols.append(C.ravel())
            vals.append(Ke.ravel())

        for e in self.enriched_elems:
            pts, wts = self._element_quadrature(e)
            _, gx, gy, dofmap = self._element_basis(e, pts)
            nslot = gx.shape[1]
            dof = dofmap.reshape(-1)                     # (2*nslot,), x then y interleaved
            Ke = np.zeros((2 * nslot, 2 * nslot))
            for q in range(len(wts)):
                B = np.zeros((3, 2 * nslot))
                B[0, 0::2] = gx[q]
                B[1, 1::2] = gy[q]
                B[2, 0::2] = gy[q]
                B[2, 1::2] = gx[q]
                Ke += B.T @ self.D @ B * wts[q] * self.t
            R, C = np.meshgrid(dof, dof, indexing="ij")
            rows.append(R.ravel())
            cols.append(C.ravel())
            vals.append(Ke.ravel())

        K = coo_matrix((np.concatenate(vals),
                        (np.concatenate(rows), np.concatenate(cols))),
                       shape=(self.n_dof, self.n_dof)).tocsr()
        return K

    # -- loads and boundary conditions ------------------------------------
    def traction_top(self, sigma_pa: float) -> np.ndarray:
        """Consistent nodal forces for a uniform vertical traction on the top edge."""
        f = np.zeros(self.n_dof)
        m = self.mesh
        top = m.edge_nodes("top")
        for k in range(len(top) - 1):
            n0, n1 = int(top[k]), int(top[k + 1])
            le = m.nodes[n1, 0] - m.nodes[n0, 0]
            half = 0.5 * sigma_pa * le * self.t
            f[2 * n0 + 1] += half
            f[2 * n1 + 1] += half
        return f

    def fixed_dofs_bottom_roller(self) -> np.ndarray:
        """Bottom edge on rollers, plus one horizontal restraint to kill rigid body motion."""
        m = self.mesh
        bot = m.edge_nodes("bottom")
        d = [2 * int(n) + 1 for n in bot]
        d.append(2 * int(bot[0]))
        return np.array(sorted(set(d)), dtype=np.int64)

    def solve(self, sigma_pa: float) -> XFEMSolution:
        K = self.assemble()
        f = self.traction_top(sigma_pa)
        fixed = self.fixed_dofs_bottom_roller()

        free = np.setdiff1d(np.arange(self.n_dof), fixed)
        Kff = K[free][:, free]
        u = np.zeros(self.n_dof)
        u[free] = spsolve(Kff.tocsc(), f[free])
        return XFEMSolution(u=u, solver=self,
                            info={"n_dof": self.n_dof,
                                  "n_enriched_dof": self.n_dof - self.n_std,
                                  "n_heaviside_nodes": len(self.heav_index),
                                  "n_tip_nodes": len(self.tip_index),
                                  "n_cut_elems": len(self.cut_elems),
                                  "n_tip_elems": len(self.tip_elems),
                                  "sigma_MPa": sigma_pa / 1e6})

    # -- field recovery ---------------------------------------------------
    def gradients_at(self, u: np.ndarray, e: int, pts: np.ndarray) -> np.ndarray:
        """du_i/dx_j at pts inside element e. Returns (npts, 2, 2) ordered [i][j]."""
        _, gx, gy, dofmap = self._element_basis(e, pts)
        ux = u[dofmap[:, 0]]
        uy = u[dofmap[:, 1]]
        g = np.empty((len(pts), 2, 2))
        g[:, 0, 0] = gx @ ux
        g[:, 0, 1] = gy @ ux
        g[:, 1, 0] = gx @ uy
        g[:, 1, 1] = gy @ uy
        return g

    def stress_at(self, u: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Cauchy stress [s_xx, s_yy, s_xy] in Pa at arbitrary points."""
        out = np.zeros((len(pts), 3))
        for k, p in enumerate(pts):
            e = self.mesh.locate(p[0], p[1])
            g = self.gradients_at(u, e, p[None, :])[0]
            eps = np.array([g[0, 0], g[1, 1], g[0, 1] + g[1, 0]])
            out[k] = self.D @ eps
        return out

    def displacement_at(self, u: np.ndarray, pts: np.ndarray) -> np.ndarray:
        out = np.zeros((len(pts), 2))
        for k, p in enumerate(pts):
            e = self.mesh.locate(p[0], p[1])
            N, _, _, dofmap = self._element_basis(e, p[None, :])
            out[k, 0] = N[0] @ u[dofmap[:, 0]]
            out[k, 1] = N[0] @ u[dofmap[:, 1]]
        return out

    # -- interaction integral ---------------------------------------------
    def interaction_integral(self, u: np.ndarray, tip_id: int = 0,
                             r_factor: float = 3.0) -> dict:
        """Domain form interaction integral. Returns K_I and K_II in MPa*sqrt(m)."""
        m, mat = self.mesh, self.mat
        tp = self.tip_list[tip_id]
        tip_xy = np.asarray(tp["xy"], float)
        alpha = tp["alpha"]
        c, s = math.cos(alpha), math.sin(alpha)
        Q = np.array([[c, s], [-s, c]])          # global to local rotation

        dx = float(np.diff(m.x).mean())
        dy = float(np.diff(m.y).mean())
        r_d = r_factor * max(dx, dy)

        dist = np.linalg.norm(m.nodes - tip_xy, axis=1)
        q_node = (dist <= r_d).astype(float)

        mu = mat.G
        kappa = mat.kappa(self.plane_strain)
        e_eff = mat.E / (1.0 - mat.nu ** 2) if self.plane_strain else mat.E
        nu = mat.nu

        I = np.zeros(2)
        n_elem_used = 0
        for e in range(m.n_elem):
            conn = m.elements[e]
            qn = q_node[conn]
            if qn.max() == 0.0 or qn.min() == 1.0:
                continue                          # grad q is zero, no contribution
            n_elem_used += 1
            pts, wts = self._element_quadrature(e)
            N, gx, gy, dofmap = self._element_basis(e, pts)

            # q and its gradient use the standard Q4 part only
            xlo, xhi, ylo, yhi = m.element_bounds(e)
            ex, ey = xhi - xlo, yhi - ylo
            xi = 2.0 * (pts[:, 0] - xlo) / ex - 1.0
            eta = 2.0 * (pts[:, 1] - ylo) / ey - 1.0
            sx = np.array([-1.0, 1.0, 1.0, -1.0])
            sy = np.array([-1.0, -1.0, 1.0, 1.0])
            dNdx = 0.25 * sx * (1.0 + sy * eta[:, None]) * (2.0 / ex)
            dNdy = 0.25 * sy * (1.0 + sx * xi[:, None]) * (2.0 / ey)
            dqdx = dNdx @ qn
            dqdy = dNdy @ qn
            dq_glob = np.column_stack([dqdx, dqdy])
            dq_loc = dq_glob @ Q.T

            # FE gradients and stress, rotated into the local crack frame
            ux, uy = u[dofmap[:, 0]], u[dofmap[:, 1]]
            g = np.empty((len(pts), 2, 2))
            g[:, 0, 0] = gx @ ux
            g[:, 0, 1] = gy @ ux
            g[:, 1, 0] = gx @ uy
            g[:, 1, 1] = gy @ uy
            g_loc = np.einsum("ik,pkl,jl->pij", Q, g, Q)

            eps = np.column_stack([g[:, 0, 0], g[:, 1, 1], g[:, 0, 1] + g[:, 1, 0]])
            sig = eps @ self.D.T
            S = np.zeros((len(pts), 2, 2))
            S[:, 0, 0], S[:, 1, 1], S[:, 0, 1], S[:, 1, 0] = sig[:, 0], sig[:, 1], sig[:, 2], sig[:, 2]
            S_loc = np.einsum("ik,pkl,jl->pij", Q, S, Q)

            d = pts - tip_xy
            x1 = c * d[:, 0] + s * d[:, 1]
            x2 = -s * d[:, 0] + c * d[:, 1]
            r = np.maximum(np.hypot(x1, x2), 1e-12)
            th = np.arctan2(x2, x1)

            for mode in (1, 2):
                sa, dua = aux_fields(r, th, mode, mu, kappa)
                A = np.zeros((len(pts), 2, 2))
                A[:, 0, 0], A[:, 1, 1] = sa[:, 0], sa[:, 1]
                A[:, 0, 1] = A[:, 1, 0] = sa[:, 2]

                # aux strain from aux stress
                if self.plane_strain:
                    ea11 = ((1 - nu ** 2) * sa[:, 0] - nu * (1 + nu) * sa[:, 1]) / mat.E
                    ea22 = ((1 - nu ** 2) * sa[:, 1] - nu * (1 + nu) * sa[:, 0]) / mat.E
                else:
                    ea11 = (sa[:, 0] - nu * sa[:, 1]) / mat.E
                    ea22 = (sa[:, 1] - nu * sa[:, 0]) / mat.E
                ea12 = (1.0 + nu) * sa[:, 2] / mat.E

                W12 = (S_loc[:, 0, 0] * ea11 + S_loc[:, 1, 1] * ea22
                       + 2.0 * S_loc[:, 0, 1] * ea12)

                du1_fe = g_loc[:, 0, 0]
                du2_fe = g_loc[:, 1, 0]

                t1 = (S_loc[:, 0, 0] * dua[:, 0] + S_loc[:, 1, 0] * dua[:, 1]
                      + A[:, 0, 0] * du1_fe + A[:, 1, 0] * du2_fe - W12)
                t2 = (S_loc[:, 0, 1] * dua[:, 0] + S_loc[:, 1, 1] * dua[:, 1]
                      + A[:, 0, 1] * du1_fe + A[:, 1, 1] * du2_fe)

                I[mode - 1] += float(np.sum((t1 * dq_loc[:, 0] + t2 * dq_loc[:, 1]) * wts))

        K = 0.5 * e_eff * I / 1.0e6      # Pa*sqrt(m) to MPa*sqrt(m)
        return {"K_I": float(K[0]), "K_II": float(K[1]),
                "r_domain": r_d, "r_factor": r_factor,
                "n_ring_elements": n_elem_used, "tip": tp["which"]}

    # -- propagation ------------------------------------------------------
    @staticmethod
    def kink_angle(K_I: float, K_II: float) -> float:
        """Maximum circumferential stress criterion. Returns theta_c in radians."""
        if abs(K_II) < 1e-12 * max(abs(K_I), 1.0):
            return 0.0
        ratio = K_II / K_I if abs(K_I) > 1e-14 else math.copysign(1e14, K_II)
        return 2.0 * math.atan((1.0 - math.sqrt(1.0 + 8.0 * ratio ** 2)) / (4.0 * ratio))

    @staticmethod
    def effective_K(K_I: float, K_II: float) -> float:
        """Equivalent mode I stress intensity factor at the kink angle."""
        th = XFEMSolver.kink_angle(K_I, K_II)
        c = math.cos(0.5 * th)
        return c ** 3 * K_I - 3.0 * c ** 2 * math.sin(0.5 * th) * K_II


def propagate(mesh: StructuredMesh, mat: Material, crack: Crack, sigma_pa: float,
              n_steps: int = 12, da_factor: float = 0.5, r_factor: float = 3.0,
              tip_id: int = 0, thickness: float = 1.0) -> dict:
    """Grow a crack step by step using the maximum circumferential stress criterion.

    Each step advances the chosen tip by da = da_factor * element size along the
    kink direction, then re solves. Returns the path and the K history.
    """
    dx = float(np.diff(mesh.x).mean())
    da = da_factor * dx
    hist = {"path": [], "K_I": [], "K_II": [], "theta_deg": [], "K_eff": [], "a": []}

    for step in range(n_steps):
        solver = XFEMSolver(mesh, mat, crack, thickness=thickness)
        sol = solver.solve(sigma_pa)
        res = solver.interaction_integral(sol.u, tip_id=tip_id, r_factor=r_factor)
        th = XFEMSolver.kink_angle(res["K_I"], res["K_II"])
        keff = XFEMSolver.effective_K(res["K_I"], res["K_II"])

        tp = solver.tip_list[tip_id]
        tip_xy = np.asarray(tp["xy"], float)
        ang = tp["alpha"] + th
        new_tip = tip_xy + da * np.array([math.cos(ang), math.sin(ang)])

        hist["path"].append(tip_xy.tolist())
        hist["K_I"].append(res["K_I"])
        hist["K_II"].append(res["K_II"])
        hist["theta_deg"].append(math.degrees(th))
        hist["K_eff"].append(keff)
        hist["a"].append(crack.total_length())

        if tp["which"] == "end":
            pts = np.vstack([crack.points, new_tip])
        else:
            pts = np.vstack([new_tip, crack.points])
        if not (0.02 * mesh.W < new_tip[0] < 0.98 * mesh.W
                and 0.02 * mesh.H < new_tip[1] < 0.98 * mesh.H):
            break
        crack = Crack(pts, tip_start=crack.tip_start, tip_end=crack.tip_end)

    hist["final_crack"] = crack.points.tolist()
    return hist


def solve_center_crack(mat: Material, half_length: float, sigma_pa: float,
                       W: float = 0.1, aspect: float = 2.0, nx: int = 61,
                       ny: int = 121, r_factor: float = 3.0) -> dict:
    """Convenience driver for the centre cracked tension benchmark."""
    H = aspect * W
    mesh = crack_aligned_mesh(W, H, nx, ny)
    crack = straight_center_crack(W, H, half_length)
    solver = XFEMSolver(mesh, mat, crack)
    sol = solver.solve(sigma_pa)
    res = solver.interaction_integral(sol.u, tip_id=0, r_factor=r_factor)
    res.update(sol.info)
    res["a"] = half_length
    res["mesh"] = mesh.summary()
    sol.K_I, sol.K_II = res["K_I"], res["K_II"]
    res["solution"] = sol
    return res
