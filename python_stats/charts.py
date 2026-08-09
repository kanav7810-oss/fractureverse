"""The 17 figures. Each function is chart_NN and returns the path it wrote.

Physics comes from physics/, the learned models from ml/artifacts and pinn/artifacts,
and three of the figures reuse Part 1 output that is already on disk rather than
re running a solver that has not changed.
"""

from __future__ import annotations

import json
import math

import numpy as np

from physics import epfm, lefm, peridynamic, xfem
from physics.materials import domain_metadata, get_material, load_json, load_reference
from physics.mesh import crack_aligned_mesh

from . import CACHE, RESEARCH
from .style import DOMAIN_COLOR, DOMAIN_LABEL, cached, finish, new

# Anchor cases, the same three the Part 1 validation reports lives for
ANCHOR = {
    "aerospace": dict(material="Al2024-T3", geometry="center", W=0.10,
                      a0=1.0e-3, sigma=150e6, R=0.1),
    "biomedical": dict(material="CorticalBone_healthy", geometry="edge", W=0.02,
                       a0=0.1e-3, sigma=40e6, R=0.1),
    "civil": dict(material="Concrete_normal", geometry="edge", W=0.20,
                  a0=5.0e-3, sigma=2e6, R=0.1),
}
DOMAINS = tuple(ANCHOR)


def anchor_material(domain: str):
    return get_material(domain, ANCHOR[domain]["material"])


def _part1() -> dict:
    return json.loads((RESEARCH / "part1_validation.json").read_text())


# ---------------------------------------------------------------------------
# 1. Paris law rate curves against the reference bands
# ---------------------------------------------------------------------------
def chart_01():
    ref = load_reference()
    fig, ax = new((8.5, 5.5))
    dK = np.logspace(np.log10(0.3), np.log10(40.0), 200)

    for d in DOMAINS:
        m = anchor_material(d)
        ax.loglog(dK, lefm.paris_rate(dK, m.paris_C, m.paris_m),
                  color=DOMAIN_COLOR[d], label=f"{DOMAIN_LABEL[d]}, C = {m.paris_C:.2g}, m = {m.paris_m}")

    al = anchor_material("aerospace")
    c_anch = al.raw.get("paris_C_anchored")
    if c_anch:
        ax.loglog(dK, lefm.paris_rate(dK, float(c_anch), al.paris_m), "--",
                  color=DOMAIN_COLOR["aerospace"],
                  label=f"2024-T3 anchored C = {float(c_anch):.2g}, factor 5.7 lower")

    for name, s in ref["series"].items():
        ax.loglog(s["delta_K"], s["da_dN"], "o", ms=3.5, alpha=0.7,
                  label=f"reference {name}")

    a = ref["anchor"]
    ax.plot(a["delta_K"], a["da_dN"], "k*", ms=13, label="literature anchor, 2024-T3")
    ax.set_xlabel("Stress intensity range delta K (MPa sqrt(m))")
    ax.set_ylabel("Crack growth rate da/dN (m/cycle)")
    ax.set_title("Paris law rate curves against independent reference data")
    ax.set_ylim(1e-12, 1e-3)
    ax.legend(loc="lower right", fontsize=7.5, ncol=1)
    return finish(fig, 1, "paris_rate_curves",
                  "Paris law da/dN for the three domain materials against the reference "
                  "bands. The specified 2024-T3 coefficient sits a factor 5.7 above the "
                  "commonly cited anchor, so the anchored curve is drawn as well.")


# ---------------------------------------------------------------------------
# 2. Crack length against cycle count, three domains
# ---------------------------------------------------------------------------
def chart_02():
    fig, axes = new((11.0, 4.6), ncols=3)
    for ax, d in zip(axes, DOMAINS):
        cfg, m = ANCHOR[d], anchor_material(d)
        for law, ls in (("paris", "-"), ("walker", "--"), ("forman", ":")):
            h = lefm.crack_growth_history(cfg["a0"], cfg["sigma"], cfg["R"], m,
                                          W=cfg["W"], geometry=cfg["geometry"], law=law)
            ax.semilogx(np.maximum(h["N"], 1.0), h["a"] * 1e3, ls,
                        color=DOMAIN_COLOR[d], label=f"{law}, N_f = {h['N_f']:.3g}")
        ax.axhline(h["a_c"] * 1e3, color="k", lw=1.0, ls="-.", label="critical length a_c")
        ax.set_xlabel("Cycles N")
        ax.set_ylabel("Crack length a (mm)")
        ax.set_title(DOMAIN_LABEL[d], fontsize=10)
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle("Fatigue crack growth to failure under three growth laws", y=1.02)
    return finish(fig, 2, "crack_growth_curves",
                  "Crack length against cycle count for the three domain anchor cases "
                  "under Paris, Walker and Forman growth laws.")


