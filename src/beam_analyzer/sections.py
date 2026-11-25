"""Steel section catalogue.

Section properties come from the AISC Steel Construction Manual,
16th Edition, Tables 1-1 (AISC Shapes Database v16.0), stored in
``data/sections_aisc.json``.  Values were cross-checked against the
AISC reference tables republished by steelcalculator.app on
2026-11-25 (W8x31, W10x22, W10x30, W12x26, W12x40, W14x48, W18x40,
W21x44, W24x68 all match the published table exactly).

Only strong-axis bending properties are catalogued (the use case of
this tool).  A rectangular section can be defined directly for
custom cross-sections.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .units import (
    IN_TO_M,
    in2_to_m2,
    in3_to_m3,
    in4_to_m4,
    lb_ft_to_kn_m,
)

_DATA_PATH = Path(__file__).resolve().parent / "data" / "sections_aisc.json"


@dataclass(frozen=True)
class Section:
    """A beam cross-section with everything the solver needs (SI units).

    Attributes
    ----------
    name:
        Designation, e.g. ``"W12x26"`` or ``"RECT 200x400"``.
    Ix_m4:
        Second moment of area about the strong (bending) axis, m^4.
    Sx_m3:
        Elastic section modulus about the strong axis, m^3.
    Zx_m3:
        Plastic section modulus about the strong axis, m^3.
    area_m2:
        Cross-sectional area, m^2.
    depth_m:
        Overall depth of the section, m.
    web_area_m2:
        Web area used for the average shear-stress check
        (d * tw for W-shapes, full area for rectangles).
    weight_kn_m:
        Self-weight per unit length, kN/m.
    source:
        Where the properties came from.
    """

    name: str
    Ix_m4: float
    Sx_m3: float
    Zx_m3: float
    area_m2: float
    depth_m: float
    web_area_m2: float
    weight_kn_m: float
    source: str

    @property
    def Ix_cm4(self) -> float:
        """Moment of inertia in cm^4 (handy for reporting)."""
        return self.Ix_m4 * 1e8

    @property
    def Sx_cm3(self) -> float:
        """Elastic section modulus in cm^3."""
        return self.Sx_m3 * 1e6

    def shear_area_m2(self) -> float:
        """Area resisting shear (web area for I-shapes)."""
        return self.web_area_m2


def _load_aisc() -> dict[str, dict]:
    with open(_DATA_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    return {row["designation"].upper(): row for row in data["shapes"]}


_AISC = _load_aisc()


def list_sections() -> list[str]:
    """Designations available in the AISC catalogue, lightest first."""
    return [
        _AISC[key]["designation"]
        for key in sorted(_AISC, key=lambda d: _AISC[d]["weight_lb_ft"])
    ]


def get_section(designation: str) -> Section:
    """Look up an AISC W-shape by designation (case-insensitive).

    Raises
    ------
    KeyError
        If the designation is not in the catalogue.
    """
    lookup = designation.strip().upper()
    for stored in _AISC:
        if stored.upper() == lookup:
            row = _AISC[stored]
            break
    else:
        raise KeyError(
            f"section {designation!r} not in AISC catalogue; "
            f"available: {', '.join(list_sections())}"
        )
    d_m = row["d_in"] * IN_TO_M
    tw_m = row["tw_in"] * IN_TO_M
    return Section(
        name=row["designation"],
        Ix_m4=in4_to_m4(row["Ix_in4"]),
        Sx_m3=in3_to_m3(row["Sx_in3"]),
        Zx_m3=in3_to_m3(row["Zx_in3"]),
        area_m2=in2_to_m2(row["A_in2"]),
        depth_m=d_m,
        web_area_m2=d_m * tw_m,
        weight_kn_m=lb_ft_to_kn_m(row["weight_lb_ft"]),
        source="AISC Steel Construction Manual, 16th Edition, Table 1-1",
    )


def rectangular_section(
    width_m: float, height_m: float, name: str | None = None
) -> Section:
    """A solid rectangular section (e.g. timber or a built-up plate).

    Bending about the strong axis (height vertical).
    """
    if width_m <= 0 or height_m <= 0:
        raise ValueError("rectangular section width and height must be > 0")
    b, h = width_m, height_m
    area = b * h
    Ix = b * h ** 3 / 12.0
    Sx = b * h ** 2 / 6.0
    Zx = b * h ** 2 / 4.0
    return Section(
        name=name or f"RECT {b * 1000:.0f}x{h * 1000:.0f}",
        Ix_m4=Ix,
        Sx_m3=Sx,
        Zx_m3=Zx,
        area_m2=area,
        depth_m=h,
        web_area_m2=area,
        weight_kn_m=0.0,
        source="computed from rectangular geometry (I=bh^3/12, S=bh^2/6)",
    )


def required_section_modulus(
    moment_knm: float, fy_mpa: float, factor: float = 0.66
) -> float:
    """Required elastic section modulus (m^3) for a moment demand.

    ``factor`` is the allowable-stress fraction of the yield strength
    (default 0.66, the classic ASD value for compact beams).
    """
    sigma_allow_mpa = factor * fy_mpa
    # M (kN*m) / sigma (kN/m^2) -> m^3; 1 MPa = 1000 kN/m^2.
    return abs(moment_knm) / (sigma_allow_mpa * 1000.0)


def lightest_section_for(moment_knm: float, fy_mpa: float) -> Section:
    """Lightest catalogued W-shape whose Sx meets the moment demand."""
    s_req = required_section_modulus(moment_knm, fy_mpa)
    candidates = [get_section(d) for d in list_sections()]
    ok = [s for s in candidates if s.Sx_m3 >= s_req]
    if not ok:
        raise ValueError(
            f"no catalogued section provides Sx >= {s_req * 1e6:.1f} cm^3 "
            f"for M = {moment_knm:.1f} kN*m at Fy = {fy_mpa:.0f} MPa"
        )
    return ok[0]


def radius_of_gyration_m(I_m4: float, A_m2: float) -> float:
    """r = sqrt(I / A)."""
    return math.sqrt(I_m4 / A_m2)
