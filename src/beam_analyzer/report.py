"""Report generation: Markdown and self-contained HTML."""

from __future__ import annotations

from pathlib import Path

from .diagrams import Diagrams, max_abs_moment, max_abs_shear
from .model import BeamSpec
from .sections import Section
from .solver import Solution
from .stress import StressCheck

_CSS = """
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
       max-width: 900px; margin: 2em auto; padding: 0 1em; color: #1a1a1a; }
h1, h2 { border-bottom: 2px solid #1f77b4; padding-bottom: 0.2em; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #bbb; padding: 0.35em 0.7em; text-align: right; }
th { background: #eef4fa; text-align: left; }
td:first-child, th:first-child { text-align: left; }
.pass { color: #1a7f37; font-weight: bold; }
.fail { color: #c0392b; font-weight: bold; }
img, svg { max-width: 100%; }
code { background: #f2f2f2; padding: 0 0.3em; }
"""


def _fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def build_markdown(
    spec: BeamSpec,
    section: Section,
    solution: Solution,
    diagrams: Diagrams,
    check: StressCheck,
    diagram_png_rel: str | None = None,
) -> str:
    """Render the full analysis report as Markdown."""
    m_max = max_abs_moment(diagrams)
    v_max = max_abs_shear(diagrams)
    lines: list[str] = []
    lines.append(f"# Beam analysis report — {spec.name}")
    lines.append("")
    lines.append(f"Span L = {spec.length_m:.3f} m; E = {spec.e_mpa:,.0f} MPa; "
                 f"Fy = {spec.fy_mpa:.0f} MPa.")
    lines.append(f"Section: **{section.name}** (Ix = {section.Ix_cm4:,.1f} cm^4, "
                 f"Sx = {section.Sx_cm3:,.1f} cm^3, source: {section.source}).")
    lines.append("")
    lines.append("## Supports and loads")
    lines.append("")
    lines.append("| Support | x (m) | Type |")
    lines.append("|---|---|---|")
    for s in spec.supports:
        lines.append(f"| S | {s.x_m:.3f} | {s.kind} |")
    if spec.point_loads:
        lines.append("")
        lines.append("| Point load | x (m) | P (kN) |")
        lines.append("|---|---|---|")
        for p in spec.point_loads:
            lines.append(f"| P | {p.x_m:.3f} | {p.p_kn:.3f} |")
    if spec.distributed_loads:
        lines.append("")
        lines.append("| Distributed load | x1 (m) | x2 (m) | w1 (kN/m) | w2 (kN/m) |")
        lines.append("|---|---|---|---|---|")
        for w in spec.distributed_loads:
            lines.append(
                f"| w | {w.x1_m:.3f} | {w.x2_m:.3f} | {w.w1_kn_m:.3f} | {w.w2:.3f} |"
            )
    if spec.moments:
        lines.append("")
        lines.append("| Applied moment | x (m) | M (kN*m) |")
        lines.append("|---|---|---|")
        for m in spec.moments:
            lines.append(f"| M | {m.x_m:.3f} | {m.m_knm:.3f} |")
    if spec.include_self_weight:
        lines.append("")
        lines.append(f"Self-weight of {section.name} "
                     f"({section.weight_kn_m:.4f} kN/m) included as a UDL.")
    lines.append("")
    lines.append("## Reactions")
    lines.append("")
    lines.append("| Support x (m) | Type | R vertical (kN) | M reaction (kN*m) |")
    lines.append("|---|---|---|---|")
    for r in solution.reactions:
        lines.append(
            f"| {r.x_m:.3f} | {r.kind} | {r.vertical_kn:.3f} | {r.moment_knm:.3f} |"
        )
    lines.append("")
    lines.append(f"Equilibrium check: force residual "
                 f"{solution.equilibrium_force_residual_kn:.2e} kN, moment residual "
                 f"{solution.equilibrium_moment_residual_knm:.2e} kN*m.")
    lines.append("")
    lines.append("## Key results")
    lines.append("")
    lines.append(f"- Max shear: **{v_max.value:.3f} kN** at x = {v_max.x_m:.3f} m")
    lines.append(f"- Max bending moment: **{m_max.value:.3f} kN*m** at x = {m_max.x_m:.3f} m")
    lines.append(f"- Min bending moment: **{diagrams.min_moment.value:.3f} kN*m** "
                 f"at x = {diagrams.min_moment.x_m:.3f} m")
    lines.append(f"- Max downward deflection: **{diagrams.max_deflection.value:.3f} mm** "
                 f"at x = {diagrams.max_deflection.x_m:.3f} m")
    if diagrams.max_upward_deflection.value > 1e-9:
        lines.append(f"- Max upward deflection: "
                     f"{diagrams.max_upward_deflection.value:.3f} mm at "
                     f"x = {diagrams.max_upward_deflection.x_m:.3f} m")
    lines.append("")
    lines.append("## Stress checks")
    lines.append("")
    lines.append("| Check | Demand | Allowable / capacity | Utilisation | Verdict |")
    lines.append("|---|---|---|---|---|")
    lines.append(
        f"| Bending stress | {check.sigma_max_mpa:.2f} MPa | "
        f"{check.sigma_allow_mpa:.2f} MPa | {check.bending_utilization:.3f} | "
        f"{'PASS' if check.bending_ok else 'FAIL'} |"
    )
    lines.append(
        f"| Shear stress | {check.tau_max_mpa:.2f} MPa | "
        f"{check.tau_allow_mpa:.2f} MPa | {check.shear_utilization:.3f} | "
        f"{'PASS' if check.shear_ok else 'FAIL'} |"
    )
    lines.append(
        f"| LRFD flexure | {check.moment_demand_knm:.2f} kN*m | "
        f"phi*Mn = {check.phi_mn_knm:.2f} kN*m | {check.demand_capacity_ratio:.3f} | "
        f"{'PASS' if check.demand_capacity_ratio <= 1.0 else 'FAIL'} |"
    )
    lines.append(
        f"| Deflection | {check.delta_max_mm:.2f} mm | "
        f"{check.delta_allow_mm:.2f} mm (L/{spec.deflection_limit_ratio:.0f}) | "
        f"{check.delta_max_mm / check.delta_allow_mm:.3f} | "
        f"{'PASS' if check.deflection_ok else 'FAIL'} |"
    )
    lines.append("")
    lines.append(f"**Overall verdict: {check.verdict()}**")
    lines.append("")
    lines.append("## Diagram values (stations every 0.5 m)")
    lines.append("")
    lines.append("| x (m) | V (kN) | M (kN*m) | delta (mm) |")
    lines.append("|---|---|---|---|")
    for row in diagrams.station_table(step_m=0.5):
        lines.append(
            f"| {row['x_m']:.2f} | {row['V_kN']:.3f} | {row['M_kNm']:.3f} | "
            f"{row['delta_mm']:.3f} |"
        )
    if diagram_png_rel:
        lines.append("")
        lines.append(f"![Beam diagrams]({diagram_png_rel})")
    lines.append("")
    lines.append("> Sign convention: V and M follow dV/dx = -w and dM/dx = V, "
                 "M positive when sagging. Deflection positive upward in the "
                 "table; the reported maximum is the largest downward value. "
                 "Euler-Bernoulli theory (no shear deformation).")
    return "\n".join(lines) + "\n"


