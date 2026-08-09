# FRACTUREVERSE closing summary, end of Part 4

All four parts are complete. This file replaces the rolling handoff. `HANDOFF_part1.md`,
`HANDOFF_part2.md` and `HANDOFF_part3.md` are kept verbatim for the original physics, model
and frontend detail, but everything still load bearing is carried forward below.

There is no Part 5. The remaining work is listed in section 9 as open items, not as a plan.

---

## 0. Standing instructions from the user

- **Caveman mode stays on for the whole project.** Terse, drop articles and filler, keep every
  technical fact exact. Drop out of caveman only for safety warnings and destructive action
  confirmations. Ponytail is also on: laziest solution that actually works, no speculative
  abstractions, no unrequested features.
- **One single folder** for the whole stack: `C:\fractureverse`.
- **No em dashes anywhere.** Not in code, comments, UI text, README or the exported PDF.
  `validate_part3.py` check 6 and `validate_part4.py` check 8 both enforce this across `.py`,
  `.md`, `.ts`, `.tsx`, `.css` and `.html`, skipping `node_modules`, `dist`, `test-results` and
  generated folders. Both validators build the character with `chr(0x2014)` so the scanner does
  not flag itself. `research/paper.md` is inside the scan, and `make_paper.py` refuses to write
  a manuscript containing one.
- **Horizontal scroll rule, absolute.** Never hijack vertical scroll. `validate_part3.py` check 7
  and `validate_part4.py` check 9 grep the frontend for `onWheel`, wheel listeners, `scrollTo`,
  `scrollIntoView` and `preventDefault`. Playwright suite 01 asserts it in a real browser as well,
  by measuring document overflow and by wrapping `addEventListener`.

## 1. Environment, verified again this session

| Item | Value |
|---|---|
| OS | Windows 11 Home, PowerShell, Bash also available |
| Python | 3.11.15 |
| Node / npm | v24.18.0 / 11.16.0 |
| GPU | AMD Radeon 610M integrated, torch is the CPU build |
| New in Part 4 | fastapi 0.139.0, uvicorn 0.51.0, pydantic 2.13.4, reportlab 5.0.0, httpx 0.28.1, @playwright/test 1.62.1 with the chromium build |

`requirements.txt` already pinned the four backend packages, nothing was added to it. `httpx`
was present and is what `fastapi.testclient.TestClient` uses. Starlette prints a deprecation
warning asking for `httpx2`, which is noise, not a failure.

## 2. What Part 4 built

```
C:\fractureverse\
  api\
    __init__.py
    main.py                FastAPI service. Health, capabilities, solve, predict,
                           figures, report, static fixture passthrough, dist mount
  ml\
    infer.py               single sample inference. The helper Parts 1 to 3 never had
  make_paper.py            research/paper.md and research/fractureverse.pdf
  validate_part4.py        13 checks, all passing
  research\
    paper.md               generated manuscript, 12,803 characters
    fractureverse.pdf      same manuscript, 17 figures embedded, 4.7 MB
    part4_validation.json
  app\
    playwright.config.ts   one server, uvicorn on 8000 serving app/dist at the root
    tests\
      helpers.ts           boot, open, expectNoBodyOverflow
      01-shell.spec.ts     6 tests, sidebar, both data modes, the scroll rule
      02-overview.spec.ts  4 tests, headline counts, both Paris lives, four findings
      03-theories.spec.ts  3 tests, theory cards and the geometry table
      04-playground.spec.ts 8 tests, live solve, guards, epfm, predict, offline
      05-viewer.spec.ts    4 tests, canvas, 50,000 instances, fallback resolution
      06-physics.spec.ts   5 tests, xfem path, per domain solves, peridynamic field
      07-models.spec.ts    7 tests, leaderboard, splits, SHAP, parity, PINN
      08-figures.spec.ts   4 tests, gallery, lightbox, PNG load, validation log
      09-api.spec.ts       9 tests, the backend contract end to end
  HANDOFF_part3.md
```

Changed, not new: `app/src/data.ts` grew the mode probe and the `apiSolve` and `apiPredict`
calls, `app/src/ui.tsx` grew `useMode` and a skippable `useFixture`, `app/src/App.tsx` shows the
mode in the sidebar, `app/src/Playground.tsx` gained the live path, `app/vite.config.ts` proxies
`/api`, `README.md` was refreshed.

Run the whole stack:

```bash
python -m uvicorn api.main:app --port 8000
```

http://127.0.0.1:8000 is then the entire application on one origin, API under `/api` and the
production bundle from `app/dist` at the root. Frontend development is still

```bash
npm run dev --prefix app -- --port 5178 --strictPort
```

which proxies `/api` to port 8000 and falls into offline mode if nothing is listening.

Reproduce Part 4:

```bash
python make_paper.py
npm run build --prefix app
python validate_part4.py
```

