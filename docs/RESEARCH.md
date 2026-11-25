# Research notes — structural-beam-analyzer

How the solver works, which formulas it was checked against, and
where every number in the section catalogue comes from. All
references below are real publications; the verification values in
`beam check` and the test suite are the closed-form results from
these sources.

## 1. Theory: direct-stiffness (finite-element) beam analysis

The beam is modelled with two-node Euler-Bernoulli elements
(degrees of freedom: vertical displacement `v` and rotation `θ` per
node). The element stiffness matrix is the standard one (see
Hibbeler 2017, Ch. 15; Cook et al. 2002, Ch. 2):

```
k_e = EI / L^3 * [[ 12,  6L, -12,  6L],
                  [ 6L, 4L^2, -6L, 2L^2],
                  [-12, -6L,  12, -6L],
                  [ 6L, 2L^2, -6L, 4L^2]]
```

Distributed loads are converted to work-equivalent (consistent)
nodal loads `f = ∫ Nᵀ q dx` with the cubic Hermite shape functions,
so a linearly varying load `w(x)` between element ends `w1, w2`
gives

```
f = [-L(7w1+3w2)/20, -L²(w1/20+w2/30),
     -L(3w1+7w2)/20, +L²(w1/30+w2/20)]
```

(forces up +, moments CCW +; `w` positive downward). For a uniform
load this reduces to the familiar `[-wL/2, -wL²/12, -wL/2, +wL²/12]`.
Element end forces are `f_e = k_e·u_e − f_eq`, converted to internal
shear/moment as `V_left = +f_e[0]`, `M_left = −f_e[1]`,
`V_right = −f_e[2]`, `M_right = +f_e[3]` (sagging moment positive).
Inside an element, `V` and `M` follow from local integration of the
distributed load (`dV/dx = −w`, `dM/dx = V`), and the deflection is
the cubic Hermite interpolation of the nodal `v` and `θ`.

The mesh is built from critical positions (beam ends, supports,
load points, load ends) subdivided so elements are at most ~L/100
long (capped at 600 elements). Reactions are recovered from
`R = K·u − F` at the restrained degrees of freedom, and global
equilibrium residuals (ΣF, ΣM) are reported with every result.

Euler-Bernoulli theory is used throughout: shear deformation is
neglected (valid for the usual span/depth ratios of steel beams),
the material is linear-elastic, and deflections are small.

## 2. Closed-form verification values

Every case below is in `beam check` (12/12 passing) and in the
pytest suite (`tests/test_reactions.py`, `test_diagrams.py`,
`test_deflection.py`). All use E = 200 000 MPa, Ix = 1.0e-4 m⁴
(EI = 20 000 kN·m²) unless noted.

| Case | Reactions | Moment | Deflection |
|---|---|---|---|
| Simply supported, central P | R = P/2 each | Mmax = PL/4 | δ = PL³/48EI |
| Simply supported, UDL w | R = wL/2 each | Mmax = wL²/8 | δ = 5wL⁴/384EI |
| Cantilever, tip P | R = P, M_wall = −PL | M_wall = −PL | δ = PL³/3EI |
| Cantilever, UDL w | R = wL, M_wall = −wL²/2 | M_wall = −wL²/2 | δ = wL⁴/8EI |
| Fixed-fixed, central P | R = P/2 each | M_end = −PL/8, M_mid = +PL/8 | δ = PL³/192EI |
| Fixed-fixed, UDL w | R = wL/2 each | M_end = −wL²/12, M_mid = +wL²/24 | δ = wL⁴/384EI |
| Propped cantilever, UDL w | R_wall = 5wL/8, R_prop = 3wL/8 | M_wall = −wL²/8 | δmax = 0.0054142·wL⁴/EI |
| Continuous, two equal spans, UDL w | R_end = 3wL/8, R_mid = 5wL/4 | M_support = −wL²/8, M_span = 9wL²/128 | δmax ≈ 0.0054·wL⁴/EI |
| Simply supported, triangular 0 → w0 | R_L = w0L/6, R_R = w0L/3 | Mmax = w0L²/(9√3) at x = L/√3 | — |
| Cantilever, triangular 0 at wall → w0 at tip | R = w0L/2 | M_wall = −w0L²/3 | δ = 11w0L⁴/120EI |
| Simply supported, eccentric P (a from left, b from right) | R_L = Pb/L, R_R = Pa/L | Mmax = R_L·a | — |
| Simply supported, midspan couple M0 | R_L = +M0/L, R_R = −M0/L | M jumps by M0 at the couple | — |

