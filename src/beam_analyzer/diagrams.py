"""Shear, moment and deflection diagrams from a solved beam.

All diagram values are computed from the finite-element solution:
element end forces give the shear and moment at element ends, and
inside an element V and M follow from the local distributed load
(dV/dx = -w, dM/dx = V).  Deflection inside an element is the cubic
Hermite interpolation of the nodal displacements and rotations.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .solver import Solution

# Sampling density per element for diagrams and key-value search.
_SAMPLES_PER_ELEMENT = 25


@dataclass
class Extremum:
    """A maximum/minimum value with its location."""

    value: float
    x_m: float


@dataclass
class Diagrams:
    """Sampled diagrams plus key values."""

    x_m: np.ndarray
    shear_kn: np.ndarray
    moment_knm: np.ndarray
    deflection_mm: np.ndarray
    max_shear: Extremum
    min_shear: Extremum
    max_moment: Extremum
    min_moment: Extremum
    max_deflection: Extremum  # largest downward deflection (positive mm)
    max_upward_deflection: Extremum  # largest upward deflection (mm)

    def station_table(self, step_m: float = 0.5) -> list[dict]:
        """Diagram values at regular stations (for reports)."""
        rows: list[dict] = []
        x = 0.0
        spec = None
        while x <= self.x_m[-1] + 1e-9:
            idx = int(np.argmin(np.abs(self.x_m - min(x, self.x_m[-1]))))
            rows.append(
                {
                    "x_m": float(self.x_m[idx]),
                    "V_kN": float(self.shear_kn[idx]),
                    "M_kNm": float(self.moment_knm[idx]),
                    "delta_mm": float(self.deflection_mm[idx]),
                }
            )
            x += step_m
        return rows


def _hermite(xi: float, v1: float, th1: float, v2: float, th2: float, L: float) -> float:
    """Cubic Hermite interpolation of deflection at local coordinate xi."""
    N1 = 1.0 - 3.0 * xi ** 2 + 2.0 * xi ** 3
    N2 = L * (xi - 2.0 * xi ** 2 + xi ** 3)
    N3 = 3.0 * xi ** 2 - 2.0 * xi ** 3
    N4 = L * (-xi ** 2 + xi ** 3)
    return N1 * v1 + N2 * th1 + N3 * v2 + N4 * th2


def _element_diagrams(
    el, n_samples: int = _SAMPLES_PER_ELEMENT
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sample x, V, M and deflection inside one element.

    V(x) = V1 - int_0^x w(s) ds
    M(x) = M1 + int_0^x V(s) ds
    with w linear between the element end intensities.
    """
    L = el.length_m
    V1 = el.shear_left_kn
    M1 = el.moment_left_knm
    w1, w2 = el.w1_kn_m, el.w2_kn_m
    xi = np.linspace(0.0, 1.0, n_samples)
    x = el.x1_m + xi * L
    # Integral of w from 0 to xi*L: L*(w1*xi + (w2-w1)*xi^2/2).
    int_w = L * (w1 * xi + 0.5 * (w2 - w1) * xi ** 2)
    V = V1 - int_w
    # M(x) = M1 + V1*x - int_0^x w(s)*(x-s) ds;
    # int_0^x w(s)*(x-s) ds = L^2*(w1*xi^2/2 + (w2-w1)*xi^3/6).
    int_wx = L ** 2 * (w1 * xi ** 2 / 2.0 + (w2 - w1) * xi ** 3 / 6.0)
    M = M1 + V1 * (xi * L) - int_wx
    v = np.array(
        [
            _hermite(t, el.u[0], el.u[1], el.u[2], el.u[3], L)
            for t in xi
        ]
    )
    return x, V, M, v * 1000.0  # deflection in mm


