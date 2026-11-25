"""Beam model: supports, loads and the beam specification.

Sign conventions (used everywhere in the package)
--------------------------------------------------
* x runs from the left end (0) to the right end (L), in metres.
* Vertical displacement v is positive upward; rotation theta is
  positive counter-clockwise.
* Point loads P and distributed intensities w are positive
  **downward**.  An applied moment is positive counter-clockwise.
* Reactions are reported positive upward (vertical) and
  counter-clockwise (moment).
* Internal shear V and bending moment M follow the convention
  dV/dx = -w and dM/dx = V, with M positive when sagging
  (bottom fibres in tension).
"""

from __future__ import annotations

from dataclasses import dataclass, field

SUPPORT_TYPES = ("pin", "roller", "fixed")
LOAD_TYPES = ("point", "udl", "triangular", "moment")

#: Default modulus of elasticity for structural steel, MPa
#: (AISC 360-16 Section B3: E = 200 000 MPa).
E_STEEL_MPA = 200_000.0
#: Default yield strength for ASTM A992 steel, MPa (50 ksi = 344.7 MPa).
FY_A992_MPA = 345.0


@dataclass(frozen=True)
class Support:
    """A support at position ``x_m``.

    ``kind`` is ``"pin"`` (vertical restraint), ``"roller"``
    (vertical restraint, free to move horizontally -- for a beam
    identical to a pin) or ``"fixed"`` (vertical + rotational
    restraint).
    """

    x_m: float
    kind: str

    def __post_init__(self) -> None:
        if self.kind not in SUPPORT_TYPES:
            raise ValueError(
                f"support kind must be one of {SUPPORT_TYPES}, got {self.kind!r}"
            )
        if self.x_m < 0:
            raise ValueError("support position must be >= 0")


@dataclass(frozen=True)
class PointLoad:
    """A concentrated vertical load, positive downward (kN)."""

    x_m: float
    p_kn: float


@dataclass(frozen=True)
class DistributedLoad:
    """A distributed load between ``x1_m`` and ``x2_m`` (kN/m, + down).

    ``w1`` is the intensity at ``x1_m`` and ``w2`` at ``x2_m``.
    ``w1 == w2`` is a uniform load; otherwise it varies linearly
    (triangular when one end is zero).
    """

    x1_m: float
    x2_m: float
    w1_kn_m: float
    w2_kn_m: float | None = None

    def __post_init__(self) -> None:
        if self.x2_m <= self.x1_m:
            raise ValueError("distributed load needs x2_m > x1_m")

    @property
    def w2(self) -> float:
        """Intensity at the right end (defaults to the left value)."""
        return self.w1_kn_m if self.w2_kn_m is None else self.w2_kn_m

    @property
    def is_uniform(self) -> bool:
        """True when the intensity is constant along the load."""
        return abs(self.w2 - self.w1_kn_m) < 1e-12

    def intensity_at(self, x_m: float) -> float:
        """Linearly interpolated intensity at ``x_m`` (kN/m)."""
        if x_m <= self.x1_m:
            return self.w1_kn_m
        if x_m >= self.x2_m:
            return self.w2
        t = (x_m - self.x1_m) / (self.x2_m - self.x1_m)
        return self.w1_kn_m + t * (self.w2 - self.w1_kn_m)

    def total_load_kn(self) -> float:
        """Resultant of the distributed load (kN)."""
        return 0.5 * (self.w1_kn_m + self.w2) * (self.x2_m - self.x1_m)


@dataclass(frozen=True)
class AppliedMoment:
    """A concentrated couple, positive counter-clockwise (kN*m)."""

    x_m: float
    m_knm: float


