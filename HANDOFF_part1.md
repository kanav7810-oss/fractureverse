# FRACTUREVERSE handoff, end of Part 1

Read this file first. It is the only context the next session needs.

---

## 0. Standing instructions from the user

- **Caveman mode stays on for the whole project.** Terse, drop articles and filler, keep every
  technical fact exact. Drop out of caveman only for safety warnings and destructive action
  confirmations. Ponytail is also on: laziest solution that actually works, no speculative
  abstractions, no unrequested features.
- **One single folder** for the whole stack: `C:\fractureverse`. Do not spread across repos.
- **No em dashes anywhere.** Not in code, comments, UI text, README, or the exported PDF.
- **Horizontal scroll rule, absolute.** Never hijack vertical scroll. Applies to every
  container in Part 3.
- Build order is fixed: Part 1, then 2, then 3, then 4. Finish a part fully, write a handoff,
  hand to the next session.

## 1. Environment, already verified

| Item | Value |
|---|---|
| OS | Windows 11 Home, shell is PowerShell, Bash also available |
| Python | 3.11.15 at `python` on PATH |
| Node / npm | v24.18.0 / 11.16.0 |
| GPU | AMD Radeon 610M integrated, no dedicated VRAM. torch is the **CPU build**. Plan PINN training for CPU. |
| Installed and confirmed importable | numpy 2.4.6, scipy 1.17.1, matplotlib 3.11.0, seaborn 0.13.2, pandas 3.0.3, scikit-learn 1.9.0, torch 2.13.0+cpu, xgboost 3.2.0, shap 0.51.0, fastapi 0.139.0, uvicorn 0.51.0, pydantic 2.13.4, reportlab 5.0.0 |

Nothing needs installing for Part 2. Part 3 needs `npm install` only.

## 2. Council verify answers, recorded

1. **All four theories with correct governing equations and units?** Yes. LEFM, EPFM, XFEM and
   peridynamics are implemented and each is validated against an independent target. Units are
   SI throughout with the two literature exceptions documented in section 4.
2. **Are the three domain datasets real and publicly accessible?** The *properties* are real and
   cited to Reilly and Burstein 1975, Yeni 1997, Caler and Carter 1989, Keller 1994, Bergmann
   2001, Bazant and Pfeiffer 1987, NASA/TM-2002-211428, NASGRO, ASTM E399, FHWA NBI and ASCE
   2021. The *bulk NBI CSV* was not downloaded, because no live network fetch was performed in
   Part 1. `data/civil/corrosion.json` carries the NBI condition rating scale and the deficient
   bridge count rather than the 617,000 row table. If Part 2 or 3 wants the real table, pull it
   from `https://www.fhwa.dot.gov/bridge/nbi.cfm` and drop it in `data/civil/`. Nothing in the
   codebase depends on it.
3. **Does the PINN enforce fracture boundary conditions as physics losses?** Not built yet, it
   is Part 2. The XFEM solver already exposes `stress_at`, `displacement_at` and
   `gradients_at`, which is exactly the collocation data the data loss term needs.
4. **Three.js at 50,000 elements and 30 fps on a Radeon 610M?** No, not with 50,000 individually
   drawn elements. Plan for an instanced or merged BufferGeometry with a single draw call, and
   the spec's own automatic fallback to 30x30x10 on a frame time over 50 ms. Budget this in Part 3.
5. **Is the folder structure complete and non overlapping?** Yes for `physics/`, `data/` and
   `research/`. `pinn/`, `ml/`, `python_stats/`, `visualizations/`, `app/`, `api/` and `tests/`
   are not created yet, by design, and are Parts 2 to 4.
6. **Will Playwright tests be deterministic with stochastic ML?** Only if Part 2 saves seeded,
   trained weights to disk and Part 4 loads them instead of training. Part 2 must seed numpy,
   torch and python `random`, and must write model weights plus a fixed test split.
7. **Does the dashboard route three solvers without state bleed?** The backend half is done.
   `physics/unified_solver.py` is stateless: every call builds a fresh solver from a
   `SolveRequest`. Check 14 exercises three domain and theory combinations in one process. The
   frontend half is Part 3.

## 3. What exists right now

