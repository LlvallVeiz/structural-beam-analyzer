"""Report generation tests -- Markdown and self-contained HTML."""

import pytest

from beam_analyzer.diagrams import plot_diagrams
from beam_analyzer.io import analyse, spec_from_dict
from beam_analyzer.report import build_html, build_markdown
from conftest import make_spec
from test_io import SS_CENTRAL
from beam_analyzer.model import PointLoad, Support
from beam_analyzer.sections import rectangular_section


def _result():
    spec, section = spec_from_dict(SS_CENTRAL)
    return analyse(spec, section)


def test_markdown_contains_key_results():
    r = _result()
    md = build_markdown(
        r["spec"], r["section"], r["solution"], r["diagrams"], r["check"]
    )
    assert "# Beam analysis report — ss-central-point" in md
    assert "W10x30" in md
    assert "Overall verdict: PASS" in md
    assert "5.000" in md  # reaction
    assert "15.000" in md  # Mmax
    assert "## Diagram values" in md
    assert "| 3.00 |" in md  # station at midspan


def test_markdown_includes_diagram_image_when_given():
    r = _result()
    md = build_markdown(
        r["spec"], r["section"], r["solution"], r["diagrams"], r["check"],
        diagram_png_rel="diagram.png",
    )
    assert "![Beam diagrams](diagram.png)" in md


def test_html_is_self_contained_with_svg(tmp_path):
    r = _result()
    svg = tmp_path / "diagram.svg"
    plot_diagrams(r["solution"], r["diagrams"], str(svg), fmt="svg")
    html = build_html(
        r["spec"], r["section"], r["solution"], r["diagrams"], r["check"],
        diagram_svg_path=svg,
    )
    assert html.startswith("<!DOCTYPE html>")
    assert "ss-central-point" in html
    assert "W10x30" in html
    assert "PASS" in html
    assert "<svg" in html  # diagram embedded inline
    assert "<table>" in html


def test_html_renders_without_diagram():
    r = _result()
    html = build_html(
        r["spec"], r["section"], r["solution"], r["diagrams"], r["check"]
    )
    assert html.startswith("<!DOCTYPE html>")
    assert "ss-central-point" in html


def test_markdown_reports_failure():
    # Cantilever, P = 50 kN: RECT 100x200 fails bending (see test_stress).
    section = rectangular_section(0.1, 0.2)
    spec = make_spec(
        "t-cant-fail", 4.0, [Support(0.0, "fixed")], [PointLoad(4.0, 50.0)],
        ix=section.Ix_m4,
    )
    from beam_analyzer.io import analyse as _analyse

    r = _analyse(spec, section)
    md = build_markdown(
        r["spec"], r["section"], r["solution"], r["diagrams"], r["check"]
    )
    assert "Overall verdict: FAIL" in md
    assert "300.00 MPa" in md  # sigma_max