@dataclass
class BeamSpec:
    """Complete definition of one beam analysis case.

    Parameters
    ----------
    name:
        Case name, used in reports and file names.
    length_m:
        Span length in metres (single overall length; interior
        supports split it into spans).
    e_mpa:
        Modulus of elasticity in MPa.
    Ix_m4:
        Second moment of area about the bending axis, m^4.  When a
        ``section`` is supplied instead, ``Ix_m4`` is taken from it.
    supports:
        List of supports (at least two vertical restraints, and at
        least one of them must restrain rotation or be a pin -- a
        beam on two rollers is a mechanism in the horizontal sense
        only; vertical stability needs >= 2 vertical restraints).
    point_loads, distributed_loads, moments:
        Applied loads.
    fy_mpa:
        Yield strength of the material, MPa (for stress checks).
    include_self_weight:
        Add the section self-weight as a uniform load when a
        catalogued section with a known weight is used.
    deflection_limit_ratio:
        Allowable deflection expressed as span / ratio
        (e.g. 360 means L/360).
    """

    name: str
    length_m: float
    e_mpa: float = E_STEEL_MPA
    Ix_m4: float | None = None
    supports: list[Support] = field(default_factory=list)
    point_loads: list[PointLoad] = field(default_factory=list)
    distributed_loads: list[DistributedLoad] = field(default_factory=list)
    moments: list[AppliedMoment] = field(default_factory=list)
    fy_mpa: float = FY_A992_MPA
    include_self_weight: bool = False
    deflection_limit_ratio: float = 360.0
    section_name: str | None = None
    section_weight_kn_m: float = 0.0

    def __post_init__(self) -> None:
        if self.length_m <= 0:
            raise ValueError("beam length must be > 0")
        if self.e_mpa <= 0:
            raise ValueError("E must be > 0")
        if self.Ix_m4 is not None and self.Ix_m4 <= 0:
            raise ValueError("Ix must be > 0")
        if self.fy_mpa <= 0:
            raise ValueError("Fy must be > 0")
        if self.deflection_limit_ratio <= 0:
            raise ValueError("deflection limit ratio must be > 0")
        self.validate_supports()
        self.validate_loads()

    # -- validation -----------------------------------------------------
    def validate_supports(self) -> None:
        """Check the support set can carry vertical load."""
        if len(self.supports) < 1:
            raise ValueError("a beam needs at least one support")
        if len(self.supports) < 2 and not any(
            s.kind == "fixed" for s in self.supports
        ):
            raise ValueError(
                "a beam needs at least two supports (a single support "
                "is only valid when it is fixed, i.e. a cantilever)"
            )
        for s in self.supports:
            if not 0.0 <= s.x_m <= self.length_m:
                raise ValueError(
                    f"support at x={s.x_m} m is outside the beam "
                    f"[0, {self.length_m}]"
                )
        xs = sorted(s.x_m for s in self.supports)
        if len(self.supports) >= 2 and len(set(xs)) < 2:
            raise ValueError("supports must sit at two distinct positions")
        if xs[0] > 0.0 or xs[-1] < self.length_m:
            # Overhangs are allowed only when the extreme supports are
            # not at the ends; they are supported by the solver, but
            # warn the user through the check below only if the beam
            # would tip: a single vertical restraint at one end plus
            # an overhang is still stable when a fixed support exists.
            pass

    def validate_loads(self) -> None:
        """Check every load lies on the beam."""
        for p in self.point_loads:
            if not 0.0 <= p.x_m <= self.length_m:
                raise ValueError(f"point load at x={p.x_m} m is off the beam")
        for w in self.distributed_loads:
            if not (0.0 <= w.x1_m < w.x2_m <= self.length_m):
                raise ValueError(
                    f"distributed load [{w.x1_m}, {w.x2_m}] m is off the beam"
                )
        for m in self.moments:
            if not 0.0 <= m.x_m <= self.length_m:
                raise ValueError(f"applied moment at x={m.x_m} m is off the beam")

    # -- derived quantities ---------------------------------------------
    @property
    def EI_kn_m2(self) -> float:
        """Flexural rigidity EI in kN*m^2 (E in MPa = 1000 kN/m^2)."""
        if self.Ix_m4 is None:
            raise ValueError("Ix is not set on this beam")
        return self.e_mpa * 1000.0 * self.Ix_m4

    @property
    def spans(self) -> list[tuple[float, float]]:
        """(start, end) of each span between consecutive supports."""
        xs = sorted({s.x_m for s in self.supports})
        return [(xs[i], xs[i + 1]) for i in range(len(xs) - 1)]

    def self_weight_load(self) -> DistributedLoad | None:
        """Self-weight as a uniform load, or None when not requested."""
        if not self.include_self_weight or self.section_weight_kn_m <= 0:
            return None
        return DistributedLoad(
            0.0, self.length_m, self.section_weight_kn_m, self.section_weight_kn_m
        )
