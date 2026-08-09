"""Structured quadrilateral mesh with optional crack tip grading.

Every element stays axis aligned, so the Jacobian of the bilinear map is a
constant diagonal matrix per element. That keeps the XFEM and J integral code
short and lets identical elements share a single precomputed stiffness matrix.

Node numbering:  n = j*(nx+1) + i,  i in [0, nx],  j in [0, ny]
Element numbering: e = j*nx + i, connectivity is counter clockwise
    (i, j) -> (i+1, j) -> (i+1, j+1) -> (i, j+1)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class StructuredMesh:
    """Rectangular domain [0, W] x [0, H] discretised into Q4 elements."""

    W: float
    H: float
    nx: int
    ny: int
    x: np.ndarray          # (nx+1,) node coordinates along x
    y: np.ndarray          # (ny+1,) node coordinates along y
    nodes: np.ndarray      # (n_nodes, 2)
    elements: np.ndarray   # (n_elem, 4) int

    @property
    def n_nodes(self) -> int:
        return self.nodes.shape[0]

    @property
    def n_elem(self) -> int:
        return self.elements.shape[0]

    def element_bounds(self, e: int) -> tuple[float, float, float, float]:
        """x_lo, x_hi, y_lo, y_hi of element e."""
        i, j = e % self.nx, e // self.nx
        return self.x[i], self.x[i + 1], self.y[j], self.y[j + 1]

    def element_size(self, e: int) -> tuple[float, float]:
        xlo, xhi, ylo, yhi = self.element_bounds(e)
        return xhi - xlo, yhi - ylo

    def element_corners(self, e: int) -> np.ndarray:
        xlo, xhi, ylo, yhi = self.element_bounds(e)
        return np.array([[xlo, ylo], [xhi, ylo], [xhi, yhi], [xlo, yhi]])

    def locate(self, px: float, py: float) -> int:
        """Index of the element containing point (px, py). Clamped to the domain."""
        i = int(np.clip(np.searchsorted(self.x, px, side="right") - 1, 0, self.nx - 1))
        j = int(np.clip(np.searchsorted(self.y, py, side="right") - 1, 0, self.ny - 1))
        return j * self.nx + i

    def edge_nodes(self, side: str) -> np.ndarray:
        """Node indices on 'bottom', 'top', 'left' or 'right'."""
        nx1 = self.nx + 1
        if side == "bottom":
            return np.arange(nx1)
        if side == "top":
            return np.arange(nx1) + self.ny * nx1
        if side == "left":
            return np.arange(self.ny + 1) * nx1
        if side == "right":
            return np.arange(self.ny + 1) * nx1 + self.nx
        raise ValueError(f"unknown side {side!r}")

    def summary(self) -> dict:
        return {
            "W": self.W, "H": self.H, "nx": self.nx, "ny": self.ny,
            "n_nodes": self.n_nodes, "n_elem": self.n_elem,
            "dx_min": float(np.diff(self.x).min()), "dx_max": float(np.diff(self.x).max()),
            "dy_min": float(np.diff(self.y).min()), "dy_max": float(np.diff(self.y).max()),
        }


def _build(W: float, H: float, x: np.ndarray, y: np.ndarray) -> StructuredMesh:
    nx, ny = len(x) - 1, len(y) - 1
    xx, yy = np.meshgrid(x, y)
    nodes = np.column_stack([xx.ravel(), yy.ravel()])
    i = np.arange(nx)
    j = np.arange(ny)
    I, J = np.meshgrid(i, j)
    n0 = (J * (nx + 1) + I).ravel()
    elements = np.column_stack([n0, n0 + 1, n0 + nx + 2, n0 + nx + 1]).astype(np.int64)
    return StructuredMesh(W=W, H=H, nx=nx, ny=ny, x=x, y=y, nodes=nodes, elements=elements)


def uniform_mesh(W: float, H: float, nx: int, ny: int) -> StructuredMesh:
    """Uniform Q4 mesh. This is the mesh XFEM validation runs on."""
    return _build(W, H, np.linspace(0.0, W, nx + 1), np.linspace(0.0, H, ny + 1))


def crack_aligned_mesh(W: float, H: float, nx: int, ny: int) -> StructuredMesh:
    """Uniform mesh with ny forced odd so mid height falls strictly inside an element row.

    A horizontal crack at y = H/2 then never lands on a mesh line, which is what
    the enrichment scheme needs. A crack lying exactly on an element edge leaves
    no element cut and the Heaviside enrichment degenerates.
    """
    if ny % 2 == 0:
        ny += 1
    return uniform_mesh(W, H, nx, ny)


def graded_1d(length: float, n: int, focus: float, ratio: float = 4.0,
              zone: float = 0.15) -> np.ndarray:
    """Coordinates on [0, length] refined by `ratio` inside a band around `focus`.

    The band half width is `zone` * length. Element size varies smoothly through a
    cosine blend so there is no abrupt jump in aspect ratio at the band edge.
    """
    s = np.linspace(0.0, 1.0, 4001)
    f = focus / length
    d = np.abs(s - f) / max(zone, 1e-9)
    blend = np.where(d < 1.0, 0.5 * (1.0 + np.cos(np.pi * d)), 0.0)
    density = 1.0 + (ratio - 1.0) * blend        # elements per unit length, relative
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (density[1:] + density[:-1]) * np.diff(s))])
    cum /= cum[-1]
    targets = np.linspace(0.0, 1.0, n + 1)
    return np.interp(targets, cum, s) * length


def tip_refined_mesh(W: float, H: float, nx: int, ny: int,
                     tip_x: float, tip_y: float, ratio: float = 4.0,
                     zone_frac: float = 0.15) -> StructuredMesh:
    """Structured mesh with roughly `ratio` times finer elements around the crack tip.

    Refinement is applied independently on each axis so elements stay rectangular.
    Use this for stress recovery and visualisation. Prefer `crack_aligned_mesh` for
    the interaction integral, where uniform spacing keeps the q function clean.
    """
    x = graded_1d(W, nx, tip_x, ratio, zone_frac)
    y = graded_1d(H, ny, tip_y, ratio, zone_frac)
    return _build(W, H, x, y)


# ---------------------------------------------------------------------------
# Q4 shape functions on the reference square [-1, 1]^2
# ---------------------------------------------------------------------------

_XI = np.array([-1.0, 1.0, 1.0, -1.0])
_ETA = np.array([-1.0, -1.0, 1.0, 1.0])


def shape_q4(xi: float, eta: float) -> np.ndarray:
    """N_1..N_4 at parent coordinates."""
    return 0.25 * (1.0 + _XI * xi) * (1.0 + _ETA * eta)


def dshape_q4(xi: float, eta: float) -> np.ndarray:
    """dN/dxi and dN/deta, shape (2, 4)."""
    return np.array([0.25 * _XI * (1.0 + _ETA * eta),
                     0.25 * _ETA * (1.0 + _XI * xi)])


def to_parent(px: float, py: float, xlo: float, xhi: float,
              ylo: float, yhi: float) -> tuple[float, float]:
    return 2.0 * (px - xlo) / (xhi - xlo) - 1.0, 2.0 * (py - ylo) / (yhi - ylo) - 1.0


def to_physical(xi: float, eta: float, xlo: float, xhi: float,
                ylo: float, yhi: float) -> tuple[float, float]:
    return xlo + 0.5 * (xi + 1.0) * (xhi - xlo), ylo + 0.5 * (eta + 1.0) * (yhi - ylo)


# Gauss Legendre points cached by order
_GAUSS: dict[int, tuple[np.ndarray, np.ndarray]] = {}


def gauss_1d(n: int) -> tuple[np.ndarray, np.ndarray]:
    if n not in _GAUSS:
        _GAUSS[n] = np.polynomial.legendre.leggauss(n)
    return _GAUSS[n]


def gauss_2d(n: int) -> tuple[np.ndarray, np.ndarray]:
    """Tensor product rule on [-1,1]^2. Returns points (m,2) and weights (m,)."""
    p, w = gauss_1d(n)
    P, Q = np.meshgrid(p, p, indexing="ij")
    Wp, Wq = np.meshgrid(w, w, indexing="ij")
    return np.column_stack([P.ravel(), Q.ravel()]), (Wp * Wq).ravel()
