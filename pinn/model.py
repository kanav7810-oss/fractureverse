"""Network and physics losses for the centre cracked tension panel.

Geometry matches physics.xfem.solve_center_crack exactly, so the XFEM solution can
be used as the data term and as the error reference:

    panel 0 <= x <= W, 0 <= y <= H,  H = 2 W
    crack along y = H/2 from x = W/2 - a to x = W/2 + a
    uniform traction sigma_yy = sigma on y = H, tractions free on x = 0, x = W
    roller on y = 0, so v = 0 there

The plain MLP cannot represent the displacement jump across the crack faces, so
the two crack tips contribute the four Westergaard branch functions as extra input
features. sqrt(r) sin(theta/2) is discontinuous across the branch cut, which is
placed on the crack, and that is what carries the opening. This is the same idea
as the XFEM enrichment, fed in as inputs rather than as extra degrees of freedom.

Hard constraint: v = (y / H) * net_v, so the roller boundary condition is exact and
never competes with the other losses.

Five loss terms, in this order:
    0 pde          equilibrium, div sigma = 0, both components, interior
    1 traction_top sigma_yy = sigma and sigma_xy = 0 on y = H
    2 traction_side sigma_xx = sigma_xy = 0 on x = 0 and x = W
    3 crack_face   sigma_yy = sigma_xy = 0 just above and just below the crack
    4 data         XFEM displacements at interior collocation points
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn

LOSS_NAMES = ("pde", "traction_top", "traction_side", "crack_face", "data")


class Panel:
    """Non dimensionalisation and the enrichment feature map."""

    def __init__(self, W: float, H: float, a: float, sigma: float,
                 E: float, nu: float):
        self.W, self.H, self.a, self.sigma = W, H, a, sigma
        self.E, self.nu = E, nu
        self.xc, self.yc = 0.5 * W, 0.5 * H
        self.u_ref = sigma * W / E          # displacement scale
        self.tips = ((self.xc + a, 0.0), (self.xc - a, math.pi))

    def features(self, xy: torch.Tensor) -> torch.Tensor:
        """[x_hat, y_hat] plus 4 branch functions per tip. 10 inputs."""
        x, y = xy[:, 0:1], xy[:, 1:2]
        feats = [x / self.W, y / self.H]
        for tx, alpha in self.tips:
            dx, dy = x - tx, y - self.yc
            ca, sa = math.cos(alpha), math.sin(alpha)
            xl = ca * dx + sa * dy
            yl = -sa * dx + ca * dy
            r = torch.sqrt(xl ** 2 + yl ** 2 + 1e-16)
            th = torch.atan2(yl, xl)
            sr = torch.sqrt(r) / math.sqrt(self.a)
            feats += [sr * torch.cos(th / 2), sr * torch.sin(th / 2),
                      sr * torch.sin(th / 2) * torch.sin(th),
                      sr * torch.cos(th / 2) * torch.sin(th)]
        return torch.cat(feats, dim=1)


class PINN(nn.Module):
    """8 hidden layers, 128 neurons, tanh, Xavier initialisation."""

    def __init__(self, panel: Panel, n_in: int = 10, width: int = 128, depth: int = 8):
        super().__init__()
        layers, d = [], n_in
        for _ in range(depth):
            layers += [nn.Linear(d, width), nn.Tanh()]
            d = width
        layers += [nn.Linear(d, 2)]
        self.net = nn.Sequential(*layers)
        self.panel = panel
        for m in self.net:
            if isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, xy: torch.Tensor) -> torch.Tensor:
        """Displacement [u, v] in metres."""
        out = self.net(self.panel.features(xy)) * self.panel.u_ref
        v = out[:, 1:2] * (xy[:, 1:2] / self.panel.H)   # hard roller at y = 0
        return torch.cat([out[:, 0:1], v], dim=1)


def _grad(out: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
    return torch.autograd.grad(out, x, torch.ones_like(out), create_graph=True)[0]


def stresses(model: PINN, xy: torch.Tensor):
    """Plane stress Cauchy components, Pa. xy must require grad."""
    uv = model(xy)
    gu = _grad(uv[:, 0:1], xy)
    gv = _grad(uv[:, 1:2], xy)
    exx, eyy = gu[:, 0:1], gv[:, 1:2]
    gxy = gu[:, 1:2] + gv[:, 0:1]
    E, nu = model.panel.E, model.panel.nu
    c = E / (1.0 - nu ** 2)
    sxx = c * (exx + nu * eyy)
    syy = c * (eyy + nu * exx)
    sxy = E / (2.0 * (1.0 + nu)) * gxy
    return sxx, syy, sxy, uv


def loss_terms(model: PINN, pts: dict) -> list[torch.Tensor]:
    """The five terms, each already mean squared and non dimensionalised by sigma."""
    s = model.panel.sigma

    # 0 equilibrium
    xy = pts["interior"].requires_grad_(True)
    sxx, syy, sxy, _ = stresses(model, xy)
    dsxx = _grad(sxx, xy)
    dsyy = _grad(syy, xy)
    dsxy = _grad(sxy, xy)
    scale = s / model.panel.a          # stress gradient scale
    rx = (dsxx[:, 0:1] + dsxy[:, 1:2]) / scale
    ry = (dsxy[:, 0:1] + dsyy[:, 1:2]) / scale
    l_pde = (rx ** 2).mean() + (ry ** 2).mean()

    # 1 top traction
    xy = pts["top"].requires_grad_(True)
    _, syy, sxy, _ = stresses(model, xy)
    l_top = (((syy - s) / s) ** 2).mean() + ((sxy / s) ** 2).mean()

    # 2 free lateral edges
    xy = pts["side"].requires_grad_(True)
    sxx, _, sxy, _ = stresses(model, xy)
    l_side = ((sxx / s) ** 2).mean() + ((sxy / s) ** 2).mean()

    # 3 traction free crack faces, sampled just above and just below
    xy = pts["crack"].requires_grad_(True)
    _, syy, sxy, _ = stresses(model, xy)
    l_crack = ((syy / s) ** 2).mean() + ((sxy / s) ** 2).mean()

    # 4 data from XFEM
    xy = pts["data_xy"]
    uv = model(xy)
    l_data = (((uv - pts["data_uv"]) / model.panel.u_ref) ** 2).mean()

    return [l_pde, l_top, l_side, l_crack, l_data]
