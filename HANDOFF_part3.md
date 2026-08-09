# FRACTUREVERSE handoff, end of Part 3

Read this file first. It is the only context the next session needs. `HANDOFF_part1.md` and
`HANDOFF_part2.md` are kept verbatim if you want the original physics or model detail, but
everything still load bearing is carried forward below.

---

## 0. Standing instructions from the user

- **Caveman mode stays on for the whole project.** Terse, drop articles and filler, keep every
  technical fact exact. Drop out of caveman only for safety warnings and destructive action
  confirmations. Ponytail is also on: laziest solution that actually works, no speculative
  abstractions, no unrequested features.
- **One single folder** for the whole stack: `C:\fractureverse`.
- **No em dashes anywhere.** Not in code, comments, UI text, README, or the exported PDF.
  `validate_part3.py` check 6 enforces this across `.py`, `.md`, `.ts`, `.tsx`, `.css` and
  `.html`, skipping `node_modules`, `dist` and generated folders. Both validators now build the
  character with `chr(0x2014)` so the scanner does not flag itself.
- **Horizontal scroll rule, absolute.** Never hijack vertical scroll. `validate_part3.py`
  check 7 greps the frontend for `onWheel`, wheel listeners, `scrollTo`, `scrollIntoView` and
  `preventDefault` and fails if any appears.
- Build order is fixed: Part 1, then 2, then 3, then 4.

## 1. Environment, verified again this session

| Item | Value |
|---|---|
| OS | Windows 11 Home, PowerShell, Bash also available |
| Python | 3.11.15 |
| Node / npm | v24.18.0 / 11.16.0 |
| GPU | AMD Radeon 610M integrated, torch is the CPU build |
| New in Part 3 | react 19.2.8, typescript 6.0.2, vite 8.2.1, three 0.185.1, @react-three/fiber 9.7.0, @react-three/drei, framer-motion 13.0.0, recharts |

No new Python dependency. `requirements.txt` unchanged. `app/node_modules` is installed.

## 2. What Part 3 built

```
C:\fractureverse\
  app\
    gen_fixtures.py        builds every JSON the frontend reads, run from the repo root
    index.html             title FRACTUREVERSE
    src\
      main.tsx             untouched vite entry
      index.css            the whole theme, one file
      data.ts              fetch layer, cache, types, fmt and fromLogLife helpers
      ui.tsx               useFixture, Section, Stat, Note, Select, Slider, chart constants
      App.tsx              sidebar, the 12 feature registry, Overview, Theories, Figures, Validation
      Playground.tsx       features 3 and 4
      Viewer3D.tsx         feature 5
      Physics.tsx          features 6 and 7
      Models.tsx           features 8 to 11
    public\data\           capabilities, stats_summary, sweep, curves, anchored, xfem,
                           peridynamic, ml, pinn, figures, validation
    public\figures\        the 17 PNG copied from python_stats
    dist\                  production build, 1.65 MB js, 462 kB gzipped
  validate_part3.py        13 checks, all passing
  research\part3_validation.json
  HANDOFF_part2.md
```

The 12 features, in sidebar order:

1. Overview, domain impact numbers, both Paris lives, the four honesty notes
2. Theory explorer, blurbs and per domain availability, geometry table
3. Solver playground, every selector from `capabilities()`
4. Crack growth history plus the anchored versus specified Paris table
5. Volumetric crack viewer, Three.js
6. XFEM crack path, propagation and per domain single step solves
7. Peridynamic damage map, branching and the fracture energy check
8. Model leaderboard, split switch, per domain LSTM, training history
9. Feature attribution, SHAP bars, the dropped leaky features
10. Parity explorer, 225 test trajectories coloured by domain
11. PINN against XFEM, opening profile and the five loss curves
12. Figure gallery, 17 PNG with captions and a lightbox, plus the validation log

Reproduce with

```bash
python app/gen_fixtures.py
npm install --prefix app
npm run build --prefix app
python validate_part3.py
```

`gen_fixtures.py` takes about 60 s, almost all of it the one peridynamic solve.
`validate_part3.py` takes about 30 s and runs `npm run build` as its last check.

Dev server:

```bash
npm run dev --prefix app -- --port 5178 --strictPort
```

## 3. Decisions Part 4 inherits

**3.1 The frontend reads static fixtures, not an API.** `app/src/data.ts` has one function,
`loadJson(name)`, which fetches `public/data/<name>` and caches the promise. Part 4 replaces the
body of that function and nothing else. No component calls `fetch` directly.

**3.2 The solver grid is precomputed.** `sweep.json` is 4050 records, LEFM and EPFM over
6 materials by 6 geometries by 9 stresses from 40 to 260 MPa by 5 initial crack lengths from 0.5
to 8 mm by 3 growth laws. Records are keyed
`domain|material|geometry|law|sigma_MPa|a0_mm`. Combinations that `geometry_factor` rejects are
absent rather than extrapolated, which is why the count is 4050 and not 4860. When the live
`/solve` endpoint lands, the playground should call it and the grid becomes a fallback or is
deleted. Do not keep two sources of truth for the same number.

**3.3 `curves.json` only holds center plus paris growth histories**, 270 of them, downsampled to
40 points. Any other combination shows a line of copy saying so instead of an invented curve.

**3.4 Numbers are copied, never retyped.** `stats_summary.json` is byte identical to
`research/stats_summary.json`, asserted by check 5. `capabilities.json` is byte identical to
`capabilities()`, asserted by check 3.

**3.5 Framer Motion `AnimatePresence` is not used for the feature swap.** Under React 19 strict
mode the outgoing view was stranded and the incoming one never mounted. Every transition is now
a keyed `motion.div` with `initial` and `animate` only. If Part 4 adds exit animations, test the
nav switch, this bit once already.

