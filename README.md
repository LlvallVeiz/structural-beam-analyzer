# structural-beam-analyzer

Euler-Bernoulli beam analysis in Python: reactions, shear-force and
bending-moment diagrams, deflection, and stress checks — with every
computed value verified against hand calculations and textbook
formulas.

```
$ beam check
[PASS] SS central point load: R 5.0000 vs 5.0000 ok; ... delta 2.2500 vs 2.2500 ok
[PASS] SS uniform load: ...
...
Verification: 12/12 cases passed
```

## Background and theory

A beam is discretised into two-node Euler-Bernoulli finite elements
(vertical displacement `v` and rotation `θ` per node) and solved
with the direct-stiffness method. Distributed loads are converted
to work-equivalent (consistent) nodal loads, so uniform and linearly
varying (triangular) loads are handled exactly at the element level.
Element end forces give the shear and moment at element ends;
inside an element, `V` and `M` follow from local integration of the
distributed load (`dV/dx = −w`, `dM/dx = V`, sagging moment
positive), and deflection is the cubic Hermite interpolation of the
nodal displacements. The mesh is built from critical positions
(supports, load points, load ends) subdivided to ~L/100.

Stress checks (screening level, see Limitations):

- Bending: σ_max = |M|max / Sx vs 0.66·Fy (ASD, compact beam)
- Shear: τ_max = |V|max / A_web vs 0.40·Fy
- LRFD flexure: φMn = 0.9·Zx·Fy vs the moment demand
- Deflection: δ_max vs L/360 (configurable)

Full derivation, the closed-form verification table, and references
are in [docs/RESEARCH.md](docs/RESEARCH.md).

## Features

- Support types: pin, roller, fixed — simply supported, cantilever,
  fixed-fixed, propped cantilever, continuous 2-span, and overhangs.
- Loads: point load, uniform distributed load, linearly varying
  (triangular) distributed load, applied moment; partial distributed
  loads; optional section self-weight.
- Reactions (vertical + moment), shear/moment/deflection diagrams
  with key values and their locations, station tables.
- AISC W-shape catalogue (11 shapes, Steel Construction Manual
  16th ed., Tables 1-1) plus rectangular and custom sections;
  lightest-section selection for a moment demand.
- Reports: Markdown + self-contained HTML (embedded SVG diagram),
  JSON metrics, CSV batch summary.
- CLI + JSON batch mode; 12 hand-calculation verification cases
  (`beam check`) and a 71-test pytest suite.

## Project structure

```
structural-beam-analyzer/
├── src/beam_analyzer/
│   ├── __init__.py  __main__.py  cli.py      # CLI (analyze, sections, batch, example, check)
│   ├── model.py     # BeamSpec, supports, loads, sign conventions
│   ├── solver.py    # direct-stiffness FEM, equivalent nodal loads
│   ├── diagrams.py  # shear/moment/deflection diagrams, plots
│   ├── sections.py  # AISC catalogue + rectangular/custom sections
│   ├── stress.py    # bending/shear/LRFD/deflection checks
│   ├── report.py    # Markdown + HTML report generation
│   ├── io.py        # JSON input, batch mode, metrics
│   ├── units.py     # SI/imperial conversions
│   └── data/sections_aisc.json   # 11 W-shapes, AISC 16th ed. Table 1-1
├── tests/           # 71 pytest tests (reactions, diagrams, deflection,
│                    #   stress, sections, solver, io, report, cli)
├── examples/        # 6 JSON cases + run_examples.py + RESULTS.md
│   └── output/      # generated reports/diagrams/metrics per example
├── docs/RESEARCH.md # theory, verification table, references
├── pyproject.toml  requirements.txt  LICENSE  CHANGELOG.md
```

## Installation

Python 3.10+, numpy and matplotlib:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .          # installs the `beam` command
```

Without installing, run with `PYTHONPATH=src python -m beam_analyzer ...`.

## How to run

### Verify against hand calculations

```bash
beam check
# Verification: 12/12 cases passed
```

### Analyse one case (JSON input)

```bash
beam analyze examples/ss_central_point.json --out output/ss_central_point
```

```
Case: ss_central_point  |  section: W12x26
  Reactions: [5.0, 5.0] kN
  Mmax: 15.000 kN*m at x=3.000 m
  Max deflection: 2.650 mm at x=3.000 m
  Verdict: PASS
  Outputs written to output/ss_central_point
