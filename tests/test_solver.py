"""Solver / model tests -- meshing, validation, overhangs,
partial loads and self-weight."""

import pytest

from beam_analyzer.model import (
    BeamSpec,
    DistributedLoad,
    PointLoad,
    Support,
)
from beam_analyzer.solver import solve
from conftest import make_spec, solve_diagrams, ss_supports


def test_nodes_include_supports_and_load_points():
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)]
    )
    sol = solve(spec)
    nodes = sol.nodes_x_m
    assert 0.0 in nodes
    assert 3.0 in nodes
    assert 6.0 in nodes
    # The mesh is refined well beyond the critical points.
    assert 50 < len(sol.elements) <= 600


def test_elements_span_the_beam_without_gaps():
    spec = make_spec(
        "t-ss-udl", 6.0, ss_supports(), None,
        [DistributedLoad(0.0, 6.0, 5.0, 5.0)],
    )
    sol = solve(spec)
    assert sol.elements[0].x1_m == pytest.approx(0.0)
    assert sol.elements[-1].x1_m + sol.elements[-1].length_m == pytest.approx(6.0)
    for a, b in zip(sol.elements[:-1], sol.elements[1:]):
        assert a.x1_m + a.length_m == pytest.approx(b.x1_m)


def test_overhang_point_load():
    # Supports at 0 and 5 m, 1 m overhang, P = 10 kN at the tip:
    # R_0 = -P*1/5 = -2 kN (uplift), R_5 = 12 kN.
    spec = make_spec(
        "t-overhang", 6.0,
        [Support(0.0, "pin"), Support(5.0, "roller")],
        [PointLoad(6.0, 10.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx([-2.0, 12.0])


def test_partial_udl():
    # UDL w = 10 kN/m over [2, 4] m on a 6 m SS beam: resultant 20 kN
    # at midspan, so R = 10 kN each; M(3) = 10*3 - 10*1*0.5 = 25 kN*m.
    spec = make_spec(
        "t-partial", 6.0, ss_supports(), None,
        [DistributedLoad(2.0, 4.0, 10.0, 10.0)],
    )
    sol, dia = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx([10.0, 10.0])
    assert dia.max_moment.value == pytest.approx(25.0, rel=1e-3)


def test_self_weight_of_section(w12x26):
    # W12x26 weighs 0.3794 kN/m; SS beam L = 6 m -> R = wL/2 each.
    spec = make_spec(
        "t-sw", 6.0, ss_supports(), None, None, None,
        ix=w12x26.Ix_m4, include_self_weight=True,
        section_weight_kn_m=w12x26.weight_kn_m,
    )
    sol, _ = solve_diagrams(spec)
    expected = w12x26.weight_kn_m * 6.0 / 2.0
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx(
        [expected, expected], rel=1e-6
    )


def test_single_roller_is_invalid():
    with pytest.raises(ValueError):
        make_spec("t-bad", 6.0, [Support(0.0, "roller")])


def test_single_pin_is_invalid():
    with pytest.raises(ValueError):
        make_spec("t-bad", 6.0, [Support(0.0, "pin")])


def test_single_fixed_support_is_a_cantilever():
    spec = make_spec(
        "t-cant", 4.0, [Support(0.0, "fixed")], [PointLoad(4.0, 8.0)]
    )
    sol, _ = solve_diagrams(spec)
    assert sol.reactions[0].vertical_kn == pytest.approx(8.0)


def test_load_off_beam_is_invalid():
    with pytest.raises(ValueError):
        make_spec("t-bad", 6.0, ss_supports(), [PointLoad(7.0, 10.0)])
    with pytest.raises(ValueError):
        make_spec(
            "t-bad", 6.0, ss_supports(), None,
            [DistributedLoad(5.0, 7.0, 1.0, 1.0)],
        )


def test_bad_support_kind_and_dimensions():
    with pytest.raises(ValueError):
        Support(0.0, "spring")
    with pytest.raises(ValueError):
        BeamSpec(name="t-bad", length_m=-1.0, supports=ss_supports())
    with pytest.raises(ValueError):
        BeamSpec(name="t-bad", length_m=6.0, e_mpa=0.0, supports=ss_supports())
    with pytest.raises(ValueError):
        DistributedLoad(4.0, 2.0, 1.0, 1.0)


def test_total_loads_match_reactions():
    spec = make_spec(
        "t-ss-udl", 6.0, ss_supports(), [PointLoad(3.0, 10.0)],
        [DistributedLoad(0.0, 6.0, 5.0, 5.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert sol.total_downward_load_kn == pytest.approx(40.0)
    assert sol.total_upward_reaction_kn == pytest.approx(40.0)
