"""JSON input/output and batch mode.

Input JSON schema (all lengths in metres, forces in kN, E/Fy in MPa)::

    {
      "name": "ss-central-point",
      "length_m": 6.0,
      "E_MPa": 200000,
      "section": {"type": "aisc", "designation": "W12x26", "Fy_MPa": 345},
      "supports": [{"x_m": 0, "type": "pin"}, {"x_m": 6, "type": "roller"}],
      "loads": [{"type": "point", "x_m": 3, "P_kN": 10}],
      "options": {"deflection_limit_ratio": 360,
                  "include_self_weight": false}
    }

Section alternatives::

    {"type": "rectangular", "b_m": 0.2, "h_m": 0.4, "Fy_MPa": 24}
    {"type": "custom", "Ix_m4": 2.5e-4, "Sx_m3": 1.2e-3,
     "Zx_m3": 1.4e-3, "area_m2": 0.01, "depth_m": 0.4,
     "web_area_m2": 0.008, "weight_kn_m": 0.0, "Fy_MPa": 345}

Load entries: ``point`` (x_m, P_kN), ``udl`` (x1_m, x2_m, w_kN_m),
``triangular`` (x1_m, x2_m, w1_kN_m, w2_kN_m) and ``moment``
(x_m, M_kNm).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .diagrams import compute_diagrams, max_abs_moment, max_abs_shear, plot_diagrams
from .model import (
    AppliedMoment,
    BeamSpec,
    DistributedLoad,
    PointLoad,
    Support,
)
from .report import build_html, build_markdown
from .sections import Section, get_section, rectangular_section
from .solver import solve
from .stress import check_stress


def _load_section(spec_dict: dict) -> tuple[Section, float]:
    """Build a Section from the ``section`` block; returns (section, Fy)."""
    block = spec_dict["section"]
    kind = block["type"]
    fy = float(block.get("Fy_MPa", 345.0))
    if kind == "aisc":
        section = get_section(block["designation"])
    elif kind == "rectangular":
        section = rectangular_section(float(block["b_m"]), float(block["h_m"]))
    elif kind == "custom":
        section = Section(
            name=block.get("name", "CUSTOM"),
            Ix_m4=float(block["Ix_m4"]),
            Sx_m3=float(block["Sx_m3"]),
            Zx_m3=float(block["Zx_m3"]),
            area_m2=float(block["area_m2"]),
            depth_m=float(block["depth_m"]),
            web_area_m2=float(block["web_area_m2"]),
            weight_kn_m=float(block.get("weight_kn_m", 0.0)),
            source="user-supplied custom section",
        )
    else:
        raise ValueError(f"unknown section type {kind!r}")
    return section, fy


def spec_from_dict(data: dict) -> tuple[BeamSpec, Section]:
    """Parse an input dict into (BeamSpec, Section)."""
    section, fy = _load_section(data)
    options = data.get("options", {})
    supports = [
        Support(float(s["x_m"]), s["type"]) for s in data.get("supports", [])
    ]
    point_loads: list[PointLoad] = []
    distributed: list[DistributedLoad] = []
    moments: list[AppliedMoment] = []
    for entry in data.get("loads", []):
        kind = entry["type"]
        if kind == "point":
            point_loads.append(PointLoad(float(entry["x_m"]), float(entry["P_kN"])))
        elif kind == "udl":
            distributed.append(
                DistributedLoad(
                    float(entry["x1_m"]),
                    float(entry["x2_m"]),
                    float(entry["w_kN_m"]),
                    float(entry["w_kN_m"]),
                )
            )
        elif kind == "triangular":
            distributed.append(
                DistributedLoad(
                    float(entry["x1_m"]),
                    float(entry["x2_m"]),
                    float(entry["w1_kN_m"]),
                    float(entry["w2_kN_m"]),
                )
            )
        elif kind == "moment":
            moments.append(
                AppliedMoment(float(entry["x_m"]), float(entry["M_kNm"]))
            )
        else:
            raise ValueError(f"unknown load type {kind!r}")
    spec = BeamSpec(
        name=data.get("name", "beam"),
        length_m=float(data["length_m"]),
        e_mpa=float(data.get("E_MPa", 200_000.0)),
        Ix_m4=section.Ix_m4,
        supports=supports,
        point_loads=point_loads,
        distributed_loads=distributed,
        moments=moments,
        fy_mpa=fy,
        include_self_weight=bool(options.get("include_self_weight", False)),
        deflection_limit_ratio=float(options.get("deflection_limit_ratio", 360.0)),
        section_name=section.name,
        section_weight_kn_m=section.weight_kn_m,
    )
    return spec, section


def load_case(path: str | Path) -> tuple[BeamSpec, Section]:
    """Load one JSON case file."""
    with open(path, encoding="utf-8") as fh:
        return spec_from_dict(json.load(fh))


def analyse(spec: BeamSpec, section: Section) -> dict:
    """Run the full pipeline; returns all result objects."""
    solution = solve(spec)
    diagrams = compute_diagrams(solution)
    check = check_stress(
        diagrams,
        section,
        spec.fy_mpa,
        spec.length_m,
        spec.deflection_limit_ratio,
    )
    return {
        "spec": spec,
        "section": section,
        "solution": solution,
        "diagrams": diagrams,
        "check": check,
    }


def metrics_dict(result: dict) -> dict:
    """Flat key numbers for JSON/CSV summaries."""
    spec = result["spec"]
    diagrams = result["diagrams"]
    check = result["check"]
    solution = result["solution"]
    m_max = max_abs_moment(diagrams)
    v_max = max_abs_shear(diagrams)
    return {
        "name": spec.name,
        "length_m": spec.length_m,
        "section": result["section"].name,
        "reactions_kN": [round(r.vertical_kn, 4) for r in solution.reactions],
        "reaction_moments_kNm": [
            round(r.moment_knm, 4) for r in solution.reactions
        ],
        "max_shear_kN": round(v_max.value, 4),
        "max_shear_x_m": round(v_max.x_m, 4),
        "max_moment_kNm": round(m_max.value, 4),
        "max_moment_x_m": round(m_max.x_m, 4),
        "min_moment_kNm": round(diagrams.min_moment.value, 4),
        "max_deflection_mm": round(diagrams.max_deflection.value, 4),
        "max_deflection_x_m": round(diagrams.max_deflection.x_m, 4),
        "sigma_max_MPa": round(check.sigma_max_mpa, 3),
        "sigma_allow_MPa": round(check.sigma_allow_mpa, 3),
        "bending_utilization": round(check.bending_utilization, 4),
        "tau_max_MPa": round(check.tau_max_mpa, 3),
        "shear_utilization": round(check.shear_utilization, 4),
        "phi_Mn_kNm": round(check.phi_mn_knm, 3),
        "demand_capacity_ratio": round(check.demand_capacity_ratio, 4),
        "delta_allow_mm": round(check.delta_allow_mm, 3),
        "verdict": check.verdict(),
        "equilibrium_force_residual_kN": solution.equilibrium_force_residual_kn,
        "equilibrium_moment_residual_kNm": solution.equilibrium_moment_residual_knm,
    }


def write_case_outputs(result: dict, out_dir: str | Path) -> dict[str, Path]:
    """Write report.md, report.html, diagram.png/svg and metrics.json.

    Returns a dict of role -> path.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    spec = result["spec"]
    diagrams = result["diagrams"]
    png = plot_diagrams(result["solution"], diagrams, str(out / "diagram.png"))
    svg = plot_diagrams(
        result["solution"], diagrams, str(out / "diagram.svg"), fmt="svg"
    )
    md = build_markdown(
        spec,
        result["section"],
        result["solution"],
        diagrams,
        result["check"],
        diagram_png_rel="diagram.png",
    )
    (out / "report.md").write_text(md, encoding="utf-8")
    html = build_html(
        spec,
        result["section"],
        result["solution"],
        diagrams,
        result["check"],
        diagram_svg_path=Path(svg),
    )
    (out / "report.html").write_text(html, encoding="utf-8")
    (out / "metrics.json").write_text(
        json.dumps(metrics_dict(result), indent=2), encoding="utf-8"
    )
    return {
        "report_md": out / "report.md",
        "report_html": out / "report.html",
        "diagram_png": Path(png),
        "diagram_svg": Path(svg),
        "metrics": out / "metrics.json",
    }


def run_batch(input_dir: str | Path, out_dir: str | Path) -> list[dict]:
    """Analyse every ``*.json`` case in ``input_dir``.

    Writes one output folder per case plus ``summary.csv`` in the
    output directory.  Returns the list of metric dicts.
    """
    in_dir = Path(input_dir)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for case_path in sorted(in_dir.glob("*.json")):
        spec, section = load_case(case_path)
        result = analyse(spec, section)
        write_case_outputs(result, out_root / spec.name)
        rows.append(metrics_dict(result))
    if rows:
        fieldnames = list(rows[0].keys())
        with open(out_root / "summary.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    return rows
