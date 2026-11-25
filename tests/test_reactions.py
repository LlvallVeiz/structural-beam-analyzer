"""Reaction tests -- every value is a hand calculation or a
textbook result (Gere & Goodno, Hibbeler; see docs/RESEARCH.md)."""

import pytest

from beam_analyzer.model import AppliedMoment, DistributedLoad, PointLoad, Support
from conftest import make_spec, solve_diagrams, ss_supports


def test_ss_central_point_load():
    spec = make_spec(
        "t-ss-central", 6.0, ss_supports(), [PointLoad(3.0, 10.0)]
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx([5.0, 5.0])


def test_ss_uniform_load():
    spec = make_spec(
        "t-ss-udl", 6.0, ss_supports(), None,
        [DistributedLoad(0.0, 6.0, 5.0, 5.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx([15.0, 15.0])


def test_cantilever_tip_load():
    spec = make_spec(
        "t-cant-tip", 4.0, [Support(0.0, "fixed")], [PointLoad(4.0, 8.0)]
    )
    sol, _ = solve_diagrams(spec)
    assert sol.reactions[0].vertical_kn == pytest.approx(8.0)
    # Wall moment (CCW +) balances PL = 32 kN*m clockwise.
    assert sol.reactions[0].moment_knm == pytest.approx(32.0)


def test_fixed_fixed_central_load():
    spec = make_spec(
        "t-ff-central", 6.0,
        [Support(0.0, "fixed"), Support(6.0, "fixed")],
        [PointLoad(3.0, 12.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx([6.0, 6.0])
    # End moments PL/8 = 9 kN*m, opposite senses at the two walls.
    assert [r.moment_knm for r in sol.reactions] == pytest.approx([9.0, -9.0])


def test_propped_cantilever_udl():
    # R_wall = 5wL/8, R_prop = 3wL/8 (w = 6, L = 5).
    spec = make_spec(
        "t-propped", 5.0,
        [Support(0.0, "fixed"), Support(5.0, "roller")], None,
        [DistributedLoad(0.0, 5.0, 6.0, 6.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx(
        [18.75, 11.25], rel=1e-3
    )
    assert sol.reactions[0].moment_knm == pytest.approx(18.75, rel=1e-3)


def test_continuous_two_span_udl():
    # Two equal spans L = 4 m, w = 5 kN/m:
    # R_end = 3wL/8, R_mid = 5wL/4.
    spec = make_spec(
        "t-cont", 8.0,
        [Support(0.0, "pin"), Support(4.0, "roller"),
         Support(8.0, "roller")], None,
        [DistributedLoad(0.0, 8.0, 5.0, 5.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx(
        [7.5, 25.0, 7.5], rel=1e-3
    )


def test_ss_eccentric_point_load():
    # P = 10 kN at a = 2 m from the left (b = 4 m): R_L = Pb/L.
    spec = make_spec(
        "t-ss-ecc", 6.0, ss_supports(), [PointLoad(2.0, 10.0)]
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx(
        [40.0 / 6.0, 20.0 / 6.0]
    )


def test_ss_midspan_applied_moment():
    # CCW couple M0 = 12 kN*m at midspan: R_L = +M0/L, R_R = -M0/L.
    spec = make_spec(
        "t-ss-moment", 6.0, ss_supports(), None, None,
        [AppliedMoment(3.0, 12.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert [r.vertical_kn for r in sol.reactions] == pytest.approx([2.0, -2.0])


def test_equilibrium_residuals_are_zero():
    spec = make_spec(
        "t-eq", 6.0,
        [Support(0.0, "fixed"), Support(6.0, "fixed")], None,
        [DistributedLoad(0.0, 6.0, 4.0, 4.0)],
    )
    sol, _ = solve_diagrams(spec)
    assert sol.equilibrium_force_residual_kn == pytest.approx(0.0, abs=1e-6)
    assert sol.equilibrium_moment_residual_knm == pytest.approx(0.0, abs=1e-6)
    # Total applied load equals total reaction.
    assert sol.total_downward_load_kn == pytest.approx(24.0)
    assert sol.total_upward_reaction_kn == pytest.approx(24.0)