About three minutes, almost all of it the vite build and the browser suite. `validate_part4.py`
runs checks 1 to 11 in process with `TestClient`, then starts a real uvicorn for Playwright.

## 3. Decisions Part 4 made, and why

**3.1 Two modes, both named on screen.** The Part 3 handoff said not to keep two sources of
truth silently. The app probes `GET /api/health` once, caches the answer, and the sidebar and
the playground both say which mode is running. In live mode `sweep.json` and `curves.json` are
never fetched, and `/api/data/sweep.json` returns 404 with a hint pointing at `/api/solve`. In
offline mode the 1.9 MB grid answers and the badge says so. The grid was kept rather than
deleted because the frontend has to work with no Python running, which is how it is graded.

**3.2 The mode probe settles before any data hook runs.** `Playground` resolves `useMode` and
then renders `PlaygroundBody`. Without that split, the first render would be offline by default
and would fire the 1.9 MB grid fetch that live mode does not want.

**3.3 The elastic plastic solve is a second call.** `solve` with `theory="epfm"` returns J, the
J-R curve, CTOD and the instability point, and no `N_f`, no `history` and no `plastic_zone`,
because a life needs the Paris integration that lives in the linear elastic path. The Part 3
sweep records merged both for the same point. The live playground does the same with two
requests and one object spread. A single `theory="epfm"` request would blank the whole result
panel, which is exactly the crash the first Playwright run caught.

**3.4 Slow theories are refused, not queued.** `xfem` and `peridynamic` are in `SLOW_THEORIES`
and return 413 with a hint unless the body carries `allow_slow: true`. No job queue was built.
The frontend never asks for them, the precomputed `xfem.json` and `peridynamic.json` fixtures
still drive those two views, and Playwright suite 06 asserts that opening either view issues
zero `/api/solve` calls. A single `xfem` solve with `allow_slow` does complete in a few seconds,
`xfem.propagate` at 12 steps is the 21 s path and is not exposed at all.

**3.5 Endpoints are `def`, not `async def`.** FastAPI then runs them in the threadpool, so a
blocking numpy or torch call does not stall the event loop. This is the whole of the concurrency
story and it is enough for one user on one machine.

**3.6 `/api/solve` thins the growth history to 40 points.** The solver returns 400. The chart
draws 40, the fixture stored 40, and the query parameter `history_points` takes 0 for the full
array or anything up to 400.

**3.7 `ml/infer.py` rebuilds the training pipeline rather than reimplementing it.** It calls
`lefm.crack_growth_history` at `n_points=200`, which is what `ml/data_gen.py` used, then
`feature_extract._seq_window` and `_static_row`, then the train fitted scalers from
`ml/artifacts/scalers.json`, then the saved LSTM. Inspection noise is deliberately not applied:
training added it so the task was not log linear, a live caller is handing over their own
measurement. On each domain anchor case the life ratio error is 0.021 aerospace, 0.024
biomedical, 0.099 civil, consistent with the reported 0.046 median on the test split.

**3.8 The paper is generated, not written.** `make_paper.py` reads `stats_summary.json`,
`ml_report.json`, `part1_validation.json`, `pinn_report.json`, `anchored.json` and
`figures.json`, follows the section plan in `research/paper_outline.md`, and emits markdown and
a PDF with the 17 figures embedded. No number is retyped, which is the same rule the frontend
follows. Regenerating after a retrain updates every table.

## 3b. The design system, added after Part 4 shipped

**Type, three families.** Playfair Display carries the wordmark, `h1`, `h2`, the note titles
and **every number in the application, always italic**. That rule lives in one selector block
at the top of `index.css` and covers `.stat .v`, `td.num`, `.val`, the sidebar numerals, the
figure card titles and the recharts tick labels, plus a `.fig` class for numbers inside running
text. Space Grotesk is the reading face. JetBrains Mono is only for identifiers a reader might
retype, which is the `.mono` class.

**Colour, three gradients and no more.** Warm ink base, `#0b0c0f` through `#1a1d25`, warm off
white text at `#ece8e1`. The three are jade `#7fd1c0` to `#2f8f8a`, ember `#e8b04b` to
`#c96a3f`, indigo `#9aa4ff` to `#5560d6`. They share a value and step in temperature, and each
one means something fixed: jade is the app accent and aerospace is indigo, biomedical jade,
civil ember in every chart. `--good`, `--warn`, `--bad` and `--accent` are aliases onto those
three so no component can introduce a fourth. Chart series, the peridynamic damage map and the
3D viewer were all recoloured onto the same ramp.

**Favicon.** `app/public/favicon.svg` was the stock bolt shipped with the template. It is now a
plate with a branching crack drawn on the jade to ember gradient, which is the one image the
whole project is about.