# ---------------------------------------------------------------------------
# 3. Geometry correction factors and the resulting K_I
# ---------------------------------------------------------------------------
def chart_03():
    fig, (ax1, ax2) = new((10.5, 4.6), ncols=2)
    W = 0.1
    RANGE = {"center": (0.02, 0.45), "edge": (0.02, 0.60),
             "compact": (0.20, 0.75), "through": (0.02, 0.45)}
    for geom, col in (("center", "#1f77b4"), ("edge", "#d62728"),
                      ("compact", "#2ca02c"), ("through", "#9467bd")):
        r = np.linspace(*RANGE[geom], 200)
        F = [lefm.geometry_factor(x * W, W, geom) for x in r]
        ax1.plot(r, F, color=col, label=geom)
        ax2.plot(r * W * 1e3, [lefm.stress_intensity(100e6, x * W, W, geom) for x in r],
                 color=col, label=geom)
    ax1.set_xlabel("Normalised crack length a/W")
    ax1.set_ylabel("Geometry factor F")
    ax1.set_title("Geometry correction factors")
    ax1.set_ylim(0, 8)
    ax1.legend()
    ax2.set_xlabel("Crack length a (mm)")
    ax2.set_ylabel("K_I (MPa sqrt(m))")
    ax2.set_title("K_I at 100 MPa applied stress, W = 100 mm")
    ax2.legend()
    return finish(fig, 3, "geometry_factors",
                  "Handbook geometry correction factors and the stress intensity they "
                  "produce at a fixed applied stress.")


# ---------------------------------------------------------------------------
# 4. XFEM mixed mode crack path
# ---------------------------------------------------------------------------
def _propagate_run() -> dict:
    mat = get_material("aerospace", "Al2024-T3")
    W, H = 0.1, 0.2
    mesh = crack_aligned_mesh(W, H, 61, 121)
    a = 0.015
    beta = math.radians(30.0)
    p0 = np.array([0.5 * W - a * math.cos(beta), 0.5 * H - a * math.sin(beta)])
    p1 = np.array([0.5 * W + a * math.cos(beta), 0.5 * H + a * math.sin(beta)])
    crack = xfem.Crack(np.vstack([p0, p1]))
    hist = xfem.propagate(mesh, mat, crack, 100e6, n_steps=12, da_factor=0.6)
    return {k: (v if isinstance(v, list) else float(v)) for k, v in hist.items()}


def chart_04():
    hist = cached("xfem_propagate_30deg", _propagate_run)
    path = np.asarray(hist["path"])
    final = np.asarray(hist["final_crack"])
    fig, (ax1, ax2) = new((10.5, 4.6), ncols=2)

    ax1.plot(final[:, 0] * 1e3, final[:, 1] * 1e3, "-", color="0.5",
             label="crack, all segments")
    ax1.plot(path[:, 0] * 1e3, path[:, 1] * 1e3, "o-", color="#d62728", ms=4,
             label="advancing tip, 12 steps")
    ax1.plot(path[0, 0] * 1e3, path[0, 1] * 1e3, "ks", ms=7, label="initial tip")
    ax1.set_xlabel("x (mm)")
    ax1.set_ylabel("y (mm)")
    ax1.set_title("Mixed mode path, 30 degree initial crack")
    ax1.set_aspect("equal")
    ax1.legend(fontsize=8)

    step = np.arange(len(hist["K_I"]))
    ax2.plot(step, hist["K_I"], "o-", label="K_I")
    ax2.plot(step, hist["K_II"], "s-", label="K_II")
    ax2.plot(step, hist["K_eff"], "^-", label="K_eff")
    ax2b = ax2.twinx()
    ax2b.plot(step, hist["theta_deg"], "v--", color="0.4", label="kink angle")
    ax2b.set_ylabel("Kink angle (degrees)")
    ax2b.grid(False)
    ax2.set_xlabel("Propagation step")
    ax2.set_ylabel("Stress intensity (MPa sqrt(m))")
    ax2.set_title("Stress intensity history along the path")
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2b.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, fontsize=8, loc="center right")
    return finish(fig, 4, "xfem_crack_path",
                  "XFEM crack path for an inclined centre crack. The path turns towards "
                  "mode I within the first two steps, which is the maximum circumferential "
                  "stress criterion doing its job, and K_II collapses accordingly.")


