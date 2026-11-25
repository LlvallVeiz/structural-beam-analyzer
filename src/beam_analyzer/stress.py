"""Stress checks for a solved beam.

Checks implemented (simplified, documented in docs/RESEARCH.md):

* Bending: sigma_max = |M|max / Sx  vs  sigma_allow = 0.66 * Fy
  (classic ASD value for a compact, laterally supported beam).
* Shear: tau_max = |V|max / A_web  vs  tau_allow = 0.40 * Fy
  (A_web = d * tw for W-shapes; full area for rectangles).
* LRFD flexural capacity (informational): phi*Mn = 0.9 * Zx * Fy,
  compared with the moment demand.
* Deflection: delta_max vs L / ratio (default L/360).

These are member-strength screening checks, NOT a full AISC 360
design: lateral-torsional buckling, local buckling, combined
axial load and connection design are out of scope and listed as
limitations in the README.
"""

from __future__ import annotations

from dataclasses import dataclass

from .diagrams import Diagrams, max_abs_moment, max_abs_shear
from .sections import Section

#: Default allowable bending stress as a fraction of Fy (ASD, compact).
DEFAULT_BENDING_FACTOR = 0.66
#: Default allowable shear stress as a fraction of Fy.
DEFAULT_SHEAR_FACTOR = 0.40
#: LRFD resistance factor for flexure (AISC 360-16 Ch. F).
PHI_BENDING = 0.90


@dataclass
class StressCheck:
    """Results of the stress and deflection checks."""

    sigma_max_mpa: float
    sigma_allow_mpa: float
    bending_utilization: float  # sigma_max / sigma_allow
    bending_ok: bool
    tau_max_mpa: float
    tau_allow_mpa: float
    shear_utilization: float
    shear_ok: bool
    phi_mn_knm: float  # LRFD flexural capacity 0.9*Zx*Fy
    moment_demand_knm: float
    demand_capacity_ratio: float  # |M|max / phi*Mn
    delta_max_mm: float
    delta_allow_mm: float
    deflection_ok: bool
    overall_ok: bool

    def verdict(self) -> str:
        """One-line verdict."""
        return "PASS" if self.overall_ok else "FAIL"


def check_stress(
    diagrams: Diagrams,
    section: Section,
    fy_mpa: float,
    span_m: float,
    deflection_limit_ratio: float = 360.0,
    bending_factor: float = DEFAULT_BENDING_FACTOR,
    shear_factor: float = DEFAULT_SHEAR_FACTOR,
) -> StressCheck:
    """Run bending, shear and deflection checks for one section."""
    m_max = max_abs_moment(diagrams)
    v_max = max_abs_shear(diagrams)

    # sigma (MPa) = M (kN*m) / S (m^3) / 1000  (1 MPa = 1000 kN/m^2).
    sigma_max = abs(m_max.value) / section.Sx_m3 / 1000.0
    sigma_allow = bending_factor * fy_mpa
    bending_util = sigma_max / sigma_allow if sigma_allow > 0 else float("inf")

    tau_max = abs(v_max.value) / section.shear_area_m2() / 1000.0
    tau_allow = shear_factor * fy_mpa
    shear_util = tau_max / tau_allow if tau_allow > 0 else float("inf")

    phi_mn = PHI_BENDING * section.Zx_m3 * fy_mpa * 1000.0  # kN*m
    dcr = abs(m_max.value) / phi_mn if phi_mn > 0 else float("inf")

    delta_max = diagrams.max_deflection.value
    delta_allow = span_m * 1000.0 / deflection_limit_ratio

    bending_ok = bending_util <= 1.0
    shear_ok = shear_util <= 1.0
    deflection_ok = delta_max <= delta_allow
    return StressCheck(
        sigma_max_mpa=sigma_max,
        sigma_allow_mpa=sigma_allow,
        bending_utilization=bending_util,
        bending_ok=bending_ok,
        tau_max_mpa=tau_max,
        tau_allow_mpa=tau_allow,
        shear_utilization=shear_util,
        shear_ok=shear_ok,
        phi_mn_knm=phi_mn,
        moment_demand_knm=abs(m_max.value),
        demand_capacity_ratio=dcr,
        delta_max_mm=delta_max,
        delta_allow_mm=delta_allow,
        deflection_ok=deflection_ok,
        overall_ok=bending_ok and shear_ok and deflection_ok,
    )