**Where each of the three is used.** Jade is the app accent, the sidebar rail, the wordmark
and the 3D viewer cells. Indigo carries the honesty notes, the peridynamic damage map ramp and
the aerospace series. Ember is reserved for warnings, the small scale yielding badge and the
civil series, so a warm colour on screen always means read this one more carefully.

**Landing view.** The Overview header is a banner: eyebrow, wordmark, a serif claim line and
four gradient pills built from the same fixtures the stats below use. `Section` grows an
optional `hero` prop for it, and only that one view passes it, so the other eleven keep the
plain title.

**Validation log.** Part 1 writes its check detail as a JSON blob truncated at 400 characters,
which rendered raw was a wall of quotes. `DetailCell` in `App.tsx` splits it into labelled
pairs, rounds numbers to six significant figures, gives long prose values a full width row and
says how many fields were left in `research/part1_validation.json`. Each part also carries a
paragraph naming what its validator actually measures and against what.

**One thing that did not work.** Per instance colour in the 3D viewer. three only declares the
instancing colour attribute when `instanceColor` exists at material compile time, and under
react-three-fiber the material here compiles first, so every cell rendered black. Pre allocating
the attribute and forcing a recompile did not change it. A mesh per damage band would fix the
colour and cost the single draw call the whole view exists to demonstrate, so the cells are one
jade and the threshold slider is what reads damage magnitude. The comment in `Viewer3D.tsx`
says exactly this, and the 2D peridynamic map still carries the full ramp.

## 4. Numbers the stack reports, all read from disk

| Model, test split of 225 | R squared | RMSE, decades | Median life ratio error |
|---|---|---|---|
| LSTM | 0.99989 | 0.0277 | 0.046 |
| XGBoost, field features | 0.99976 | 0.0416 | 0.050 |
| Ridge, field features | 0.99984 | 0.0336 | 0.057 |
| Closed form Paris | 0.99983 | 0.0350 | 0.018 |

PINN: displacement relative L2 2.37 percent, K_I 26.94 from the PINN opening fit against 27.75
from the XFEM interaction integral and 27.87 closed form, 117,250 parameters, 2233 s on CPU.

Aerospace anchor case, 2024-T3, 150 MPa, R 0.1, a0 1 mm, center cracked, W 100 mm:
N_f 2671.5 cycles specified, 15217.5 anchored, ratio 5.70, a_c 16.05 mm. `/api/solve` returns
2671.5099717 for that request, bitwise equal to a direct `solve()` call, asserted by check 3.
`/api/predict` returns 2614.5 cycles for the same crack from the first 20 samples alone.

Validation totals: Part 1 14 of 14, Part 2 15 of 15, Part 3 13 of 13, Part 4 13 of 13.
Playwright: 50 of 50 across 9 suites.

## 5. Unit convention, unchanged, do not break this

SI everywhere except `K_I`, `K_II`, `K_IC` in MPa sqrt(m) and `paris_C` scaled so `da/dN` is in
m per cycle for `delta_K` in MPa sqrt(m). Applied stress crosses every API boundary in pascals,
including the JSON bodies of `/api/solve` and `/api/predict`. The ML target is `log10(N_f)`, so
anything showing a life calls `10 ** prediction` first. `/api/predict` already does that and
returns both `log10_N_f` and `N_f_predicted`. The frontend `fromLogLife` in `data.ts` is still
used in the two places that read the raw parity fixture.

## 6. Public API

Python, unchanged:

```python
from physics.unified_solver import solve, capabilities, SolveRequest, LoadCase, \
                                   CrackConfig, request_from_dict, to_json_safe
from ml.feature_extract import prepared, WINDOW
from ml.infer import predict, features          # new in Part 4
from ml.lstm_model import load as load_lstm
from ml.xgboost_model import load as load_xgb
from ml.evaluate import score, load_report
from pinn.train import load as load_pinn
```

HTTP:

| Endpoint | Notes |
|---|---|
| `GET /api/health` | `{ok, service, part, live_solver, figures}`, the mode probe |
| `GET /api/capabilities` | byte identical to `capabilities()`, check 2 asserts it |
| `POST /api/solve` | `?history_points=40` by default, 0 for all 400. 422 out of range, 413 slow |
| `POST /api/predict` | one crack through the LSTM, with the closed form life beside it |
| `GET /api/figures` | the 17 captions. `/api/figures/{name}` serves the PNG |
| `GET /api/report` | the PDF, `?fmt=markdown` for the source |
| `GET /api/data/{name}` | the nine precomputed artifacts. `sweep.json` is 404 by design |

## 7. Sharp edges

Carried forward, all still true:

- `lefm.cycles_to_failure` returns a dict. The number is under `N_f`.
- `lefm.geometry_factor` raises for out of range `a/W`. Center and through below 0.5, compact
  between 0.2 and 0.8. `/api/solve` turns that into a 422 with the bounds in the hint.