```

The output folder contains `report.md`, `report.html`,
`diagram.png`, `diagram.svg` and `metrics.json`.

### Batch mode

```bash
beam batch examples --out output/all
# ss_central_point ... PASS
# ...
# 6 cases written to output/all (summary.csv included)
```

### Section catalogue

```bash
beam sections --list
beam sections --show W12x26
beam sections --lightest 100        # lightest section for M = 100 kN*m
```

```
Lightest section for M = 100.0 kN*m at Fy = 345 MPa: W12x26 (Sx = 547.3 cm^3)
```

### Built-in examples

```bash
beam example list
# Built-in examples: cantilever_tip, continuous_two_span, fixed_fixed_udl,
#   propped_cantilever_triangular, ss_central_point, ss_udl
beam example ss_udl --out /tmp/cases   # copy one example JSON out
```

### JSON input format

```json
{
  "name": "ss-central-point",
  "length_m": 6.0,
  "E_MPa": 200000,
  "section": {"type": "aisc", "designation": "W12x26", "Fy_MPa": 345},
  "supports": [{"x_m": 0, "type": "pin"}, {"x_m": 6, "type": "roller"}],
  "loads": [{"type": "point", "x_m": 3, "P_kN": 10}],
  "options": {"deflection_limit_ratio": 360, "include_self_weight": false}
}
```

Section alternatives: `{"type": "rectangular", "b_m": 0.2, "h_m": 0.4}`
or `{"type": "custom", "Ix_m4": ..., "Sx_m3": ..., "Zx_m3": ...,
"area_m2": ..., "depth_m": ..., "web_area_m2": ...}`.
Load types: `point` (`x_m`, `P_kN`), `udl` (`x1_m`, `x2_m`,
`w_kN_m`), `triangular` (`x1_m`, `x2_m`, `w1_kN_m`, `w2_kN_m`),
`moment` (`x_m`, `M_kNm`).

## Example outputs (real runs)

From `examples/RESULTS.md` — generated 25 Nov 2026, all PASS:

| Example | Section | Reactions (kN) | \|M\|max (kN·m) | δmax (mm) | σmax (MPa) | Bending util. |
|---|---|---|---|---|---|---|
| `ss_central_point` — P = 10 kN midspan, L = 6 m | W12x26 | 5.00, 5.00 | 15.000 | 2.650 | 27.406 | 0.120 |
| `ss_udl` — w = 5 kN/m, L = 6 m | W10x30 | 15.00, 15.00 | 22.500 | 5.962 | 42.378 | 0.186 |
| `cantilever_tip` — P = 8 kN at tip, L = 4 m | W12x26 | 8.00 | 32.000 | 10.050 | 58.466 | 0.257 |
| `fixed_fixed_udl` — w = 4 kN/m, L = 6 m | W10x22 | 12.00, 12.00 | 12.000 | 1.374 | 31.564 | 0.139 |
| `continuous_two_span` — two 4 m spans, w = 5 kN/m | W12x26 | 7.50, 25.00, 7.50 | 10.000 | 0.408 | 18.271 | 0.080 |
| `propped_cantilever_triangular` — triangular 0 → 6 kN/m, L = 5 m | W14x48 | 6.75, 8.25 | 8.750 | 0.284 | 7.606 | 0.033 |

Spot-checks against closed forms: `ss_central_point`
Mmax = PL/4 = 15 kN·m, δ = PL³/48EI = 2.650 mm;
`fixed_fixed_udl` end moments −wL²/12 = −12 kN·m, midspan
+wL²/24 = +6 kN·m; `continuous_two_span` interior reaction
5wL/4 = 25 kN. Equilibrium residuals are ~1e-9 kN in every case.

## Design decisions

- **SI internally** (m, kN, kN·m, MPa); the AISC catalogue is stored
  in imperial units as published and converted on load, so the
  source data stays verbatim.
- **Exact equivalent nodal loads** instead of lumping distributed
  loads at nodes: reactions and end moments are exact to solver
  precision, and deflections agree with closed forms to ~0.1%
  (the only approximation is the sampled Hermite maximum).
- **Sections are data, not code**: the catalogue is a JSON file with
  a cited source, so adding shapes needs no code change.
- **Sign conventions are documented in `model.py`** and enforced by
  tests: loads downward +, reactions upward +, sagging moment +,
  `dV/dx = −w`, `dM/dx = V`.
- **Verification is a first-class command** (`beam check`), not an
  afterthought: the same 12 hand calculations are also pytest
  tests, so a regression fails the suite.

## Verification

```bash
beam check          # 12/12 hand-calculation cases passed
pytest -q           # 71 passed
```

## Limitations

- Euler-Bernoulli only: no shear deformation (Timoshenko), so deep
  beams (span/depth < ~5) will be slightly stiffer than reality.
- No lateral-torsional buckling, local flange/web buckling, or
  combined axial + bending checks — the stress checks are screening
  checks, not a full AISC 360 design.
- No axial degrees of freedom, no temperature or support-settlement
  loads, no dynamic analysis.
- Single beam only (no frames); only the strong axis is considered.
- Deflection maxima are sampled from Hermite interpolation on a
  ~L/100 mesh, so they agree with closed forms to ~0.1–0.2%, not
  to machine precision.

## References

- Gere, J. M., & Goodno, B. J. (2017). *Mechanics of Materials*
  (8th ed.). Cengage Learning.
- Hibbeler, R. C. (2017). *Structural Analysis* (10th ed.). Pearson.
- AISC. (2017). *Steel Construction Manual* (16th ed.).
- AISC. (2016). *Specification for Structural Steel Buildings*
  (ANSI/AISC 360-16).
- ASTM A992/A992M-22. *Standard Specification for Structural Steel
  Shapes*.
- Cook, R. D., et al. (2002). *Concepts and Applications of Finite
  Element Analysis* (4th ed.). Wiley.

## License

MIT — see [LICENSE](LICENSE).