# ---------------------------------------------------------------------------
# 5. Peridynamic damage field and branching
# ---------------------------------------------------------------------------
def chart_05():
    dmg = np.load(RESEARCH / "part1_peridynamic_damage.npy")
    blk = _part1()["peridynamic_branching"]
    W, H = blk["panel"]["W"], blk["panel"]["H"]
    fig, ax = new((9.0, 4.8))
    im = ax.imshow(dmg.T, origin="lower", extent=[0, W, 0, H], cmap="inferno",
                   vmin=0.0, vmax=0.5, aspect="equal")
    ax.axhline(0.5 * H, xmax=blk["notch_tip_x"] / W, color="cyan", lw=2.0,
               label="machined notch")
    ax.axvline(blk["first_branch_x"], color="w", ls="--", lw=1.2,
               label=f"first branch at x = {blk['first_branch_x']:.3f} m")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Peridynamic damage, concrete panel, applied "
                 f"{blk['sigma_MPa']:.0f} MPa against horizon implied strength "
                 f"{blk['pd_strength_MPa']:.1f} MPa")
    fig.colorbar(im, ax=ax, label="damage, broken bond fraction")
    ax.legend(loc="upper right", fontsize=8)
    return finish(fig, 5, "peridynamic_damage",
                  "Bond based peridynamic damage field. The crack chooses its own path "
                  "and branches without any predefined path. The driving ratio is the "
                  "applied stress against the horizon implied strength, not the handbook "
                  "tensile strength, and both numbers are on the figure.")


# ---------------------------------------------------------------------------
# 6. J-R curves and instability
# ---------------------------------------------------------------------------
def chart_06():
    fig, axes = new((11.0, 4.6), ncols=3)
    for ax, d in zip(axes, DOMAINS):
        cfg, m = ANCHOR[d], anchor_material(d)
        R = epfm.jr_curve(m)
        da = np.linspace(1e-5, 2e-3, 200)
        ax.plot(da * 1e3, R.J(da) / 1e3, color=DOMAIN_COLOR[d], label="J-R material curve")
        for sf, ls in ((1.0, "--"), (1.5, ":"), (2.0, "-.")):
            sig = cfg["sigma"] * sf
            Ja = [epfm.j_elastic_plastic(
                lefm.stress_intensity(sig, cfg["a0"] + x, cfg["W"], cfg["geometry"]),
                sig, m) / 1e3 for x in da]
            ax.plot(da * 1e3, Ja, ls, color="0.35",
                    label=f"applied J at {sig / 1e6:.0f} MPa")
        inst = epfm.instability_point(m, cfg["sigma"] * 2.0, cfg["a0"],
                                      cfg["W"], cfg["geometry"])
        if inst.get("delta_a_instability"):
            ax.plot(inst["delta_a_instability"] * 1e3, inst["J_instability"] / 1e3,
                    "kx", ms=10, label="tangency, unstable tearing")
        ax.set_xlabel("Crack extension delta a (mm)")
        ax.set_ylabel("J (kJ/m^2)")
        ax.set_title(DOMAIN_LABEL[d], fontsize=10)
        ax.set_yscale("log")
        ax.legend(fontsize=7.5)
    fig.suptitle("Elastic plastic driving force against material resistance", y=1.02)
    return finish(fig, 6, "jr_curves",
                  "J-R resistance curves with applied J at three load levels. Where the "
                  "applied curve becomes tangent to the resistance curve, tearing is "
                  "unstable under load control.")