- `feature_extract.get_split` caches to `ml/artifacts/split.json`. Deleting it changes the test
  set and invalidates every reported score. Fixture, not cache.
- `ml/artifacts/*.npz` are about 1.4 MB each, do not serve them to the browser.
- `python_stats/cache/` holds the 21 s XFEM propagation and the ML prediction dump.
- `torch.use_deterministic_algorithms(True)` is process global, set inside
  `ml.lstm_model.seed_everything`.
- PINN numbers come from `pinn/artifacts/pinn_report.json`, torch CPU is not bitwise portable.
- `xfem.propagate` rebuilds the solver every step, 12 steps is about 21 s. It is not exposed.
- A `peridynamic` solve is about 24 s and must not sit behind a synchronous request handler.
  It is refused unless `allow_slow` is set.
- Vite serves `app/public` at the site root, so fixtures live at `/data/*.json` and figures at
  `/figures/*.png`. `import.meta.env.BASE_URL` is used everywhere, so a subpath deploy works.
- The vite bundle is 1.65 MB, 462 kB gzipped, mostly three and recharts.
- `.claude/launch.json` at the repo root defines the dev server on port 5178.

New in Part 4:

- `ml/infer.py` caches the model and the scalers with `lru_cache`, so the first `/api/predict`
  pays the torch load and the rest are milliseconds. Retraining in the same process will keep
  serving the old weights until it restarts.
- `N_POINTS = 200` in `ml/infer.py` must match `ml/data_gen.py`. The 20 sample window is the
  first tenth of a 200 point geometric sweep in crack length. Change one and the features shift
  under the scalers with no error raised.
- `/api/predict` is only meaningful near its training distribution. Asking about cortical bone
  at 150 MPa on a 100 mm panel returns a number, and that number is nonsense. `validate_part4.py`
  check 5 uses each domain's own anchor case for this reason.
- `app/dist` is mounted at `/` only if it exists. Start uvicorn before `npm run build` and the
  API works while the root 404s until the next restart.
- Playwright reuses an existing server on port 8000. If a stale uvicorn is running against an old
  `dist`, the suite tests the old bundle. Restart it after a rebuild.
- `research/fractureverse.pdf` is 4.7 MB because the 17 figures are 300 dpi PNG. It is not
  committed to any size budget, but it is not something to serve to every visitor either.

## 8. What each validator covers

| File | Checks | Time | Runs npm |
|---|---|---|---|
| `validate_part1.py` | 14, physics against independent targets | about 80 s | no |
| `validate_part2.py` | 15, saved weights reproduce reported scores to 1e-9 | seconds | no |
| `validate_part3.py` | 13, fixtures, frontend rules, production build | about 30 s | yes |
| `validate_part4.py` | 13, endpoints, guards, inference, paper, browser suite | about 3 min | yes |

Part 4 check 13 reads the three earlier reports rather than rerunning them. Parts 1 and 2 store
their check lists inside `app/public/data/validation.json`, Part 3 writes
`research/part3_validation.json` in its own shape.

## 8b. Where it is published

| What | Where |
|---|---|
| Source | https://github.com/kanav7810-oss/fractureverse |
| Hosted frontend | https://fractureverse.vercel.app |

The Vercel build is the frontend only. `vercel.json` runs `npm run build --prefix app` and
serves `app/dist`, and `.vercelignore` keeps the Python tree out of the deployment, with every
pattern anchored by a leading slash. Without the anchor, `data/` also matches
`app/public/data` and the hosted app ships with no fixtures, which is exactly what the first
successful deploy did. Torch, XGBoost and SHAP do not fit in a serverless function, so the
hosted build runs in offline mode and names that state in the sidebar. Start uvicorn locally
and the same bundle switches to live solves with no rebuild.

## 9. Open items, honestly stated

None of these block anything. They are what a fifth part would pick up.

1. **No background job path.** XFEM propagation and peridynamics are refused rather than queued.
   A real deployment would return a job id and poll. The refusal is a 413 with a hint, which is
   honest but is not a feature.
2. **The bundle is one 1.65 MB chunk.** Code splitting three and recharts would cut first paint
   substantially. It was not worth the complexity at this size.
3. **The offline grid still exists.** Two paths through the playground means two things to keep
   correct. They are both tested, and the mode is on screen, but one path would be simpler.
4. **`/api/predict` has no input domain guard.** It answers anywhere, including far outside the
   training distribution, and only the note in the response says so. A distance to training set
   warning would be the honest addition.
5. **The paper has no bibliography section.** The sources are named inline in section 3 and in
   the material database, and `paper_outline.md` lists them, but nothing renders a reference
   list.
6. **Single user concurrency.** Threadpool endpoints and a process global torch determinism flag
   are fine for one machine and not for a shared service.
