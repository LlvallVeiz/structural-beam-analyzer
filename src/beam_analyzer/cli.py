"""Command-line interface for structural-beam-analyzer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .diagrams import max_abs_moment, max_abs_shear
from .io import analyse, load_case, run_batch, write_case_outputs
from .model import (
    AppliedMoment,
    BeamSpec,
    DistributedLoad,
    PointLoad,
    Support,
)
from .sections import get_section, lightest_section_for, list_sections
from .solver import solve

__version__ = "1.0.0"


# ---------------------------------------------------------------------------
# Built-in verification cases (hand calculations / textbook values).
# Every case uses E = 200 000 MPa and Ix = 1.0e-4 m^4, so
# EI = 20 000 kN*m^2.  Expected values are the closed-form results
# from Gere & Goodno / Hibbeler (see docs/RESEARCH.md).
# ---------------------------------------------------------------------------

def _spec(
    name: str,
    length: float,
    supports: list[Support],
    point_loads: list[PointLoad] | None = None,
    distributed: list[DistributedLoad] | None = None,
    moments: list[AppliedMoment] | None = None,
) -> BeamSpec:
    return BeamSpec(
        name=name,
        length_m=length,
        e_mpa=200_000.0,
        Ix_m4=1.0e-4,
        supports=supports,
        point_loads=point_loads or [],
        distributed_loads=distributed or [],
        moments=moments or [],
        fy_mpa=345.0,
    )


def verification_cases() -> list[dict]:
    """Hand-calculation cases: (name, spec, expected dict)."""
    ss = [Support(0.0, "pin"), Support(6.0, "roller")]
    cases: list[dict] = []

    # 1. Simply supported, central point load P = 10 kN, L = 6 m.
    #    R = P/2, Mmax = PL/4, delta = PL^3/(48EI).
    cases.append(
        {
            "name": "SS central point load",
            "spec": _spec("v-ss-central", 6.0, ss, [PointLoad(3.0, 10.0)]),
            "reactions": [5.0, 5.0],
            "m_max": 15.0,
            "m_min": 0.0,
            "delta_max_mm": 10.0 * 6.0 ** 3 / (48.0 * 20000.0) * 1000.0,
        }
    )
    # 2. Simply supported, UDL w = 5 kN/m, L = 6 m.
    #    R = wL/2, Mmax = wL^2/8, delta = 5wL^4/(384EI).
    cases.append(
        {
            "name": "SS uniform load",
            "spec": _spec(
                "v-ss-udl", 6.0, ss, None,
                [DistributedLoad(0.0, 6.0, 5.0, 5.0)],
            ),
            "reactions": [15.0, 15.0],
            "m_max": 22.5,
            "m_min": 0.0,
            "delta_max_mm": 5.0 * 5.0 * 6.0 ** 4 / (384.0 * 20000.0) * 1000.0,
        }
    )
    # 3. Cantilever, tip point load P = 8 kN, L = 4 m.
    #    M_wall = -PL, delta_tip = PL^3/(3EI).
    cases.append(
        {
            "name": "Cantilever tip load",
            "spec": _spec(
                "v-cant-tip", 4.0, [Support(0.0, "fixed")], [PointLoad(4.0, 8.0)]
            ),
            "reactions": [8.0],
            "m_max": 0.0,
            "m_min": -32.0,
            "delta_max_mm": 8.0 * 4.0 ** 3 / (3.0 * 20000.0) * 1000.0,
        }
    )
    # 4. Cantilever, UDL w = 3 kN/m, L = 4 m.
    #    M_wall = -wL^2/2, delta_tip = wL^4/(8EI).
    cases.append(
        {
            "name": "Cantilever uniform load",
            "spec": _spec(
                "v-cant-udl", 4.0, [Support(0.0, "fixed")], None,
                [DistributedLoad(0.0, 4.0, 3.0, 3.0)],
            ),
            "reactions": [12.0],
            "m_max": 0.0,
            "m_min": -24.0,
            "delta_max_mm": 3.0 * 4.0 ** 4 / (8.0 * 20000.0) * 1000.0,
        }
    )
    # 5. Fixed-fixed, central point load P = 12 kN, L = 6 m.
    #    R = P/2, M_end = -PL/8, M_mid = +PL/8, delta = PL^3/(192EI).
    cases.append(
        {
            "name": "Fixed-fixed central load",
            "spec": _spec(
                "v-ff-central", 6.0,
                [Support(0.0, "fixed"), Support(6.0, "fixed")],
                [PointLoad(3.0, 12.0)],
            ),
            "reactions": [6.0, 6.0],
            "m_max": 9.0,
            "m_min": -9.0,
            "delta_max_mm": 12.0 * 6.0 ** 3 / (192.0 * 20000.0) * 1000.0,
        }
    )
    # 6. Fixed-fixed, UDL w = 4 kN/m, L = 6 m.
    #    R = wL/2, M_end = -wL^2/12, M_mid = +wL^2/24, delta = wL^4/(384EI).
    cases.append(
        {
            "name": "Fixed-fixed uniform load",
            "spec": _spec(
                "v-ff-udl", 6.0,
                [Support(0.0, "fixed"), Support(6.0, "fixed")], None,
                [DistributedLoad(0.0, 6.0, 4.0, 4.0)],
            ),
            "reactions": [12.0, 12.0],
            "m_max": 6.0,
            "m_min": -12.0,
            "delta_max_mm": 4.0 * 6.0 ** 4 / (384.0 * 20000.0) * 1000.0,
        }
    )
    # 7. Propped cantilever, UDL w = 6 kN/m, L = 5 m.
    #    R_roller = 3wL/8, R_wall = 5wL/8, M_wall = -wL^2/8,
    #    delta_max = wL^4/(185EI).
    cases.append(
        {
            "name": "Propped cantilever UDL",
            "spec": _spec(
                "v-propped-udl", 5.0,
                [Support(0.0, "fixed"), Support(5.0, "roller")], None,
                [DistributedLoad(0.0, 5.0, 6.0, 6.0)],
            ),
            "reactions": [18.75, 11.25],
            "m_max": 9.0 * 6.0 * 5.0 ** 2 / 128.0,
            "m_min": -18.75,
            "delta_max_mm": 6.0 * 5.0 ** 4 / (185.0 * 20000.0) * 1000.0,
        }
    )
    # 8. Continuous beam, two equal spans L = 4 m, UDL w = 5 kN/m.
    #    R_end = 3wL/8, R_mid = 5wL/4, M_support = -wL^2/8,
    #    M_span_max = 9wL^2/128.
    cases.append(
        {
            "name": "Continuous two-span UDL",
            "spec": _spec(
                "v-cont-udl", 8.0,
                [Support(0.0, "pin"), Support(4.0, "roller"),
                 Support(8.0, "roller")], None,
                [DistributedLoad(0.0, 8.0, 5.0, 5.0)],
            ),
            "reactions": [7.5, 25.0, 7.5],
            "m_max": 9.0 * 5.0 * 4.0 ** 2 / 128.0,
            "m_min": -10.0,
            "delta_max_mm": None,  # checked separately in the test-suite
        }
    )
    # 9. Simply supported, triangular load 0 -> w0 = 6 kN/m, L = 6 m.
    #    R_left = w0 L/6, R_right = w0 L/3, Mmax = w0 L^2/(9 sqrt 3).
    cases.append(
        {
            "name": "SS triangular load",
            "spec": _spec(
                "v-ss-tri", 6.0, ss, None,
                [DistributedLoad(0.0, 6.0, 0.0, 6.0)],
            ),
            "reactions": [6.0, 12.0],
            "m_max": 6.0 * 6.0 ** 2 / (9.0 * 3.0 ** 0.5),
            "m_min": 0.0,
            "delta_max_mm": None,
        }
    )
    # 10. Cantilever, triangular load 0 at wall -> w0 = 8 kN/m at tip.
    #     Resultant w0*L/2 acts at 2L/3 from the wall, so
    #     M_wall = -w0*L^2/3 and delta_tip = 11*w0*L^4/(120EI).
    cases.append(
        {
            "name": "Cantilever triangular load",
            "spec": _spec(
                "v-cant-tri", 4.0, [Support(0.0, "fixed")], None,
                [DistributedLoad(0.0, 4.0, 0.0, 8.0)],
            ),
            "reactions": [16.0],
            "m_max": 0.0,
            "m_min": -8.0 * 4.0 ** 2 / 3.0,
            "delta_max_mm": 11.0 * 8.0 * 4.0 ** 4 / (120.0 * 20000.0) * 1000.0,
        }
    )
    # 11. Simply supported, eccentric point load P = 10 kN at x = 2 m.
    #     R_left = Pb/L, R_right = Pa/L, Mmax = R_left * a.
    cases.append(
        {
            "name": "SS eccentric point load",
            "spec": _spec("v-ss-ecc", 6.0, ss, [PointLoad(2.0, 10.0)]),
            "reactions": [40.0 / 6.0, 20.0 / 6.0],
            "m_max": 40.0 / 3.0,
            "m_min": 0.0,
            "delta_max_mm": None,
        }
    )
    # 12. Simply supported, CCW moment M0 = 12 kN*m at midspan.
    #     R_left = +M0/L, R_right = -M0/L; M jumps from +6 to -6.
    cases.append(
        {
            "name": "SS midspan applied moment",
            "spec": _spec(
                "v-ss-moment", 6.0, ss, None, None,
                [AppliedMoment(3.0, 12.0)],
            ),
            "reactions": [2.0, -2.0],
            "m_max": 6.0,
            "m_min": -6.0,
            "delta_max_mm": None,
        }
    )
    return cases


def run_verification(tol: float = 2e-3) -> tuple[int, int, list[str]]:
    """Run the hand-calculation cases; returns (passed, total, lines).

    Tolerance is relative (2e-3): the FEM deflection uses cubic
    Hermite interpolation on ~100 elements, so sampled maxima agree
    with closed-form values to ~0.1%, while reactions and end
    moments are exact to solver precision.
    """
    from .diagrams import compute_diagrams

    passed = 0
    lines: list[str] = []
    cases = verification_cases()
    for case in cases:
        sol = solve(case["spec"])
        dia = compute_diagrams(sol)
        m_max = max_abs_moment(dia)
        checks: list[tuple[str, float, float]] = []
        for got, want in zip(
            [r.vertical_kn for r in sol.reactions], case["reactions"]
        ):
            checks.append(("R", got, want))
        checks.append(("Mmax", dia.max_moment.value, case["m_max"]))
        checks.append(("Mmin", dia.min_moment.value, case["m_min"]))
        if case["delta_max_mm"] is not None:
            checks.append(("delta", dia.max_deflection.value, case["delta_max_mm"]))
        ok = True
        detail = []
        for label, got, want in checks:
            good = abs(got - want) <= tol * max(1.0, abs(want))
            ok = ok and good
            detail.append(f"{label} {got:.4f} vs {want:.4f} {'ok' if good else 'FAIL'}")
        passed += 1 if ok else 0
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {case['name']}: " + "; ".join(detail))
    return passed, len(cases), lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _examples_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "examples"


def _cmd_analyze(args: argparse.Namespace) -> int:
    spec, section = load_case(args.input)
    result = analyse(spec, section)
    out_dir = Path(args.out) if args.out else Path("output") / spec.name
    write_case_outputs(result, out_dir)
    m = result["diagrams"].max_moment
    d = result["diagrams"].max_deflection
    print(f"Case: {spec.name}  |  section: {section.name}")
    print(f"  Reactions: {[round(r.vertical_kn, 3) for r in result['solution'].reactions]} kN")
    print(f"  Mmax: {m.value:.3f} kN*m at x={m.x_m:.3f} m")
    print(f"  Max deflection: {d.value:.3f} mm at x={d.x_m:.3f} m")
    print(f"  Verdict: {result['check'].verdict()}")
    print(f"  Outputs written to {out_dir}")
    return 0


def _cmd_sections(args: argparse.Namespace) -> int:
    if args.list:
        print(f"{'Designation':<12}{'d (in)':>8}{'A (in^2)':>9}{'Ix (in^4)':>10}"
              f"{'Sx (in^3)':>10}{'Zx (in^3)':>10}{'wt (lb/ft)':>11}")
        for name in list_sections():
            s = get_section(name)
            print(f"{name:<12}{s.depth_m / 0.0254:>8.2f}{s.area_m2 / 6.4516e-4:>9.2f}"
                  f"{s.Ix_m4 / 4.16231e-7:>10.1f}{s.Sx_m3 / 1.63871e-5:>10.1f}"
                  f"{s.Zx_m3 / 1.63871e-5:>10.1f}{s.weight_kn_m / 0.0145939:>11.1f}")
        return 0
    if args.show:
        s = get_section(args.show)
        print(json.dumps({
            "designation": s.name,
            "depth_in": round(s.depth_m / 0.0254, 3),
            "Ix_in4": round(s.Ix_m4 / 4.16231e-7, 2),
            "Sx_in3": round(s.Sx_m3 / 1.63871e-5, 2),
            "Zx_in3": round(s.Zx_m3 / 1.63871e-5, 2),
            "area_in2": round(s.area_m2 / 6.4516e-4, 3),
            "weight_lb_ft": round(s.weight_kn_m / 0.0145939, 2),
            "source": s.source,
        }, indent=2))
        return 0
    if args.lightest is not None:
        fy = args.fy or 345.0
        s = lightest_section_for(args.lightest, fy)
        print(f"Lightest section for M = {args.lightest:.1f} kN*m at Fy = {fy:.0f} MPa: "
              f"{s.name} (Sx = {s.Sx_cm3:.1f} cm^3)")
        return 0
    print("Use --list, --show DESIGN or --lightest M_kNm.")
    return 2


def _cmd_batch(args: argparse.Namespace) -> int:
    rows = run_batch(args.input_dir, args.out)
    for row in rows:
        print(f"{row['name']:<28} Mmax {row['max_moment_kNm']:>9.3f} kN*m  "
              f"delta {row['max_deflection_mm']:>8.3f} mm  {row['verdict']}")
    print(f"{len(rows)} cases written to {args.out} (summary.csv included)")
    return 0


def _cmd_example(args: argparse.Namespace) -> int:
    names = sorted(p.stem for p in _examples_dir().glob("*.json"))
    if args.name == "list":
        print("Built-in examples: " + ", ".join(names))
        return 0
    src = _examples_dir() / f"{args.name}.json"
    if not src.exists():
        print(f"unknown example {args.name!r}; available: {', '.join(names)}")
        return 2
    if args.out:
        dest = Path(args.out) / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Example written to {dest}")
    else:
        print(src.read_text(encoding="utf-8"))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    passed, total, lines = run_verification()
    for line in lines:
        print(line)
    print(f"Verification: {passed}/{total} cases passed")
    return 0 if passed == total else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="beam",
        description="Structural beam analyzer: reactions, shear/moment "
                    "diagrams, deflection and stress checks.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="Analyse one JSON case file.")
    p.add_argument("input", help="Input JSON file.")
    p.add_argument("--out", help="Output directory (default: output/<name>).")
    p.set_defaults(func=_cmd_analyze)

    p = sub.add_parser("sections", help="Query the AISC section catalogue.")
    p.add_argument("--list", action="store_true", help="List all sections.")
    p.add_argument("--show", metavar="DESIGN", help="Show one section.")
    p.add_argument("--lightest", type=float, metavar="M_kNm",
                   help="Lightest section for a moment demand.")
    p.add_argument("--fy", type=float, help="Yield strength in MPa (default 345).")
    p.set_defaults(func=_cmd_sections)

    p = sub.add_parser("batch", help="Analyse all JSON cases in a directory.")
    p.add_argument("input_dir", help="Directory with *.json case files.")
    p.add_argument("--out", required=True, help="Output directory.")
    p.set_defaults(func=_cmd_batch)

    p = sub.add_parser("example", help="Show or copy a built-in example case.")
    p.add_argument("name", help="Example name, or 'list'.")
    p.add_argument("--out", help="Directory to copy the JSON into.")
    p.set_defaults(func=_cmd_example)

    p = sub.add_parser("check", help="Run hand-calculation verification cases.")
    p.set_defaults(func=_cmd_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
