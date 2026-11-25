"""Deflection tests -- closed-form Euler-Bernoulli results
(EI = 20 000 kN*m^2 throughout)."""

import pytest

from beam_analyzer.model import DistributedLoad, PointLoad, Support
from conftest import EI_KNM2, make_spec, solve_diagrams, ss_supports

EI = EI_KNM2


def test_ss_central_point_deflection():
    # delta = P L^3 / (48 EI) = 2.25 mm.
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)]
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        10.0 * 216.0 / (48.0 * EI) * 1000.0, rel=1e-3
    )
    assert dia.max_deflection.x_m == pytest.approx(3.0, abs=0.02)


def test_ss_udl_deflection():
    # delta = 5 w L^4 / (384 EI) = 4.21875 mm.
    spec = make_spec(
        "t-ss-udl", 6.0, ss_supports(), None,
        [DistributedLoad(0.0, 6.0, 5.0, 5.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        5.0 * 5.0 * 1296.0 / (384.0 * EI) * 1000.0, rel=1e-3
    )


def test_cantilever_tip_deflection():
    # delta = P L^3 / (3 EI) = 8.5333 mm.
    spec = make_spec(
        "t-cant-tip", 4.0, [Support(0.0, "fixed")], [PointLoad(4.0, 8.0)]
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        8.0 * 64.0 / (3.0 * EI) * 1000.0, rel=1e-3
    )
    assert dia.max_deflection.x_m == pytest.approx(4.0, abs=0.02)


def test_cantilever_udl_deflection():
    # delta = w L^4 / (8 EI) = 4.8 mm.
    spec = make_spec(
        "t-cant-udl", 4.0, [Support(0.0, "fixed")], None,
        [DistributedLoad(0.0, 4.0, 3.0, 3.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        3.0 * 256.0 / (8.0 * EI) * 1000.0, rel=1e-3
    )


def test_fixed_fixed_central_deflection():
    # delta = P L^3 / (192 EI) = 0.675 mm.
    spec = make_spec(
        "t-ff-central", 6.0,
        [Support(0.0, "fixed"), Support(6.0, "fixed")],
        [PointLoad(3.0, 12.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        12.0 * 216.0 / (192.0 * EI) * 1000.0, rel=1e-3
    )


def test_fixed_fixed_udl_deflection():
    # delta = w L^4 / (384 EI) = 0.675 mm.
    spec = make_spec(
        "t-ff-udl", 6.0,
        [Support(0.0, "fixed"), Support(6.0, "fixed")], None,
        [DistributedLoad(0.0, 6.0, 4.0, 4.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        4.0 * 1296.0 / (384.0 * EI) * 1000.0, rel=1e-3
    )


def test_cantilever_triangular_deflection():
    # Triangular, 0 at the wall, w0 at the tip:
    # delta_tip = 11 w0 L^4 / (120 EI) = 9.3867 mm.
    spec = make_spec(
        "t-cant-tri", 4.0, [Support(0.0, "fixed")], None,
        [DistributedLoad(0.0, 4.0, 0.0, 8.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        11.0 * 8.0 * 256.0 / (120.0 * EI) * 1000.0, rel=1e-3
    )


def test_propped_cantilever_udl_deflection():
    # delta_max = 0.0054142 w L^4 / EI (exact coefficient) = 1.0152 mm.
    # The sampled Hermite maximum is ~0.2% high; allow 0.5%.
    spec = make_spec(
        "t-propped", 5.0,
        [Support(0.0, "fixed"), Support(5.0, "roller")], None,
        [DistributedLoad(0.0, 5.0, 6.0, 6.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_deflection.value == pytest.approx(
        0.0054142 * 6.0 * 625.0 / EI * 1000.0, rel=5e-3
    )


def test_deflection_zero_at_supports():
    spec = make_spec(
        "t-ss-udl", 6.0, ss_supports(), None,
        [DistributedLoad(0.0, 6.0, 5.0, 5.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.deflection_mm[0] == pytest.approx(0.0, abs=1e-9)
    assert dia.deflection_mm[-1] == pytest.approx(0.0, abs=1e-9)
    assert dia.max_upward_deflection.value == pytest.approx(0.0, abs=1e-9)