def build_html(
    spec: BeamSpec,
    section: Section,
    solution: Solution,
    diagrams: Diagrams,
    check: StressCheck,
    diagram_svg_path: Path | None = None,
) -> str:
    """Render the report as a self-contained HTML page."""
    md = build_markdown(spec, section, solution, diagrams, check)
    body = []
    for line in md.splitlines():
        if line.startswith("# "):
            body.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("|"):
            body.append(line)
        elif line.startswith("- "):
            body.append(f"<li>{line[2:]}</li>")
        elif line.startswith("> "):
            body.append(f"<blockquote>{line[2:]}</blockquote>")
        elif line.strip() == "":
            body.append("")
        else:
            body.append(f"<p>{line}</p>")
    # Convert the simple pipe tables into real HTML tables.
    html_lines: list[str] = []
    i = 0
    while i < len(body):
        line = body[i]
        if line.startswith("|"):
            rows = []
            while i < len(body) and body[i].startswith("|"):
                cells = [c.strip() for c in body[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
            html_lines.append("<table>")
            for j, r in enumerate(rows):
                tag = "th" if j == 0 else "td"
                html_lines.append(
                    "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in r) + "</tr>"
                )
            html_lines.append("</table>")
            continue
        html_lines.append(line)
        i += 1
    svg_block = ""
    if diagram_svg_path is not None and diagram_svg_path.exists():
        svg_block = diagram_svg_path.read_text(encoding="utf-8")
    verdict_class = "pass" if check.overall_ok else "fail"
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<title>Beam analysis report — {spec.name}</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        + "\n".join(html_lines)
        + f"\n<p>Overall verdict: <span class=\"{verdict_class}\">"
        f"{check.verdict()}</span></p>\n"
        + (svg_block + "\n" if svg_block else "")
        + "</body>\n</html>\n"
    )