These are the standard results tabulated in Gere & Goodno (2017),
Appendix E, and Hibbeler (2017), Appendix C. Two values are easy
to get wrong and were caught during development by re-derivation:
the fixed-fixed UDL end moment is **wL²/12** (not wL²/8 — that is
the simply supported midspan moment), and the cantilever triangular
load with maximum intensity at the **free** end has
M_wall = −w0L²/3 and δ = 11w0L⁴/120EI (the w0L²/6 and w0L⁴/30EI
pair belongs to the maximum at the **fixed** end).

## 3. Stress checks

* Bending: σ_max = |M|max / Sx vs σ_allow = 0.66·Fy — the classic
  ASD allowable for a compact, laterally supported beam
  (AISC 360-16, Ch. F commentary; Hibbeler 2020, Ch. 6).
* Shear: τ_max = |V|max / A_web vs τ_allow = 0.40·Fy, with
  A_web = d·tw for W-shapes and the full area for rectangles.
* LRFD flexure (informational): φMn = 0.9·Zx·Fy
  (AISC 360-16, Ch. F, φb = 0.90).
* Deflection: δ_max vs L/360 by default (a common serviceability
  limit for floors; AISC 360-16, App. L and IBC Table 1604.3 use
  L/360 for floor members).

These are member-strength **screening** checks, not a full
AISC 360 design: lateral-torsional buckling, local (flange/web)
buckling, combined axial load, and connection design are out of
scope (see Limitations in the README).

## 4. Steel sections

Properties are taken from the **AISC Steel Construction Manual,
16th Edition (2017), Tables 1-1** (AISC Shapes Database v16.0),
stored in `src/beam_analyzer/data/sections_aisc.json`. The 11
shapes in the catalogue were cross-checked on 2026-11-25 against
the AISC reference tables republished at
<https://steelcalculator.app/reference/steel-section-properties-lookup/>
(d, bf, tf, tw, A, Ix, Iy, Sx, Zx, rx, ry, J); all 11 match the
published table. Material defaults: E = 200 000 MPa (AISC 360-16,
Sec. B3) and Fy = 345 MPa for ASTM A992 steel (50 ksi = 344.7 MPa;
ASTM A992/A992M).

## References

- Gere, J. M., & Goodno, B. J. (2017). *Mechanics of Materials*
  (8th ed.). Cengage Learning.
- Hibbeler, R. C. (2017). *Structural Analysis* (10th ed.). Pearson.
- Hibbeler, R. C. (2020). *Mechanics of Materials* (10th ed.). Pearson.
- American Institute of Steel Construction. (2017). *Steel
  Construction Manual* (16th ed.). AISC.
- American Institute of Steel Construction. (2016). *Specification
  for Structural Steel Buildings* (ANSI/AISC 360-16). AISC.
- ASTM International. (2022). *Standard Specification for
  Structural Steel Shapes* (ASTM A992/A992M-22). ASTM.
- Cook, R. D., Malkus, D. S., Plesha, M. E., & Witt, R. J. (2002).
  *Concepts and Applications of Finite Element Analysis* (4th ed.).
  Wiley.
- Zienkiewicz, O. C., Taylor, R. L., & Zhu, J. Z. (2013). *The
  Finite Element Method: Its Basis and Fundamentals* (7th ed.).
  Butterworth-Heinemann.
