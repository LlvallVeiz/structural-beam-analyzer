# Changelog

All notable changes to this project are documented here.

## [1.0.0] - 2026-11-25

### Added
- Direct-stiffness (Euler-Bernoulli) beam solver: simply supported,
  cantilever, fixed-fixed, propped cantilever and continuous 2-span
  beams; point, uniform, linearly varying (triangular) and applied-moment
  loads; overhangs and partial distributed loads.
- Shear-force, bending-moment and deflection diagrams computed from
  element end forces and local load integration, with key values
  (max/min shear, moment, deflection) and their locations.
- Stress checks: bending stress vs 0.66*Fy, shear stress vs 0.40*Fy,
  LRFD flexural capacity phi*Mn = 0.9*Zx*Fy, deflection vs L/360.
- AISC W-shape catalogue (11 shapes, Steel Construction Manual
  16th Edition, Tables 1-1) plus rectangular and custom sections,
  lightest-section selection and required-modulus helper.
- Report generation: Markdown + self-contained HTML (embedded SVG
  diagram), station tables, equilibrium residuals.
- CLI (`beam analyze|sections|batch|example|check`) and JSON batch mode
  with `summary.csv`.
- 12 hand-calculation verification cases (`beam check`, 12/12 passing)
  and a 60-test pytest suite.
- 6 example cases with real generated outputs in `examples/output/`.