```
C:\fractureverse\
  data\aerospace\materials.json          2024-T3, 7075-T6, K_IC vs temperature curve
  data\biomedical\materials.json         cortical bone healthy and osteoporotic, Keller law
  data\biomedical\gait_loading.json      hip force vs gait phase, walking, stairs, stumble
  data\civil\materials.json              concrete, A615 rebar
  data\civil\corrosion.json              Faraday corrosion model, i_corr levels, NBI scale
  data\reference_charts\paris_law_reference.json
  physics\materials.py  mesh.py  lefm.py  epfm.py  xfem.py  peridynamic.py  unified_solver.py
  research\part1_validation.json         full machine readable report, 14 checks
  research\part1_peridynamic_damage.npy  100 x 50 damage field from the branching run
  validate_part1.py
  README.md  requirements.txt  HANDOFF.md
```

Run `python validate_part1.py` to reproduce. Takes about 80 seconds. 14 of 14 pass.

## 4. Unit convention, do not break this

Everything is SI **except**:

- `K_I`, `K_II`, `K_IC` are in **MPa*sqrt(m)**, never Pa*sqrt(m).
- `paris_C` is scaled so `da/dN` is in **m/cycle** when `delta_K` is in **MPa*sqrt(m)**.

Applied stress is passed in **pascals** at every API boundary and divided by 1e6 internally.
`J` is in J/m^2, `G` is in J/m^2, lengths are in metres.

## 5. Public API the next parts should use

```python
from physics.materials import get_material, domain_metadata, list_materials, \
                              keller_modulus, load_reference, use_anchored_paris
from physics.unified_solver import solve, capabilities, SolveRequest, LoadCase, \
                                   CrackConfig, request_from_dict, to_json_safe
```

`capabilities()` returns everything a UI needs to build its selectors in one call: domains,
theories with blurbs, geometries, growth laws, modes, recommended theory per domain.

`solve(SolveRequest(...))` returns a dict. Keys common to every theory: `domain`, `material`,
`theory`, `K_I`, `K_II`, `a_c`, `E_GPa`, `K_IC`, `paris_C`, `paris_m`. LEFM adds `N_f`,
`da_dN`, `years_to_failure` and a full `history` block of arrays. EPFM adds `J_elastic`,
`J_elastic_plastic`, `ctod`, `jr_curve`, `instability`. XFEM adds `K_I_analytical`,
`J_from_xfem`, `kink_angle_deg`, `mesh`, and private `_solver` and `_u` handles.
Peridynamics adds `branched`, `crack_advance`, `damage_max`, `energy_check` and `_damage`.

Call `to_json_safe(result)` before serialising. It strips the private handles and numpy arrays.

Direct workhorses Part 2 will want:

```python
lefm.crack_growth_history(a0, sigma_max_pa, R, mat, W, geometry, law="paris")
    -> dict of numpy arrays a, N, delta_K, K_max, da_dN, K_ratio, plus a_c and N_f
lefm.cycles_to_failure(...)            numerical, quad based
lefm.critical_crack_length(...)        implicit brentq root find, F depends on a
xfem.solve_center_crack(mat, half_length, sigma_pa, W=, nx=, ny=, r_factor=)
    -> dict with K_I, K_II and res["solution"].u for field sampling
epfm.j_integral(solver, u, tip_id=0, r_factor=3.0)
peridynamic.concrete_branching_panel(mat, ..., G0=mat.raw["G_f"])
peridynamic.m_convergence_study(mat, m_values=(2,3,4), delta=0.09, ...)
```

## 6. Validation numbers to quote in the paper

| Quantity | Value |
|---|---|
| XFEM K_I error vs analytical, a/b = 0.3, 0.4, 0.5 | -0.48, -0.43, -0.47 percent |
| XFEM interaction integral domain spread, r_d = 2 to 5 elements | under 0.1 percent of K_I |
| XFEM mesh convergence, 31x61 to 91x181 | error decreasing, 15.3k dof at the production mesh |
| LEFM numerical N_f vs closed form Paris integral | 2.6e-12 percent |
| LEFM Paris slope vs reference bands | matches to better than 0.05 on all four series |
| Pure mode II kink angle | -70.53 degrees, Erdogan and Sih limit is -70.5 |
| EPFM domain J vs K_I squared over E prime | -1.59 percent |
| Peridynamic continuum identity G_0 = c s_0^2 delta^4 / 4 | exact |
| Peridynamic discrete G_0 recovery, delta/dx = 2, 3, 4, 6 | -27.3, -21.7, -16.5, -9.2 percent |
| Peridynamic branching, concrete panel | confirmed, first branch 45 mm past the notch tip, 67 branched columns, up to 3 damage bands per column |
| Peridynamic m convergence, damage profile L2 | 0.55, 0.11, 0.00 at delta/dx of 2, 3, 4 |
| Peridynamic crack advance | 2.025 m across a 3.0 m panel |

