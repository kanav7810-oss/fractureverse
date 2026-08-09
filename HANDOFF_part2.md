# FRACTUREVERSE handoff, end of Part 2

Read this file first. It is the only context the next session needs. The Part 1 handoff is
kept verbatim as `HANDOFF_part1.md` if you want the original physics detail, but everything
still load bearing has been carried forward below.

---

## 0. Standing instructions from the user

- **Caveman mode stays on for the whole project.** Terse, drop articles and filler, keep every
  technical fact exact. Drop out of caveman only for safety warnings and destructive action
  confirmations. Ponytail is also on: laziest solution that actually works, no speculative
  abstractions, no unrequested features.
- **One single folder** for the whole stack: `C:\fractureverse`. Do not spread across repos.
- **No em dashes anywhere.** Not in code, comments, UI text, README, or the exported PDF.
  `validate_part2.py` check 15 enforces this for Python and Markdown. Part 3 should extend
  that check to `.ts`, `.tsx` and `.css`.
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
| GPU | AMD Radeon 610M integrated, no dedicated VRAM. torch is the **CPU build**. |
| Python packages | numpy 2.4.6, scipy 1.17.1, matplotlib 3.11.0, seaborn 0.13.2, pandas 3.0.3, scikit-learn 1.9.0, torch 2.13.0+cpu, xgboost 3.2.0, shap 0.51.0, fastapi 0.139.0, uvicorn 0.51.0, pydantic 2.13.4, reportlab 5.0.0 |

Nothing needs installing for Part 3 except `npm install` inside the new `app/` folder.
Part 2 added no new Python dependencies. `requirements.txt` is unchanged and still correct.

## 2. What Part 2 built

```
C:\fractureverse\
  ml\
    __init__.py            ARTIFACTS path and SEED = 1337
    data_gen.py            1500 seeded trajectories, 500 per domain
    feature_extract.py     observation window, field feature set, the one fixed split
    baseline.py            ridge and the closed form Paris integral
    xgboost_model.py       gradient boosted trees plus SHAP
    lstm_model.py          two layer LSTM, 58,497 parameters
    evaluate.py            scoring, per domain breakdown, writes ml_report.json
    train_all.py           trains everything once, saves every weight
    artifacts\             trajectories_*.npz, trajectories_meta.json, split.json,
                           scalers.json, lstm.pt, lstm_history.json, xgb_field.json,
                           shap_summary.json, ml_report.json
  pinn\
    __init__.py  model.py  train.py
    artifacts\             pinn.pt, pinn_history.json, pinn_report.json, pinn_fields.npz
  python_stats\
    __init__.py  style.py  charts.py  generate_all.py  summarize.py
    figures\               chart_01 to chart_17 PNG at 300 dpi, plus captions.json
    cache\                 xfem_propagate_30deg.json, ml_predictions.json
  research\
    part2_validation.json  15 checks, all passing
    ml_report.json         every model, every split, per domain
    stats_summary.json     the single file the paper and Part 3 read
    paper_outline.md       section plan with the figure map
  validate_part2.py
  HANDOFF_part1.md
```

Reproduce with

```bash
python -m ml.train_all              # about 380 s, LSTM is 354 s of that
python -m pinn.train                # about 2230 s on CPU
python -m python_stats.generate_all # about 60 s, chart 4 and chart 13 dominate
python -m python_stats.summarize
python validate_part2.py            # about 12 s, loads weights, never trains
```

`validate_part2.py` is 15 of 15 passing. It loads saved weights and asserts they reproduce
the reported test scores to 1e-9, which is exactly the determinism Part 4 needs.

## 3. Numbers Part 3 will want to display

Machine learning, held out test split of 225 trajectories, target is log10(N_f):

| Model | Test R squared | Test RMSE, decades | Median life ratio error |
|---|---|---|---|
| LSTM | 0.99989 | 0.0277 | 0.046 |
| XGBoost, field features | 0.99976 | 0.0416 | 0.050 |
| Ridge, field features | 0.99984 | 0.0336 | 0.057 |
| Closed form Paris, frozen F | 0.99983 | 0.0350 | 0.018 |

LSTM per domain R squared: aerospace 0.9988, biomedical 0.9994, civil 0.9986.

PINN, 8 layers, 128 neurons, tanh, Xavier, 117,250 parameters, 2000 epochs, 2233 s on CPU
at 1.12 s per epoch, float32:

