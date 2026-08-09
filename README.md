# FRACTUREVERSE

A multi physics fracture propagation digital twin for structural failure prediction across
aerospace aluminium alloys, orthopaedic bone implants and reinforced concrete bridge decks.
Four fracture theories, three engineering domains, one platform.

Status: **complete, all four parts.** Physics and data foundation validated, 14 of 14 checks
passing. Surrogate models, the physics informed network and the 17 publication figures are in
place, 15 of 15 Part 2 checks passing. The React TypeScript frontend with its 12 features is
built, 13 of 13 Part 3 checks passing. The FastAPI backend serves live solves and single sample
life predictions, 50 Playwright tests across 9 suites pass against the production bundle, and
the paper exports to PDF, 13 of 13 Part 4 checks passing.

---

## The four theories

| Theory | What it is | Where it is strongest here |
|---|---|---|
| LEFM | Stress intensity factor, Paris and Walker crack growth, cycles to failure | Aerospace fatigue, where small scale yielding holds |
| EPFM | Domain J integral, J-R tearing resistance, CTOD | Ductile aluminium tearing, bone at high loading rate |
| XFEM | Enriched finite elements, cracks cut through the mesh | Arbitrary crack paths, mixed mode kinking, stress fields for the PINN |
| Peridynamics | Bonds between material points break on their own | Quasi brittle concrete, crack nucleation and branching with no predefined path |

## The three domains

| Domain | Material | Duty cycle | Real world anchor |
|---|---|---|---|
| Aerospace | 2024-T3 and 7075-T6 aluminium | 500 pressurisation cycles per year | Fatigue causes about 20 percent of commercial airframe structural failures |
| Biomedical | Cortical bone, healthy and osteoporotic | 1.5 million gait cycles per year | 400,000 hip and knee replacements per year in the United States, revision costs 15,000 to 50,000 USD |
| Civil | Reinforced concrete deck, A615 rebar | 5 million truck axle crossings per year | About 42,000 of 617,000 United States bridges are structurally deficient |

---

## Layout

```
fractureverse/
  data/                  three domain material databases plus reference validation data
    aerospace/           2024-T3 and 7075-T6, Paris coefficients, K_IC temperature curve
    biomedical/          cortical bone properties, Keller density law, hip gait spectrum
    civil/               concrete and rebar, chloride corrosion model, NBI rating scale
    reference_charts/    anchored da/dN bands and handbook geometry check points
  physics/
    materials.py         SI material loader, Material dataclass, Keller modulus law
    mesh.py              structured Q4 mesh, crack aligned and tip refined variants
    lefm.py              K_I, geometry factors, Paris, Walker, Forman, a_c, N_f
    epfm.py              domain J integral, J-R curve, CTOD, tearing instability
    xfem.py              Heaviside and branch enrichment, interaction integral, propagation
    peridynamic.py       bond based model, bond breaking, damage field, m convergence
    unified_solver.py    routes (domain, material, theory) to an implementation
  ml/
    data_gen.py          1500 seeded crack growth trajectories, 500 per domain
    feature_extract.py   observation window, field feature set, the one fixed split
    baseline.py          ridge and the closed form Paris integral
    xgboost_model.py     gradient boosted trees plus SHAP attribution
    lstm_model.py        two layer LSTM over the observation window
    evaluate.py          scoring, per domain breakdown, ml_report.json
    train_all.py         train everything once, save every weight
    artifacts/           trajectories, split.json, lstm.pt, xgb_field.json, scalers
  pinn/
    model.py             8 x 128 tanh network, branch enriched inputs, five losses
    train.py             NTK style gradient norm weighting, CPU training loop
    artifacts/           pinn.pt, loss history, field comparison against XFEM
  python_stats/
    style.py             one figure style, 300 dpi, 12 pt axis labels
    charts.py            the 17 figures
    generate_all.py      regenerate all or a subset
    summarize.py         builds research/stats_summary.json
    figures/             chart_01 to chart_17 PNG plus captions.json
  research/
    part1_validation.json          full machine readable validation report
    part1_peridynamic_damage.npy   damage field from the branching run
    part2_validation.json          the 15 Part 2 acceptance checks
    ml_report.json                 every model, every split, per domain
    stats_summary.json             the single file the paper and Part 3 read
    paper_outline.md               section plan with the figure map
    paper.md                       the generated manuscript, every number read from disk
    fractureverse.pdf              the same manuscript with the 17 figures embedded
  api/
    main.py              FastAPI service, capabilities, solve, predict, figures, report
  app/
    gen_fixtures.py      builds every JSON the frontend reads, from the solver and the artifacts
    src/                 data.ts fetch layer, ui.tsx primitives, App.tsx and four feature files
    public/data/         capabilities, sweep, curves, ml, pinn, peridynamic, xfem, validation
    public/figures/      the 17 PNG copied from python_stats
    tests/               nine Playwright suites, 50 tests, run against the production bundle
    playwright.config.ts one server, uvicorn serving app/dist at the site root
  make_paper.py          builds research/paper.md and research/fractureverse.pdf
  validate_part1.py      the 14 Part 1 acceptance checks
  validate_part2.py      the 15 Part 2 acceptance checks
  validate_part3.py      the 13 Part 3 acceptance checks
  validate_part4.py      the 13 Part 4 acceptance checks
  HANDOFF.md             state, decisions and open items for the next build part
  requirements.txt
```

## Run the validation

