"""Shared fixtures and builders for the beam-analyzer test suite.

Every test uses E = 200 000 MPa and (unless a real section is used)
Ix = 1.0e-4 m^4, so EI = 20 000 kN*m^2 -- the same convention as
``beam_analyzer check``.
"""

from __future__ import annotations

import pytest

from beam_analyzer.diagrams import compute_diagrams
from beam_analyzer.model import (
    AppliedMoment,
    BeamSpec,
    DistributedLoad,
    PointLoad,
    Support,
)
from beam_analyzer.sections import get_section
from beam_analyzer.solver import solve

#: Flexural rigidity used by the hand-calculation cases, kN*m^2.
EI_KNM2 = 20_000.0


@pytest.fixture(scope="session")
def w10x30():
    """AISC W10x30 section (Ix = 170 in^4, Sx = 32.4 in^3)."""
    return get_section("W10x30")


@pytest.fixture(scope="session")
def w12x26():
    """AISC W12x26 section."""
    return get_section("W12x26")


def make_spec(
    name: str,
    length: float,
    supports: list[Support],
    point_loads: list[PointLoad] | None = None,
    distributed: list[DistributedLoad] | None = None,
    moments: list[AppliedMoment] | None = None,
    ix: float = 1.0e-4,
    **kwargs,
) -> BeamSpec:
    """Build a BeamSpec with the standard E = 200 000 MPa."""
    return BeamSpec(
        name=name,
        length_m=length,
        e_mpa=200_000.0,
        Ix_m4=ix,
        supports=supports,
        point_loads=point_loads or [],
        distributed_loads=distributed or [],
        moments=moments or [],
        **kwargs,
    )


def ss_supports(length: float = 6.0) -> list[Support]:
    """Pin at 0, roller at the far end."""
    return [Support(0.0, "pin"), Support(length, "roller")]


def solve_diagrams(spec: BeamSpec):
    """Solve a spec and return (solution, diagrams)."""
    solution = solve(spec)
    return solution, compute_diagrams(solution)
