# Example results

Generated with `PYTHONPATH=src python examples/run_examples.py`
(25 Nov 2026). Every number below is copied from the
`metrics.json` produced by that run — no hand-typed values.
Each example folder in `examples/output/<name>/` contains
`report.md`, `report.html`, `diagram.png`, `diagram.svg` and
`metrics.json`.

| Example | Section | Reactions (kN) | \|M\|max (kN·m) | δmax (mm) | σmax (MPa) | Bending util. | Verdict |
|---|---|---|---|---|---|---|---|
| `ss_central_point` — SS beam, P = 10 kN at midspan, L = 6 m | W12x26 | 5.00, 5.00 | 15.000 | 2.650 | 27.406 | 0.120 | PASS |
| `ss_udl` — SS beam, w = 5 kN/m, L = 6 m | W10x30 | 15.00, 15.00 | 22.500 | 5.962 | 42.378 | 0.186 | PASS |
| `cantilever_tip` — cantilever, P = 8 kN at tip, L = 4 m | W12x26 | 8.00 | 32.000 | 10.050 | 58.466 | 0.257 | PASS |
| `fixed_fixed_udl` — fixed-fixed, w = 4 kN/m, L = 6 m | W10x22 | 12.00, 12.00 | 12.000 | 1.374 | 31.564 | 0.139 | PASS |
| `continuous_two_span` — two 4 m spans, w = 5 kN/m | W12x26 | 7.50, 25.00, 7.50 | 10.000 | 0.408 | 18.271 | 0.080 | PASS |
| `propped_cantilever_triangular` — propped cantilever, triangular 0 → 6 kN/m, L = 5 m | W14x48 | 6.75, 8.25 | 8.750 | 0.284 | 7.606 | 0.033 | PASS |

Notes:

- `ss_central_point`: Mmax = PL/4 = 15 kN·m and
  δ = PL³/48EI = 2.650 mm (W12x26, Ix = 204 in⁴) — matches the
  closed form exactly.
- `ss_udl`: Mmax = wL²/8 = 22.5 kN·m; δ = 5wL⁴/384EI = 5.962 mm
  (W10x30, Ix = 170 in⁴).
- `cantilever_tip`: wall moment −32 kN·m (= −PL), tip deflection
  10.050 mm (= PL³/3EI). Deflection utilisation is the tightest
  here: δ_allow = L/360 = 11.111 mm.
- `fixed_fixed_udl`: end moments −12 kN·m (= −wL²/12), midspan
  +6 kN·m (= +wL²/24), δ = 1.374 mm (= wL⁴/384EI).
- `continuous_two_span`: end reactions 3wL/8 = 7.5 kN, interior
  5wL/4 = 25 kN, support moment −wL²/8 = −10 kN·m, span moment
  9wL²/128 = 5.625 kN·m.
- `propped_cantilever_triangular`: reactions 6.75 kN (wall) and
  8.25 kN (prop) sum to the 15 kN total load; wall moment
  −8.75 kN·m; equilibrium residuals are ~1e-9 kN in every case.