# ---------------------------------------------------------------------------
# 7. CTOD against applied stress
# ---------------------------------------------------------------------------
def chart_07():
    fig, ax = new((8.5, 5.0))
    for d in DOMAINS:
        cfg, m = ANCHOR[d], anchor_material(d)
        sig = np.linspace(0.05, 0.9, 120) * m.sigma_Y
        K = np.array([lefm.stress_intensity(s, cfg["a0"], cfg["W"], cfg["geometry"])
                      for s in sig])
        J = np.array([epfm.j_elastic_plastic(k, s, m) for k, s in zip(K, sig)])
        ax.semilogy(sig / m.sigma_Y, [epfm.ctod(j, m) * 1e6 for j in J],
                    color=DOMAIN_COLOR[d], label=f"{DOMAIN_LABEL[d]}, elastic plastic")
        ax.semilogy(sig / m.sigma_Y, [epfm.ctod_from_K(k, m) * 1e6 for k in K], "--",
                    color=DOMAIN_COLOR[d], alpha=0.6, label=f"{d}, elastic only")
        ax.axhline(epfm.ctod_critical(m) * 1e6, color=DOMAIN_COLOR[d], ls=":", lw=1.2,
                   label=f"{d}, critical CTOD")
    ax.set_xlabel("Applied stress over yield strength")
    ax.set_ylabel("CTOD (micrometres)")
    ax.set_title("Crack tip opening displacement against load level")
    ax.legend(fontsize=7.5, ncol=2)
    return finish(fig, 7, "ctod_vs_load",
                  "CTOD from the elastic plastic J against the elastic estimate. The gap "
                  "opens once the applied stress passes roughly half of yield.")


# ---------------------------------------------------------------------------
# 8. Critical crack length against applied stress
# ---------------------------------------------------------------------------
def chart_08():
    fig, ax = new((8.5, 5.0))
    for d in DOMAINS:
        cfg, m = ANCHOR[d], anchor_material(d)
        sig = np.geomspace(0.02 * m.sigma_Y, 0.95 * m.sigma_Y, 120)
        ac = [lefm.critical_crack_length(s, m.K_IC, cfg["W"], cfg["geometry"])
              for s in sig]
        ax.loglog(sig / 1e6, np.array(ac) * 1e3, color=DOMAIN_COLOR[d],
                  label=DOMAIN_LABEL[d])
        ac0 = lefm.critical_crack_length(cfg["sigma"], m.K_IC, cfg["W"], cfg["geometry"])
        ax.plot(cfg["sigma"] / 1e6, ac0 * 1e3, "o", color=DOMAIN_COLOR[d], ms=8,
                label=f"{d} anchor, a_c = {ac0 * 1e3:.2f} mm")
    ax.set_xlabel("Applied stress (MPa)")
    ax.set_ylabel("Critical crack length a_c (mm)")
    ax.set_title("Critical crack length, implicit solve with a dependent geometry factor")
    ax.legend(fontsize=8)
    return finish(fig, 8, "critical_crack_length",
                  "Critical crack length against applied stress for the three domains, "
                  "solved implicitly because the geometry factor itself depends on a.")


