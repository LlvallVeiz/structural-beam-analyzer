"""Stress-check tests -- sigma = M/S, tau = V/A_web, phi*Mn = 0.9 Zx Fy."""

import pytest

from beam_analyzer.model import DistributedLoad, PointLoad, Support
from beam_analyzer.sections import Section, rectangular_section
from beam_analyzer.stress import check_stress
from conftest import make_spec, solve_diagrams, ss_supports


def _check(spec, section, **kwargs):
    _, dia = solve_diagrams(spec)
    return check_stress(
        dia, section, spec.fy_mpa, spec.length_m,
        spec.deflection_limit_ratio, **kwargs,
    )


def test_bending_stress_w10x30(w10x30):
    # SS beam, P = 10 kN central: Mmax = 15 kN*m.
    # sigma = 15 / Sx ; Sx(W10x30) = 32.4 in^3 = 5.309e-4 m^3 -> 28.25 MPa.
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)],
        ix=w10x30.Ix_m4,
    )
    check = _check(spec, w10x30)
    assert check.sigma_max_mpa == pytest.approx(28.25, rel=1e-3)
    assert check.sigma_allow_mpa == pytest.approx(0.66 * 345.0)
    assert check.bending_utilization == pytest.approx(28.25 / 227.7, rel=1e-3)
    assert check.bending_ok is True
    # phi*Mn = 0.9 * Zx * Fy; Zx = 36.6 in^3 -> 186.2 kN*m.
    assert check.phi_mn_knm == pytest.approx(186.2, rel=1e-3)
    assert check.demand_capacity_ratio == pytest.approx(15.0 / 186.2, rel=1e-3)
    assert check.verdict() == "PASS"
    assert check.overall_ok is True


def test_shear_stress_w10x30(w10x30):
    # SS beam, UDL w = 5: Vmax = 15 kN; A_web = d*tw = 2.026e-3 m^2.
    spec = make_spec(
        "t-ss-udl", 6.0, ss_supports(), None,
        [DistributedLoad(0.0, 6.0, 5.0, 5.0)], ix=w10x30.Ix_m4,
    )
    check = _check(spec, w10x30)
    assert check.tau_max_mpa == pytest.approx(7.40, rel=1e-2)
    assert check.tau_allow_mpa == pytest.approx(0.40 * 345.0)
    assert check.shear_ok is True


def test_bending_failure_small_rectangle():
    # Cantilever, P = 50 kN at 4 m: M = 200 kN*m.
    # RECT 100x200: Sx = 6.667e-4 m^3 -> sigma = 300 MPa > 227.7 MPa.
    section = rectangular_section(0.1, 0.2)
    spec = make_spec(
        "t-cant-fail", 4.0, [Support(0.0, "fixed")], [PointLoad(4.0, 50.0)],
        ix=section.Ix_m4,
    )
    check = _check(spec, section)
    assert check.sigma_max_mpa == pytest.approx(300.0, rel=1e-3)
    assert check.bending_ok is False
    assert check.overall_ok is False
    assert check.verdict() == "FAIL"


def test_deflection_failure_flexible_section():
    # Very flexible custom section (Ix = 1e-6 m^4, big Sx so bending
    # passes): SS central P = 10 kN -> delta = 225 mm > L/360 = 16.67 mm.
    section = Section(
        name="FLEX", Ix_m4=1.0e-6, Sx_m3=1.0e-3, Zx_m3=1.2e-3,
        area_m2=0.01, depth_m=0.4, web_area_m2=0.008, weight_kn_m=0.0,
        source="test",
    )
    spec = make_spec(
        "t-flex", 6.0, ss_supports(), [PointLoad(3.0, 10.0)], ix=1.0e-6
    )
    check = _check(spec, section)
    assert check.bending_ok is True
    assert check.delta_max_mm == pytest.approx(225.0, rel=1e-3)
    assert check.delta_allow_mm == pytest.approx(6000.0 / 360.0)
    assert check.deflection_ok is False
    assert check.overall_ok is False


def test_custom_allowable_factors(w10x30):
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)],
        ix=w10x30.Ix_m4,
    )
    check = _check(spec, w10x30, bending_factor=0.5, shear_factor=0.3)
    assert check.sigma_allow_mpa == pytest.approx(0.5 * 345.0)
    assert check.tau_allow_mpa == pytest.approx(0.3 * 345.0)


def test_deflection_limit_ratio_option(w10x30):
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)],
        ix=w10x30.Ix_m4, deflection_limit_ratio=180.0,
    )
    check = _check(spec, w10x30)
    assert check.delta_allow_mm == pytest.approx(6000.0 / 180.0)