```bash
python validate_part1.py
```

About 80 seconds. Writes `research/part1_validation.json`.

Part 2 reproduces with

```bash
python -m ml.train_all
python -m pinn.train
python -m python_stats.generate_all
python -m python_stats.summarize
python validate_part2.py
```

`validate_part2.py` loads saved weights rather than training, so it runs in seconds and is
what Part 4 should key its determinism on.

Part 3 reproduces with

```bash
python app/gen_fixtures.py
npm install --prefix app
npm run build --prefix app
python validate_part3.py
```

Part 4 reproduces with

```bash
python make_paper.py
npm run build --prefix app
python validate_part4.py
```

About three minutes, almost all of it the build and the browser suite.

## Run the stack

```bash
python -m uvicorn api.main:app --port 8000
```

That serves the API under `/api` and the production bundle from `app/dist` at the site root,
so http://127.0.0.1:8000 is the whole application on one origin. For frontend development run
`npm run dev --prefix app -- --port 5178 --strictPort` in a second terminal, which proxies
`/api` to port 8000.

Without a backend the frontend still runs, on the precomputed fixtures. It says so in the
sidebar and on the playground rather than falling back silently, and in that mode the solver
grid answers instead of a live solve.

| Endpoint | What it does |
|---|---|
| `GET /api/health` | liveness, and whether the live solver is available |
| `GET /api/capabilities` | the solver capability map, byte identical to `capabilities()` |
| `POST /api/solve` | one fresh solve, growth history included, slow theories behind `allow_slow` |
| `POST /api/predict` | one sample through the trained LSTM, against the closed form life |
| `GET /api/figures` | the 17 captions, and `/api/figures/{name}` for the PNG |
| `GET /api/report` | the paper as PDF, or `?fmt=markdown` |
| `GET /api/data/{name}` | the precomputed Part 1 and Part 2 artifacts |

## Use the solver

```python
from physics.unified_solver import solve, SolveRequest, LoadCase, CrackConfig

r = solve(SolveRequest(
    domain="aerospace", theory="lefm",
    load=LoadCase(sigma_max=150e6, R=0.1),
    crack=CrackConfig(a0=1e-3, W=0.1, geometry="center")))

print(r["K_I"], r["a_c"], r["N_f"], r["years_to_failure"])
```

## Unit convention

Everything is SI except two quantities that the fracture literature never writes in SI.
Stress intensity factors and fracture toughness are in MPa*sqrt(m), and the Paris coefficient
C is scaled so that da/dN comes out in m/cycle when delta_K is supplied in MPa*sqrt(m). Applied
stress is passed in pascals at every API boundary and converted internally.

## Validation results, Part 1

| Check | Result |
|---|---|
| XFEM K_I versus the analytical centre cracked panel | 0.43 to 0.48 percent error at a/b of 0.3, 0.4 and 0.5 |
| XFEM interaction integral domain independence | spread under 0.1 percent of K_I over r_d from 2 to 5 elements |
| LEFM life integrator versus the closed form Paris integral | 2.6e-12 percent |
| LEFM Paris slope versus the reference bands | slope matches to better than 0.05 on all four series |
| EPFM domain J integral versus K_I squared over E prime | 1.59 percent |
| Peridynamic fracture energy calibration | continuum identity exact, discrete error 9.2 percent at delta/dx of 6 |
| Peridynamic crack branching, concrete panel | confirmed, first branch 45 mm past the notch tip, reproduced at delta/dx of 2, 3 and 4 |
| Peridynamic m convergence | damage profile L2 error 0.55, 0.11, 0.00 as delta/dx goes 2, 3, 4 |

Two honesty notes are carried in the data and the report rather than buried. The specified
Paris coefficient for 2024-T3 sits about 5.7 times above the commonly cited mid range growth
rate at the same slope, so predicted lives are conservative, and an anchored alternative is
shipped alongside it. Bond based peridynamics ties tensile strength to the horizon, so the
concrete panel is sized on the Hillerborg characteristic length and the driving stress is
reported next to the horizon implied strength.

## Roadmap

- **Part 1, complete.** Physics and data foundation, four theories validated.
- **Part 2, complete.** 1500 seeded trajectories, LSTM and XGBoost prognostics against a ridge
  and a closed form Paris baseline, a PINN with five physics loss terms and NTK style adaptive
  weighting, 17 charts at 300 dpi, `stats_summary.json` and `paper_outline.md`.
- **Part 3, complete.** React TypeScript frontend, 12 features, a Three.js crack viewer that
  draws 50,000 cells in one instanced draw call with an automatic fallback, Framer Motion
  transitions, every selector generated from `capabilities()` and every number read from
  `research/stats_summary.json` or from a precomputed solver grid.
- **Part 4, complete.** FastAPI backend wrapping the solver and the trained models, a single
  sample inference helper in `ml/infer.py`, the frontend switched onto the live service with an
  explicit offline mode, 50 Playwright tests across 9 suites against the production bundle, and
  the paper exported to PDF with the 17 figures embedded.

## Design

Three type families. Playfair Display for the wordmark, the headings and every number in the
application, always italic. Space Grotesk for reading. JetBrains Mono for identifiers only.

Three gradients and no more, on a warm ink base: jade, ember and indigo. Each one means
something fixed, including one domain each in every chart, and `--good`, `--warn` and
`--accent` are aliases onto them so nothing can introduce a fourth.

See `HANDOFF.md` for the current state in detail.