**3.6 The 3D viewer is one `instancedMesh`.** Default 50 by 50 by 20, which is 50,000 cells in a
single draw call. Cells below the damage threshold are scaled to 1e-4 rather than removed, so
the instance count and the draw call never change. A `useFrame` watchdog counts frames over
50 ms and drops to 30 by 30 by 10 after 20 of them, and the HUD says when that happened. The
field is the Part 1 peridynamic damage field extruded through the thickness. It is a damage
field, not a stress field, and the copy says so.

## 4. Numbers the UI displays, all read from disk

Unchanged from Part 2 and repeated here only so Part 4 can assert them.

| Model, test split of 225 | R squared | RMSE, decades | Median life ratio error |
|---|---|---|---|
| LSTM | 0.99989 | 0.0277 | 0.046 |
| XGBoost, field features | 0.99976 | 0.0416 | 0.050 |
| Ridge, field features | 0.99984 | 0.0336 | 0.057 |
| Closed form Paris | 0.99983 | 0.0350 | 0.018 |

PINN: displacement relative L2 2.37 percent, K_I 26.94 from the PINN opening fit against 27.75
from the XFEM interaction integral and 27.87 closed form, 117,250 parameters, 2233 s on CPU.

Aerospace anchor case, 2024-T3, 150 MPa, R 0.1, a0 1 mm, center cracked, W 100 mm:
N_f 2671.5 cycles specified, 15217.5 anchored, ratio 5.70, a_c 16.05 mm.

## 5. Unit convention, unchanged, do not break this

SI everywhere except `K_I`, `K_II`, `K_IC` in MPa sqrt(m) and `paris_C` scaled so `da/dN` is in
m per cycle for `delta_K` in MPa sqrt(m). Applied stress crosses every API boundary in pascals.
The ML target is `log10(N_f)`, so anything showing a life calls `10 ** prediction` first. The
frontend has `fromLogLife` in `data.ts` for exactly this and uses it in two places.

## 6. Public API, what Part 4 wraps

```python
from physics.unified_solver import solve, capabilities, SolveRequest, LoadCase, \
                                   CrackConfig, request_from_dict, to_json_safe
from ml.feature_extract import prepared, WINDOW
from ml.lstm_model import load as load_lstm
from ml.xgboost_model import load as load_xgb
from ml.evaluate import score, load_report
from pinn.train import load as load_pinn
```

`request_from_dict` is the natural body parser for a FastAPI `/solve`. Always
`to_json_safe(result)` before serialising, it strips `_solver`, `_u` and `_damage`.

There is still **no single sample inference helper**. Part 4 needs one for `/predict`, and the
honest way is still to reuse `feature_extract._seq_window` and `feature_extract._static_row` on
a fresh `lefm.crack_growth_history` call, then apply `ml/artifacts/scalers.json`. Half an hour.

## 7. Sharp edges

Carried forward, all still true:

- `lefm.cycles_to_failure` returns a dict. The number is under `N_f`.
- `lefm.geometry_factor` raises for out of range `a/W`. Center and through below 0.5, compact
  between 0.2 and 0.8. Guard any slider or request body.
- `feature_extract.get_split` caches to `ml/artifacts/split.json`. Deleting it changes the test
  set and invalidates every reported score. Fixture, not cache.
- `ml/artifacts/*.npz` are about 1.4 MB each, do not serve them to the browser.
- `python_stats/cache/` holds the 21 s XFEM propagation and the ML prediction dump.
- `torch.use_deterministic_algorithms(True)` is process global, set inside
  `ml.lstm_model.seed_everything`.
- PINN numbers come from `pinn/artifacts/pinn_report.json`, torch CPU is not bitwise portable.
- `xfem.propagate` rebuilds the solver every step, 12 steps is about 21 s. A live XFEM endpoint
  will time out a browser default if it propagates, so return a job id or cap the steps.
- `peridynamic` solve is about 24 s. It must not sit behind a synchronous request handler.

New in Part 3:

- Vite serves `app/public` at the site root, so fixtures live at `/data/*.json` and figures at
  `/figures/*.png`. `import.meta.env.BASE_URL` is used everywhere, so a subpath deploy works.
- `sweep.json` is 1.9 MB uncompressed. It is fetched lazily, only when the playground opens.
  Serve the app with compression in Part 4 or replace the grid with the live endpoint.
- The vite bundle is 1.65 MB, 462 kB gzipped, mostly three and recharts. Code splitting is
  available if Part 4 cares, it was not worth the complexity here.
- `.claude/launch.json` at the repo root defines the dev server on port 5178.

## 8. Part 4, what to build next

1. **FastAPI backend.** `/capabilities`, `/solve`, `/predict`, `/figures`, `/report`. Wrap the
   functions in section 6. Keep it stateless, every `solve` builds a fresh solver. Long theories,
   XFEM propagation and peridynamics, need either a step cap or a background job, see section 7.
2. **Point the frontend at it.** Change the body of `loadJson` in `app/src/data.ts` and give the
   playground a live `/solve` call. Delete `sweep.json` and the grid path once the live call
   works, or keep the grid as an explicit offline mode. Not both silently.
3. **30 Playwright tests across 9 suites.** The 12 features are the natural suite boundaries.
   Assert the horizontal scroll rule, the instanced viewer fallback, and that the four honesty
   findings are on screen, since `validate_part3.py` only checks they are in the source.
4. **Final validation.** A `validate_part4.py` in the same shape, and a README refresh.
5. **The paper.** `research/paper_outline.md` has the section plan and the figure map. The
   exported PDF must contain no em dashes.

Then write the final handoff or the closing summary in the same shape as this file.