# ---------------------------------------------------------------------------
# 9. Small scale yielding validity map
# ---------------------------------------------------------------------------
def chart_09():
    m = anchor_material("aerospace")
    cfg = ANCHOR["aerospace"]
    a = np.geomspace(2e-4, 3e-2, 160)
    sig = np.linspace(20e6, 340e6, 160)
    A, S = np.meshgrid(a, sig)
    K = np.vectorize(lambda aa, ss: lefm.stress_intensity(ss, aa, cfg["W"], "center"))(A, S)
    rp = np.vectorize(lambda k: lefm.plastic_zone_size(k, m))(K)
    ratio = rp / A

    fig, (ax1, ax2) = new((11.0, 4.6), ncols=2)
    cs = ax1.contourf(A * 1e3, S / 1e6, np.log10(ratio), levels=20, cmap="viridis")
    ax1.contour(A * 1e3, S / 1e6, ratio, levels=[0.02], colors="w", linewidths=2)
    ax1.set_xscale("log")
    ax1.set_xlabel("Crack length a (mm)")
    ax1.set_ylabel("Applied stress (MPa)")
    ax1.set_title("log10 of plastic zone over crack length, 2024-T3\n"
                  "white contour is the 0.02 small scale yielding limit")
    fig.colorbar(cs, ax=ax1, label="log10(r_p / a)")

    for s in (100e6, 150e6, 200e6, 250e6):
        k = np.array([lefm.stress_intensity(s, aa, cfg["W"], "center") for aa in a])
        ax2.loglog(a * 1e3, [lefm.plastic_zone_size(kk, m) * 1e3 for kk in k],
                   label=f"{s / 1e6:.0f} MPa applied")
    ax2.loglog(a * 1e3, a * 1e3 * 0.02, "k--", label="2 percent of crack length")
    ax2.set_xlabel("Crack length a (mm)")
    ax2.set_ylabel("Plastic zone size r_p (mm)")
    ax2.set_title("Plastic zone growth, LEFM validity")
    ax2.legend(fontsize=8)
    return finish(fig, 9, "ssy_validity",
                  "Where linear elastic fracture mechanics is allowed to speak. Above the "
                  "white contour the plastic zone is more than two percent of the crack "
                  "length and the elastic plastic treatment is required.")


# ---------------------------------------------------------------------------
# 10. Mixed mode kink angle
# ---------------------------------------------------------------------------
def chart_10():
    fig, ax = new((8.5, 5.0))
    ratio = np.linspace(0.0, 6.0, 400)
    theta = [math.degrees(xfem.XFEMSolver.kink_angle(1.0, r)) for r in ratio]
    ax.plot(ratio, theta, color="#1f77b4",
            label="maximum circumferential stress criterion")
    ax.axhline(-70.53, color="k", ls="--", lw=1.2,
               label="pure mode II limit, -70.5 degrees, Erdogan and Sih")

    cases = _part1()["xfem_mixed_mode"]["cases"]
    r = [c["K_II_over_K_I"] for c in cases if c["K_I"] > 1e-9]
    t = [c["kink_angle_deg"] for c in cases if c["K_I"] > 1e-9]
    ax.plot(r, t, "o", color="#d62728", ms=8, label="XFEM interaction integral, Part 1")
    for c in cases:
        if c["K_I"] > 1e-9:
            ax.annotate(f"{c['beta_deg']:.0f} deg", (c["K_II_over_K_I"], c["kink_angle_deg"]),
                        textcoords="offset points", xytext=(6, 6), fontsize=8)
    ax.set_xlabel("Mode mixity K_II / K_I")
    ax.set_ylabel("Kink angle (degrees)")
    ax.set_title("Crack turning angle against mode mixity")
    ax.legend(fontsize=8)
    return finish(fig, 10, "kink_angle",
                  "Kink angle against mode mixity. The XFEM points for inclined cracks "
                  "sit on the analytical criterion and the pure mode II asymptote is "
                  "recovered to 0.03 degrees.")


# ---------------------------------------------------------------------------
# 11. Gait loading and the stress intensity it drives
# ---------------------------------------------------------------------------
def chart_11():
    g = load_json("biomedical", "gait_loading.json")
    cfg, m = ANCHOR["biomedical"], anchor_material("biomedical")
    bw = load_json("biomedical", "materials.json")["patient_loading"]["body_weight_N"]
    area = 3.5e-4    # implant interface bearing area, m^2

    fig, (ax1, ax2) = new((11.0, 4.6), ncols=2)
    ph = np.asarray(g["phase_percent"])
    for key, col, lab in (("walking_BW", "#1f77b4", "level walking"),
                          ("stair_climbing_BW", "#ff7f0e", "stair climbing"),
                          ("stumble_BW", "#d62728", "stumble event")):
        y = np.asarray(g[key])
        ax1.plot(ph, y, color=col, label=lab)
        sig = y * bw / area
        ax2.plot(ph, [lefm.stress_intensity(s, cfg["a0"], cfg["W"], cfg["geometry"])
                      for s in sig], color=col, label=lab)
    ax1.axvspan(0, 62, alpha=0.08, color="k")
    ax1.annotate("stance phase", (28, 0.3), fontsize=9)
    ax1.set_xlabel("Gait cycle phase (percent)")
    ax1.set_ylabel("Hip contact force (body weights)")
    ax1.set_title("Hip joint loading, Bergmann 2001 telemetry")
    ax1.legend(fontsize=8)
    ax2.axhline(m.K_IC, color="k", ls="--", label=f"K_IC = {m.K_IC} MPa sqrt(m)")
    ax2.set_xlabel("Gait cycle phase (percent)")
    ax2.set_ylabel("K_I at a 0.1 mm microcrack (MPa sqrt(m))")
    ax2.set_title("Driving force at the implant bone interface")
    ax2.legend(fontsize=8)
    return finish(fig, 11, "gait_loading",
                  "Measured hip contact force through the gait cycle and the stress "
                  "intensity it drives at a 0.1 mm interface microcrack. A stumble is "
                  "about three times the walking peak and happens roughly once per "
                  "thousand cycles.")


