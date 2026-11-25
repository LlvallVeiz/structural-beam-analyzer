"""Shear / moment diagram tests -- key values from closed-form
bending-moment expressions."""

import math

import pytest

from beam_analyzer.diagrams import max_abs_moment, max_abs_shear
from beam_analyzer.model import AppliedMoment, DistributedLoad, PointLoad, Support
from conftest import make_spec, solve_diagrams, ss_supports


def test_ss_central_point_diagram():
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)]
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_moment.value == pytest.approx(15.0)  # PL/4
    assert dia.max_moment.x_m == pytest.approx(3.0, abs=0.01)
    assert dia.min_moment.value == pytest.approx(0.0, abs=1e-6)
    assert dia.max_shear.value == pytest.approx(5.0)
    assert dia.min_shear.value == pytest.approx(-5.0)


def test_ss_udl_diagram():
    spec = make_spec(
        "t-ss-udl", 6.0, ss_supports(), None,
        [DistributedLoad(0.0, 6.0, 5.0, 5.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_moment.value == pytest.approx(22.5)  # wL^2/8
    assert dia.max_moment.x_m == pytest.approx(3.0, abs=0.01)
    assert dia.max_shear.value == pytest.approx(15.0)
    assert dia.min_shear.value == pytest.approx(-15.0)


def test_cantilever_udl_diagram():
    spec = make_spec(
        "t-cant-udl", 4.0, [Support(0.0, "fixed")], None,
        [DistributedLoad(0.0, 4.0, 3.0, 3.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.min_moment.value == pytest.approx(-24.0)  # -wL^2/2
    assert dia.min_moment.x_m == pytest.approx(0.0, abs=0.01)
    assert dia.max_moment.value == pytest.approx(0.0, abs=1e-6)
    assert max_abs_moment(dia).value == pytest.approx(-24.0)
    assert max_abs_shear(dia).value == pytest.approx(12.0)


def test_fixed_fixed_udl_diagram():
    spec = make_spec(
        "t-ff-udl", 6.0,
        [Support(0.0, "fixed"), Support(6.0, "fixed")], None,
        [DistributedLoad(0.0, 6.0, 4.0, 4.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_moment.value == pytest.approx(6.0, rel=1e-3)  # +wL^2/24
    assert dia.min_moment.value == pytest.approx(-12.0, rel=1e-3)  # -wL^2/12


def test_ss_triangular_diagram():
    # Triangular 0 -> 6 kN/m: Mmax = w0 L^2 / (9 sqrt 3) at x = L/sqrt 3.
    spec = make_spec(
        "t-ss-tri", 6.0, ss_supports(), None,
        [DistributedLoad(0.0, 6.0, 0.0, 6.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_moment.value == pytest.approx(
        6.0 * 36.0 / (9.0 * math.sqrt(3.0)), rel=1e-3
    )
    assert dia.max_moment.x_m == pytest.approx(6.0 / math.sqrt(3.0), abs=0.02)


def test_station_table_values():
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)]
    )
    _, dia = solve_diagrams(spec)
    rows = dia.station_table(step_m=0.5)
    assert len(rows) == 13  # 0.0, 0.5, ..., 6.0
    assert rows[0]["x_m"] == pytest.approx(0.0)
    assert rows[0]["V_kN"] == pytest.approx(5.0)
    assert rows[0]["M_kNm"] == pytest.approx(0.0, abs=1e-6)
    assert rows[0]["delta_mm"] == pytest.approx(0.0, abs=1e-6)
    assert rows[6]["x_m"] == pytest.approx(3.0)
    assert rows[6]["M_kNm"] == pytest.approx(15.0)
    assert rows[-1]["x_m"] == pytest.approx(6.0)
    assert rows[-1]["M_kNm"] == pytest.approx(0.0, abs=1e-6)


def test_applied_moment_jumps_moment_diagram():
    # CCW 12 kN*m at midspan: M jumps from +6 to -6 across x = 3.
    spec = make_spec(
        "t-ss-moment", 6.0, ss_supports(), None, None,
        [AppliedMoment(3.0, 12.0)],
    )
    _, dia = solve_diagrams(spec)
    assert dia.max_moment.value == pytest.approx(6.0)
    assert dia.min_moment.value == pytest.approx(-6.0)