| Quantity | Value |
|---|---|
| Displacement relative L2 against XFEM | 2.37 percent |
| K_I from the near tip opening fit, PINN | 26.94 MPa sqrt(m) |
| K_I from the same fit applied to the XFEM field | 25.53 MPa sqrt(m) |
| K_I from the XFEM interaction integral | 27.75 MPa sqrt(m) |
| K_I closed form | 27.87 MPa sqrt(m) |
| Final losses | pde 4.6e-3, traction_top 3.6e-6, traction_side 9.8e-5, crack_face 8.4e-3, data 4.7e-4 |

Read all of this from `research/stats_summary.json` rather than retyping it.

## 4. Unit convention, unchanged, do not break this

Everything is SI **except**:

- `K_I`, `K_II`, `K_IC` are in **MPa*sqrt(m)**, never Pa*sqrt(m).
- `paris_C` is scaled so `da/dN` is in **m/cycle** when `delta_K` is in **MPa*sqrt(m)**.

Applied stress is passed in **pascals** at every API boundary and divided by 1e6 internally.
`J` is in J/m^2, `G` is in J/m^2, lengths are in metres. The ML target is `log10(N_f)` in
cycles, so the frontend must take `10 ** prediction` before showing a life.

## 5. Public API for Part 3 and Part 4

Physics, unchanged from Part 1:

```python
from physics.materials import get_material, domain_metadata, list_materials, \
                              keller_modulus, load_reference, use_anchored_paris
from physics.unified_solver import solve, capabilities, SolveRequest, LoadCase, \
                                   CrackConfig, request_from_dict, to_json_safe
```

`capabilities()` returns everything a UI needs to build its selectors in one call.
`solve(SolveRequest(...))` returns a dict. Always call `to_json_safe(result)` before
serialising, it strips the private `_solver`, `_u` and `_damage` handles.

New in Part 2, all of it importable and side effect free at import time:

```python
from ml.feature_extract import prepared, WINDOW      # dataset, fixed split, scalers
from ml.lstm_model import load as load_lstm          # loads ml/artifacts/lstm.pt
from ml.xgboost_model import load as load_xgb
from ml.evaluate import score, load_report
from pinn.train import load as load_pinn             # returns (model, panel)
from python_stats.summarize import build as build_summary
```

`load_lstm(ds)` and `load_xgb(ds)` want the dict from `prepared()`. Both return
`{"name", "model", "pred"}` where `pred` holds train, val and test predictions on the fixed
split. There is **no single sample inference helper yet**. Part 4 will need one for the API,
and the honest way to build it is to reuse `feature_extract._seq_window` and
`feature_extract._static_row` on a fresh `lefm.crack_growth_history` call, then apply the
scalers saved in `ml/artifacts/scalers.json`. Budget half an hour for it, not more.

## 6. Findings that must not be quietly dropped

**6.1 The specified Paris coefficient for 2024-T3 is conservative.** Carried over from Part 1
and still true. `C = 3.6e-10` predicts `1.14e-6 m/cycle` at `delta_K = 10 MPa*sqrt(m)`, about
5.7 times the commonly cited `2.0e-7`. The slope m is correct, only the intercept is high.
`materials.use_anchored_paris(mat)` switches to `paris_C_anchored = 6.32e-11`.
**Part 2 used the specified value everywhere.** `stats_summary.json.domain_lives` reports both
lives per domain, and the anchored aerospace life is 5.70 times the specified one. Figure 1
draws both curves. If Part 3 shows a life number, show which coefficient produced it.

**6.2 Bond based peridynamics ties strength to the horizon.** Effective tensile strength scales
as one over the square root of delta, and Poisson ratio is fixed at 1/3 in 2D plane stress.
The branching panel is 3.0 m by 1.5 m with delta = 0.0905 m, so the horizon implied strength is
6.8 MPa against the 12 MPa applied. Figure 5 puts both numbers in the title. Do not let the
frontend show a peridynamic result without the `pd_strength_MPa` next to `sigma_MPa`.