# ---------------------------------------------------------------------------
# 12. Corrosion coupled civil life
# ---------------------------------------------------------------------------
def chart_12():
    c = load_json("civil", "corrosion.json")
    k = c["faraday_model"]["constant_mm_per_year_per_uA_cm2"]
    cfg, m = ANCHOR["civil"], anchor_material("civil")
    years = np.linspace(0, 75, 200)

    fig, (ax1, ax2) = new((11.0, 4.6), ncols=2)
    for name, blk in c["corrosion_levels"].items():
        i = blk["i_corr_uA_cm2"]
        ax1.plot(years, k * i * years, label=f"{name}, i_corr = {i} uA/cm^2")
    ax1.axhline(1.0, color="k", ls="--", label="1 mm section loss")
    ax1.set_xlabel("Service years")
    ax1.set_ylabel("Corrosion penetration (mm)")
    ax1.set_title("Faraday penetration, Andrade and Alonso 1996")
    ax1.legend(fontsize=8)

    # section loss raises the stress the same load produces, which shortens life
    d0 = 16.0   # mm rebar diameter
    loss = np.linspace(0.0, 3.0, 60)
    lives = []
    for lo in loss:
        factor = (d0 / max(d0 - 2 * lo, 1e-3)) ** 2   # area loss to stress rise
        n = lefm.cycles_to_failure(cfg["a0"], cfg["sigma"] * factor, cfg["R"], m,
                                   W=cfg["W"], geometry=cfg["geometry"])["N_f"]
        lives.append(lefm.cycles_to_years(max(n, 1.0), "civil"))
    ax2.semilogy(loss, lives, color=DOMAIN_COLOR["civil"], label="predicted life")
    for name, blk in c["corrosion_levels"].items():
        i = blk["i_corr_uA_cm2"]
        if i > 0:
            ax2.axvline(k * i * 24.0, ls=":", lw=1.2,
                        label=f"{name} after 24 months of inspection interval")
    ax2.set_xlabel("Radial section loss per side (mm), 16 mm bar")
    ax2.set_ylabel("Years to failure at 5e6 cycles per year")
    ax2.set_title("Corrosion fatigue coupling")
    ax2.legend(fontsize=7.5)
    return finish(fig, 12, "corrosion_coupling",
                  "Chloride driven section loss and the fatigue life it removes. Section "
                  "loss is converted to a stress rise on the remaining area, which is the "
                  "simplest defensible coupling and is stated as such.")


# ---------------------------------------------------------------------------
# 13. Model parity plot
# ---------------------------------------------------------------------------
def _ml_predictions() -> dict:
    from ml import lstm_model, xgboost_model
    from ml.baseline import closed_form_baseline, ridge_baseline
    from ml.feature_extract import prepared
    ds = prepared()
    out = {"y": ds["y"][ds["split"]["test"]].tolist(),
           "domain": ds["domain"][ds["split"]["test"]].tolist(), "models": {}}
    for res in (lstm_model.load(ds), xgboost_model.load(ds),
                ridge_baseline(ds), closed_form_baseline(ds)):
        out["models"][res["name"]] = np.asarray(res["pred"]["test"]).tolist()
    return out