def compute_diagrams(solution: Solution) -> Diagrams:
    """Build full-length sampled diagrams and key values."""
    xs: list[np.ndarray] = []
    Vs: list[np.ndarray] = []
    Ms: list[np.ndarray] = []
    ds: list[np.ndarray] = []
    for el in solution.elements:
        x, V, M, v = _element_diagrams(el)
        xs.append(x)
        Vs.append(V)
        Ms.append(M)
        ds.append(v)
    x_all = np.concatenate(xs)
    V_all = np.concatenate(Vs)
    M_all = np.concatenate(Ms)
    d_all = np.concatenate(ds)

    # Downward deflection is positive in the reported maximum:
    # v is up +, so downward deflection = -v.
    down = -d_all
    i_vmax = int(np.argmax(V_all))
    i_vmin = int(np.argmin(V_all))
    i_mmax = int(np.argmax(M_all))
    i_mmin = int(np.argmin(M_all))
    i_dmax = int(np.argmax(down))
    i_dmin = int(np.argmin(down))
    return Diagrams(
        x_m=x_all,
        shear_kn=V_all,
        moment_knm=M_all,
        deflection_mm=d_all,
        max_shear=Extremum(float(V_all[i_vmax]), float(x_all[i_vmax])),
        min_shear=Extremum(float(V_all[i_vmin]), float(x_all[i_vmin])),
        max_moment=Extremum(float(M_all[i_mmax]), float(x_all[i_mmax])),
        min_moment=Extremum(float(M_all[i_mmin]), float(x_all[i_mmin])),
        max_deflection=Extremum(float(down[i_dmax]), float(x_all[i_dmax])),
        max_upward_deflection=Extremum(
            float(-down[i_dmin]), float(x_all[i_dmin])
        ),
    )


def max_abs_moment(diagrams: Diagrams) -> Extremum:
    """Largest absolute bending moment with its location and sign.

    On a tie (e.g. a symmetric diagram with +M and -M of equal
    magnitude) the positive extremum is returned, so the result is
    deterministic despite floating-point noise.
    """
    tol = 1e-9 * max(1.0, abs(diagrams.max_moment.value),
                     abs(diagrams.min_moment.value))
    if abs(diagrams.max_moment.value) >= abs(diagrams.min_moment.value) - tol:
        return diagrams.max_moment
    return diagrams.min_moment


def max_abs_shear(diagrams: Diagrams) -> Extremum:
    """Largest absolute shear force with its location and sign.

    On a tie the positive extremum is returned (see max_abs_moment).
    """
    tol = 1e-9 * max(1.0, abs(diagrams.max_shear.value),
                     abs(diagrams.min_shear.value))
    if abs(diagrams.max_shear.value) >= abs(diagrams.min_shear.value) - tol:
        return diagrams.max_shear
    return diagrams.min_shear


def plot_diagrams(
    solution: Solution,
    diagrams: Diagrams,
    path: str,
    fmt: str = "png",
) -> str:
    """Save a three-panel shear / moment / deflection plot.

    Returns the path written.  ``fmt`` is ``"png"`` or ``"svg"``.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    L = solution.spec.length_m
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    fig.suptitle(f"Beam diagrams — {solution.spec.name}", fontsize=12)

    axes[0].plot(diagrams.x_m, diagrams.shear_kn, color="#1f77b4", lw=1.5)
    axes[0].axhline(0, color="black", lw=0.8)
    axes[0].fill_between(
        diagrams.x_m, diagrams.shear_kn, 0, color="#1f77b4", alpha=0.15
    )
    axes[0].set_ylabel("Shear V (kN)")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(diagrams.x_m, diagrams.moment_knm, color="#d62728", lw=1.5)
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].fill_between(
        diagrams.x_m, diagrams.moment_knm, 0, color="#d62728", alpha=0.15
    )
    axes[1].set_ylabel("Moment M (kN·m)")
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(diagrams.x_m, diagrams.deflection_mm, color="#2ca02c", lw=1.5)
    axes[2].axhline(0, color="black", lw=0.8)
    axes[2].fill_between(
        diagrams.x_m, diagrams.deflection_mm, 0, color="#2ca02c", alpha=0.15
    )
    axes[2].set_ylabel("Deflection (mm)")
    axes[2].set_xlabel(f"Position along beam x (m), L = {L:.2f} m")
    axes[2].grid(True, alpha=0.3)

    # Support markers.
    for ax in axes:
        for s in solution.spec.supports:
            ax.axvline(s.x_m, color="gray", lw=1.0, ls="--", alpha=0.6)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(path, format=fmt, dpi=150)
    plt.close(fig)
    return path