Baseline domain lives are in `research/part1_validation.json` under `domain_anchors`. They also
carry `years_to_failure` using the domain duty cycles of 500, 1.5e6 and 5e6 cycles per year.

## 7. Two findings that must not be quietly dropped

**7.1 The specified Paris coefficient for 2024-T3 is conservative.** The project brief pins
`C = 3.6e-10, m = 3.5`. At `delta_K = 10 MPa*sqrt(m)` that predicts `1.14e-6 m/cycle`, about
5.7 times the commonly cited mid range value of `2.0e-7 m/cycle` for 2024-T3 sheet at R = 0.1
in laboratory air. The slope m is correct, only the intercept is high. `paris_C` in
`data/aerospace/materials.json` keeps the specified value, `paris_C_anchored = 6.32e-11`
reproduces the anchor exactly, and `materials.use_anchored_paris(mat)` switches between them.
**Predicted lives with the default are short by roughly 5.7 times.** Part 2 should state which
was used in `stats_summary.json` and, ideally, report both.

**7.2 Bond based peridynamics ties strength to the horizon.** Effective tensile strength scales
as one over the square root of delta, and Poisson ratio is fixed at 1/3 in 2D plane stress.
Matching concrete's 4 MPa tensile strength exactly would need a horizon near the Hillerborg
characteristic length `l_ch = E G_f / f_t^2 = 0.1875 m`. The branching panel is therefore
3.0 m by 1.5 m with delta = 0.0905 m, giving a horizon implied strength of 6.8 MPa against the
12 MPa applied. Every run reports `pd_strength_MPa` next to `sigma_MPa` so the driving ratio is
visible. Do not hide this in Part 2 charts, label it.

## 8. Sharp edges in the code

- `crack_aligned_mesh` forces `ny` odd so a horizontal crack at mid height never lands on a mesh
  line. A crack on an element edge leaves no element cut and the Heaviside enrichment degenerates.
  Keep using it for anything that computes K.
- Enrichment is **shifted**, so displacement boundary conditions apply to standard degrees of
  freedom only. Do not add constraints on enriched dofs.
- The interaction integral and the J integral only visit elements where `grad q` is non zero, so
  the singular tip region is never integrated. That is deliberate, not a gap.
- Cut and tip elements are integrated by exact polygon clipping and fan triangulation. Tip
  elements subdivide 4 times per triangle. Changing `_subdivide` levels changes accuracy.
- `xfem.propagate` rebuilds the whole solver every step. Fine for 12 steps, slow for hundreds.
- `peridynamic.PDModel.bond_forces` mutates `self.broken` when `allow_breaking=True`. Rebuild the
  model for a fresh run rather than resetting.
- `to_json_safe` drops keys beginning with an underscore. That is how `_solver`, `_u` and
  `_damage` are kept out of API responses.

## 9. Part 2, what to build next

Create `ml/`, `pinn/`, `python_stats/`, `visualizations/`.

1. `ml/data_gen.py`: 500 trajectories from `lefm.crack_growth_history` over 5 initial crack
   lengths, 5 stress amplitudes, 4 stress ratios, 5 material parameter samples drawn inside the
   `uncertainty` ranges already present in each `materials.json`. **Seed everything.**
2. `ml/feature_extract.py`, `lstm_model.py`, `xgboost_model.py`, `baseline.py`, `evaluate.py`.
   Report R squared and RMSE per domain. Target LSTM R squared above 0.92.
3. `pinn/`: 8 layers, 128 neurons, tanh, Xavier. Five loss terms with NTK style adaptive
   weighting. Collocation data comes from `xfem.solve_center_crack` plus `solver.stress_at`.
   CPU only, so keep the epoch count realistic and log wall clock honestly.
4. `python_stats/chart_01..17` plus `generate_all.py`. 300 dpi PNG, 12 pt axis labels, legend on
   every multi series chart. Chart 4 can read the XFEM path from `xfem.propagate`, chart 5 and
   16 from `peridynamic`, chart 11 from `data/biomedical/gait_loading.json`, chart 12 from
   `data/civil/corrosion.json`, chart 15 from the `K_IC_temperature_curve` block in
   `data/aerospace/materials.json`.
5. `research/stats_summary.json` and `research/paper_outline.md`.
6. **Save seeded model weights and a fixed test split to disk** so Part 4 Playwright tests are
   deterministic. This is the single highest risk item for Part 4.

Then write `HANDOFF.md` for Part 3 in the same shape as this file.