**6.3 New in Part 2. The surrogate task is close to log linear, so R squared is not the
discriminating metric.** Paris Law is a power law, so log life is nearly linear in the log
features. Ridge regression scores 0.9998 on the test split. Every model clears the 0.92 target
by a wide margin. Two things were done about it rather than hiding it. First, the Paris
coefficients, `a_c` and `a0/a_c` were removed from the feature vector, because with them in
place the target is a closed form function of the inputs and the exercise is arithmetic, not
learning. That removal is asserted by `validate_part2.py` check 7. Second, inspection noise is
added to the observed window, 0.02 decades on crack length and delta K, 0.08 decades on the
growth rate. The honest comparison is RMSE in decades of life, where the LSTM does win, at
0.0277 against 0.0336 for ridge. Say this in the UI copy and in the paper, do not present
0.9999 as an achievement.

**6.4 New in Part 2. The PINN crack opening is about 13 percent low at the crack centre while
the whole field is within 2.4 percent.** The near tip behaviour is good, which is why the
K_I estimate is within 2.9 percent of the XFEM interaction integral, and the same opening
based estimator applied to the XFEM field actually lands further from the interaction integral
than the PINN does. The centre of the opening profile is where the enrichment features carry
the least information. Figure 17 shows the gap directly. Do not crop that panel.

## 7. Sharp edges

Carried from Part 1, all still true:

- `crack_aligned_mesh` forces `ny` odd so a horizontal crack never lands on a mesh line.
- Enrichment is **shifted**, so displacement boundary conditions apply to standard dofs only.
- The interaction integral and the J integral only visit elements where `grad q` is non zero.
- `xfem.propagate` rebuilds the whole solver every step. 12 steps takes about 21 s.
- `peridynamic.PDModel.bond_forces` mutates `self.broken`. Rebuild the model for a fresh run.
- `to_json_safe` drops keys beginning with an underscore.

New from Part 2:

- `lefm.cycles_to_failure` returns a **dict**, not a float. The number is under `N_f`.
  This bit once already.
- `lefm.geometry_factor` raises for out of range `a/W`. Center and through are valid below
  0.5, compact only between 0.2 and 0.8. Guard any slider the UI exposes.
- `feature_extract.get_split` caches to `ml/artifacts/split.json` and only regenerates if the
  trajectory count changes. Deleting that file changes the test set and invalidates every
  reported score. Treat it as a fixture.
- `ml/artifacts/*.npz` are about 1.4 MB each. Do not serve them to the browser.
- `python_stats/cache/` holds the 21 s XFEM propagation and the ML prediction dump. Delete a
  cache file to force a recompute, deleting the whole folder costs about 40 s.
- PINN training is float32 and single run reproducible on this torch build, but torch CPU is
  not bitwise portable across builds. If Part 4 needs an exact PINN number, read it from
  `pinn/artifacts/pinn_report.json` rather than retraining.
- `torch.use_deterministic_algorithms(True)` is set inside `ml.lstm_model.seed_everything`.
  It is process global. If Part 4 imports the LSTM and then runs other torch code, that flag
  is already on.

## 8. Part 3, what to build next

Create `app/`. React with TypeScript, Three.js for the crack viewer, Framer Motion for
transitions. Follow the 12 feature list in the project brief.

Hard constraints from the council answers and from Part 2 measurements:

1. **Never hijack vertical scroll.** Horizontal containers scroll horizontally only.
2. **50,000 individually drawn elements will not hold 30 fps on a Radeon 610M.** Use an
   instanced or merged BufferGeometry with a single draw call, and keep the specified
   automatic fallback to a 30 x 30 x 10 grid when frame time passes 50 ms.
3. The backend is stateless. Every `solve` call builds a fresh solver from a `SolveRequest`,
   so there is no session state for the frontend to corrupt.
4. Build every selector from `capabilities()`. Do not hardcode domain, theory, geometry or
   growth law lists in TypeScript.
5. Figures already exist as 300 dpi PNG in `python_stats/figures` with captions in
   `captions.json`. If the UI shows a chart, prefer serving the PNG over reimplementing the
   plot in JavaScript, and only rebuild a chart in the browser when it needs to be interactive.
6. Anything the UI states as a number should come from `research/stats_summary.json`.

There is no HTTP server yet. Part 4 owns FastAPI. For Part 3 either stub the fetch layer
against a JSON fixture generated from `to_json_safe(solve(...))`, or stand up a throwaway
`uvicorn` script and delete it when Part 4 lands. Do not build half of the Part 4 API in
Part 3 and leave two versions of it.

Then write `HANDOFF.md` for Part 4 in the same shape as this file.