def chart_13():
    p = cached("ml_predictions", _ml_predictions)
    rep = json.loads((RESEARCH / "ml_report.json").read_text())
    y = np.asarray(p["y"])
    dom = np.asarray(p["domain"])
    names = list(p["models"])
    fig, axes = new((11.0, 3.2), ncols=len(names), sharey=True)
    lo, hi = y.min() - 0.3, y.max() + 0.3
    for ax, n in zip(np.atleast_1d(axes), names):
        pred = np.asarray(p["models"][n])
        for d in DOMAINS:
            msk = dom == d
            ax.plot(y[msk], pred[msk], ".", ms=4, color=DOMAIN_COLOR[d], label=d)
        ax.plot([lo, hi], [lo, hi], "k--", lw=1.0, label="perfect")
        s = rep["models"][n]["test"]
        ax.set_title(f"{n}\nR2 = {s['r2']:.4f}, RMSE = {s['rmse']:.3f} dec", fontsize=9)
        ax.set_xlabel("True log10 N_f")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
    np.atleast_1d(axes)[0].set_ylabel("Predicted log10 N_f")
    np.atleast_1d(axes)[-1].legend(fontsize=7.5, loc="upper left")
    fig.suptitle("Held out test split, 225 trajectories, fixed seed", y=1.06)
    return finish(fig, 13, "model_parity",
                  "Predicted against true fatigue life on the fixed test split. Every "
                  "model clears the 0.92 target comfortably, which says the mapping is "
                  "close to log linear, not that the models are remarkable.")


# ---------------------------------------------------------------------------
# 14. SHAP attribution
# ---------------------------------------------------------------------------
def chart_14():
    blob = json.loads((CACHE.parent.parent / "ml" / "artifacts" / "shap_summary.json").read_text())
    fig, ax = new((8.5, 5.2))
    names = blob["features"][::-1]
    vals = blob["mean_abs_shap"][::-1]
    ax.barh(names, vals, color="#1f77b4")
    ax.set_xlabel("Mean absolute SHAP value (decades of life)")
    ax.set_title("XGBoost feature attribution on the test split")
    ax.grid(axis="y", alpha=0.0)
    return finish(fig, 14, "shap_attribution",
                  "Mean absolute SHAP value per feature. The cycle count already elapsed "
                  "inside the observation window dominates, which is the model finding "
                  "the same thing the Paris integral says.")


# ---------------------------------------------------------------------------
# 15. Toughness against temperature
# ---------------------------------------------------------------------------
def chart_15():
    blk = load_json("aerospace", "materials.json")["K_IC_temperature_curve"]
    cfg = ANCHOR["aerospace"]
    m = anchor_material("aerospace")
    T = np.asarray(blk["temperature_K"], float)
    K = np.asarray(blk["K_IC_MPa_sqrt_m"], float)

    fig, (ax1, ax2) = new((11.0, 4.6), ncols=2)
    ax1.plot(T, K, "o-", color="#1f77b4", label="2024-T3 literature trend")
    ax1.axvline(293, color="k", ls="--", label="room temperature, 293 K")
    ax1.set_xlabel("Temperature (K)")
    ax1.set_ylabel("K_IC (MPa sqrt(m))")
    ax1.set_title("Toughness against temperature, no sharp transition in an FCC alloy")
    ax1.legend(fontsize=8)

    for s, col in ((100e6, "#1f77b4"), (150e6, "#ff7f0e"), (200e6, "#d62728")):
        ac = [lefm.critical_crack_length(s, k, cfg["W"], "center") * 1e3 for k in K]
        ax2.plot(T, ac, "o-", color=col, label=f"{s / 1e6:.0f} MPa applied")
    ax2.set_xlabel("Temperature (K)")
    ax2.set_ylabel("Critical crack length (mm)")
    ax2.set_title("Tolerable flaw size against temperature")
    ax2.legend(fontsize=8)
    return finish(fig, 15, "toughness_temperature",
                  "Fracture toughness against temperature and the flaw size it tolerates. "
                  "Aluminium is face centred cubic so there is no ductile to brittle "
                  "transition, only a steady fall above about 400 K.")


