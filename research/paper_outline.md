# FRACTUREVERSE, paper outline

Target: one methods and results paper covering four fracture theories, three
application domains, a surrogate model layer and a physics informed network, all
reproducible from this repository. Numbers quoted below live in
`research/part1_validation.json`, `research/ml_report.json`,
`research/stats_summary.json` and `pinn/artifacts/pinn_report.json`. Figures are in
`python_stats/figures`, captions in `python_stats/figures/captions.json`.

No em dashes anywhere in the manuscript.

## 1. Introduction

- Fatigue and fracture cost, per domain, from the `impact` block of each
  `data/<domain>/materials.json`. Aerospace: fatigue is about 20 percent of
  airframe structural failures. Biomedical: 400,000 hip and knee replacements a
  year in the United States, revision 15,000 to 50,000 dollars. Civil: 42,000 of
  617,000 bridges in the National Bridge Inventory are structurally deficient.
- The gap the paper addresses: the four theories are usually taught and coded in
  isolation, on different meshes, in different unit systems, against different
  benchmarks. Here they share one material database, one unit convention and one
  validation harness.

## 2. Governing theory

One subsection per theory, each ending with the independent target it was checked
against.

2.1 Linear elastic fracture mechanics. K_I = F sigma sqrt(pi a), Paris, Walker and
Forman growth laws, implicit critical crack length. Validation: closed form Paris
integral to 2.6e-12 percent, geometry factors within 0.5 percent of handbook.
Figures 2, 3, 8.

2.2 Elastic plastic fracture mechanics. Domain form J integral, elastic plastic J,
J-R resistance curves, tearing instability by tangency, CTOD. Validation: domain J
against K_I squared over E prime, -1.59 percent. Figures 6, 7.

2.3 Extended finite element method. Heaviside and four branch function enrichment,
shifted, exact polygon clipping for cut elements, interaction integral for K_I and
K_II, maximum circumferential stress criterion for turning. Validation: centre
cracked panel within 0.5 percent, domain independence under 0.1 percent, pure mode
II kink angle -70.53 degrees against the Erdogan and Sih limit of -70.5. Figures 4,
10.

2.4 Peridynamics. Bond based, micromodulus and critical stretch calibrated to G_0,
no predefined crack path. Validation: continuum identity exact, discrete recovery
-9.2 percent at delta over dx of 6, branching confirmed, m convergence monotone.
Figures 5, 16.

## 3. Domain data and unit convention

- Table of the six materials with sources: Reilly and Burstein 1975, Yeni 1997,
  Caler and Carter 1989, Keller 1994, Bergmann 2001, Bazant and Pfeiffer 1987,
  NASA/TM-2002-211428, NASGRO, ASTM E399, FHWA NBI, ASCE 2021.
- The one deviation from strict SI: K in MPa sqrt(m), Paris C scaled to match.
  Stress crosses every API boundary in pascals.
- Loading data: hip contact force telemetry, figure 11. Corrosion model, figure 12.
  Toughness against temperature, figure 15.
- State plainly that the bulk National Bridge Inventory table was not downloaded.
  `data/civil/corrosion.json` carries the condition rating scale and the deficient
  bridge count, and nothing in the code depends on the 617,000 row table.

## 4. Surrogate modelling

- Data: 1500 trajectories, 500 per domain, from the LEFM integrator over five
  initial crack lengths, five stress amplitudes, four stress ratios and five
  material samples drawn inside the published uncertainty ranges. Seed 1337.
- Task: read the first 20 samples of a trajectory and predict log10 of the total
  life. Inspection noise is added to the observed window.
- The leak that had to be closed: with the Paris coefficients and a_c in the
  feature vector, the target is a closed form function of the inputs and ridge
  regression scores R squared above 0.999. The reported feature set removes them.
- Models: ridge, closed form Paris with a frozen geometry factor, XGBoost, LSTM.
  Figures 13 and 14.
- **Finding to state, not bury.** Every model clears the 0.92 R squared target,
  ridge included, because Paris Law is a power law and log life is nearly linear in
  the log features. The honest comparison is RMSE in decades of life and the median
  life ratio error, not R squared. Report the target as met and explain why it was
  never the discriminating metric.

## 5. Physics informed neural network

- 8 hidden layers, 128 neurons, tanh, Xavier initialisation, plane stress centre
  cracked panel matching the XFEM benchmark exactly.
- Five loss terms: equilibrium residual, top traction, free lateral edges, traction
  free crack faces, XFEM displacement data. NTK style gradient norm weighting,
  rebalanced every 100 epochs.
- Two design points worth a paragraph each. First, a plain multilayer perceptron
  cannot represent the displacement jump across the crack faces, so the four
  Westergaard branch functions per tip are supplied as input features and carry the
  discontinuity, which is the XFEM enrichment idea moved from the basis to the
  inputs. Second, the roller boundary condition is imposed as a hard constraint,
  v = (y / H) times the network output, so it never competes with the other losses.
- Report wall clock as measured on CPU, and say that this machine has an integrated
  Radeon 610M with no usable compute, so the epoch count was chosen to fit. Figure 17.

## 6. Results

- Life predictions per domain, both Paris coefficients, from
  `stats_summary.json.domain_lives`.
- Cross theory agreement table: K_I from LEFM, XFEM and the PINN opening fit on the
  same panel.
- Surrogate accuracy table, per domain.
- PINN field accuracy against XFEM.

## 7. Limitations, stated up front rather than in a footnote

1. The specified Paris coefficient for 2024-T3 is conservative by a factor of about
   5.7 on rate, so predicted aerospace lives are short by roughly that factor. Both
   values are computed and reported.
2. Bond based peridynamics ties effective strength to the horizon and fixes the
   Poisson ratio at one third in two dimensional plane stress. Every peridynamic
   run reports the horizon implied strength next to the applied stress.
3. The surrogate task is close to log linear. See section 4.
4. The PINN is trained on one panel geometry at one load level. It is a field
   solver demonstration, not a parametric surrogate.
5. Corrosion is coupled to fatigue through a section loss to stress rise argument,
   which is the simplest defensible coupling and is labelled as such on figure 12.
6. Trajectory generation, model training and figure production are all seeded, but
   torch on CPU is only bitwise reproducible for the same torch build.

## 8. Reproduction

```bash
python validate_part1.py
python -m ml.train_all
python -m pinn.train
python -m python_stats.generate_all
python -m python_stats.summarize
```

## Figure list

| Figure | Content |
|---|---|
| 1 | Paris rate curves against reference bands, specified against anchored C |
| 2 | Crack length against cycles, three domains, three growth laws |
| 3 | Geometry correction factors and the K_I they produce |
| 4 | XFEM mixed mode crack path and K history |
| 5 | Peridynamic damage field with branching |
| 6 | J-R curves and tearing instability |
| 7 | CTOD against load level |
| 8 | Critical crack length against applied stress |
| 9 | Small scale yielding validity map |
| 10 | Kink angle against mode mixity |
| 11 | Gait loading and the K it drives |
| 12 | Corrosion penetration and the life it removes |
| 13 | Surrogate parity plots on the fixed test split |
| 14 | SHAP attribution |
| 15 | Toughness against temperature and tolerable flaw size |
| 16 | Peridynamic m convergence and fracture energy recovery |
| 17 | PINN losses, adaptive weights, opening profile against XFEM |