# ---------------------------------------------------------------------------
# 16. Peridynamic m convergence
# ---------------------------------------------------------------------------
def chart_16():
    conv = _part1()["peridynamic_convergence"]
    runs = conv["runs"]
    m = [r["m"] for r in runs]
    fig, (ax1, ax2) = new((11.0, 4.6), ncols=2)
    ax1.semilogy(m, [max(r["profile_L2_error_vs_finest"], 1e-4) for r in runs],
                 "o-", color="#2ca02c", label="damage profile L2 versus finest grid")
    ax1.set_xlabel("Horizon over grid spacing, delta / dx")
    ax1.set_ylabel("Relative L2 error")
    ax1.set_title(f"m convergence at fixed horizon delta = {conv['delta']} m")
    ax1.legend(fontsize=8)

    disc = _part1()["peridynamic_calibration"]["cases"]
    dm = [d["m_ratio"] for d in disc]
    de = [d["error_percent"] for d in disc]
    ax2.plot(dm, de, "s-", color="#d62728", label="discrete G_0 recovery error")
    ax2.plot(m, [r["G0_error_percent"] for r in runs], "o--", color="#1f77b4",
             label="G_0 error inside the convergence runs")
    ax2.axhline(0.0, color="k", lw=1.0, label="continuum identity, exact")
    ax2.set_xlabel("Horizon over grid spacing, delta / dx")
    ax2.set_ylabel("Fracture energy error (percent)")
    ax2.set_title("Discrete bond summation against the continuum identity")
    ax2.legend(fontsize=8)
    return finish(fig, 16, "peridynamic_convergence",
                  "Peridynamic m convergence. The damage profile converges as the grid is "
                  "refined at a fixed horizon, and the discrete fracture energy approaches "
                  "the continuum identity from below.")


# ---------------------------------------------------------------------------
# 17. PINN training and accuracy
# ---------------------------------------------------------------------------
def chart_17():
    art = CACHE.parent.parent / "pinn" / "artifacts"
    hist = json.loads((art / "pinn_history.json").read_text())
    rep = json.loads((art / "pinn_report.json").read_text())
    f = np.load(art / "pinn_fields.npz")

    fig, (ax1, ax2, ax3) = new((13.0, 4.2), ncols=3)
    for n in rep["loss_names"]:
        ax1.semilogy(hist["epoch"], np.maximum(hist[n], 1e-12), label=n)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss term")
    ax1.set_title("Five physics losses")
    ax1.legend(fontsize=7.5)

    w = np.asarray(hist["weights"])
    for i, n in enumerate(rep["loss_names"]):
        ax2.semilogy(hist["epoch"], w[:, i], label=n)
    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Adaptive weight lambda")
    ax2.set_title("NTK style gradient norm weighting")
    ax2.legend(fontsize=7.5)

    ax3.plot(f["cod_x"] * 1e3, f["cod_xfem"] * 1e6, "-", color="k", label="XFEM")
    ax3.plot(f["cod_x"] * 1e3, f["cod_pinn"] * 1e6, "--", color="#d62728", label="PINN")
    ax3.set_xlabel("x along the crack (mm)")
    ax3.set_ylabel("Crack opening (micrometres)")
    acc = rep["accuracy"]
    ax3.set_title(f"Opening profile\nrelative L2 on displacement "
                  f"{acc['displacement_relative_L2_vs_xfem'] * 100:.1f} percent", fontsize=10)
    ax3.legend(fontsize=8)
    fig.subplots_adjust(wspace=0.38)
    fig.suptitle(f"PINN, 8 x 128 tanh, {rep['epochs']} epochs, "
                 f"{rep['wall_clock_s']:.0f} s on CPU", y=1.04)
    return finish(fig, 17, "pinn_training",
                  "PINN loss history, the adaptive weights that produced it, and the crack "
                  "opening profile against XFEM. Wall clock is CPU only and is reported "
                  "as measured.")


ALL = [chart_01, chart_02, chart_03, chart_04, chart_05, chart_06, chart_07,
       chart_08, chart_09, chart_10, chart_11, chart_12, chart_13, chart_14,
       chart_15, chart_16, chart_17]
