"""Direct-stiffness solver for Euler-Bernoulli beams.

Method
------
The beam is divided into two-node Euler-Bernoulli elements
(2 DOFs per node: vertical displacement v, rotation theta).
Element stiffness (EI constant per element)::

    k = EI / L^3 * [[12,  6L, -12,  6L],
                    [6L, 4L^2, -6L, 2L^2],
                    [-12, -6L, 12, -6L],
                    [6L, 2L^2, -6L, 4L^2]]

Work-equivalent nodal loads for a linearly varying downward load
w(x) = w1 + (w2 - w1) * x / L on the element::

    f = [-L(7w1+3w2)/20, -L^2(w1/20+w2/30),
         -L(3w1+7w2)/20, +L^2(w1/30+w2/20)]

(uniform load and triangular load are special cases).  Point loads
and applied moments are placed on nodes exactly, and every load
boundary is a node, so the linear-variation assumption is exact
inside every element.

The solver handles determinate and indeterminate beams alike
(simply supported, cantilever, fixed-fixed, propped cantilever,
continuous multi-span) because supports are just restrained DOFs.

Element end forces ``f_e = k_e u_e - f_eq`` are the nodal forces
applied *to* the element (node-on-element, v up +, theta CCW +).
They convert to internal shear/moment at the element ends (sagging
positive) as::

    V_left  = +f_e[0]      M_left  = -f_e[1]
    V_right = -f_e[2]      M_right = +f_e[3]

Verified numerically against a simply supported beam with a
central point load (element [2.94, 3.00] m: f_e = [5, -14.7, -5, 15]
while the true internal values are V = +5 kN and M = +14.7 -> +15
kN*m).  The test-suite checks these relations against textbook
reactions, moments and deflections.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import BeamSpec, DistributedLoad

# Target element length as a fraction of the span (diagram resolution).
_TARGET_ELEM_FRAC = 0.01
_MAX_ELEMENTS = 600


@dataclass
class Reaction:
    """Support reaction at one support."""

    x_m: float
    kind: str
    vertical_kn: float
    moment_knm: float = 0.0  # 0 for pin/roller; CCW + for fixed


@dataclass
class Element:
    """One finite element with its solved end forces."""

    x1_m: float
    x2_m: float
    w1_kn_m: float  # distributed intensity at the left end (down +)
    w2_kn_m: float  # distributed intensity at the right end (down +)
    f_end: np.ndarray  # element end forces [F1, M1, F2, M2], nodal signs
    u: np.ndarray  # nodal displacements [v1, th1, v2, th2]

    @property
    def length_m(self) -> float:
        """Element length in metres."""
        return self.x2_m - self.x1_m

    @property
    def shear_left_kn(self) -> float:
        """Internal shear just right of the left node (kN)."""
        return self.f_end[0]

    @property
    def shear_right_kn(self) -> float:
        """Internal shear just left of the right node (kN)."""
        return -self.f_end[2]

    @property
    def moment_left_knm(self) -> float:
        """Internal moment at the left node, sagging + (kN*m)."""
        return -self.f_end[1]

    @property
    def moment_right_knm(self) -> float:
        """Internal moment at the right node, sagging + (kN*m)."""
        return self.f_end[3]


@dataclass
class Solution:
    """Solved beam: displacements, reactions and element forces."""

    spec: BeamSpec
    nodes_x_m: np.ndarray
    v_m: np.ndarray
    theta_rad: np.ndarray
    reactions: list[Reaction]
    elements: list[Element]
    equilibrium_force_residual_kn: float = 0.0
    equilibrium_moment_residual_knm: float = 0.0

    @property
    def total_downward_load_kn(self) -> float:
        """Resultant of all applied vertical loads (kN)."""
        total = sum(p.p_kn for p in self.spec.point_loads)
        total += sum(w.total_load_kn() for w in self.spec.distributed_loads)
        sw = self.spec.self_weight_load()
        if sw is not None:
            total += sw.total_load_kn()
        return total

    @property
    def total_upward_reaction_kn(self) -> float:
        """Sum of vertical reactions (kN)."""
        return sum(r.vertical_kn for r in self.reactions)


def _critical_positions(spec: BeamSpec) -> list[float]:
    """x-positions where nodes must sit (supports, loads, ends)."""
    xs = {0.0, spec.length_m}
    for s in spec.supports:
        xs.add(s.x_m)
    for p in spec.point_loads:
        xs.add(p.x_m)
    for m in spec.moments:
        xs.add(m.x_m)
    for w in spec.distributed_loads:
        xs.add(w.x1_m)
        xs.add(w.x2_m)
    return sorted(xs)


def _build_nodes(spec: BeamSpec) -> np.ndarray:
    """Node coordinates: critical points plus subdivision."""
    critical = _critical_positions(spec)
    target = max(spec.length_m * _TARGET_ELEM_FRAC, 1e-3)
    nodes: list[float] = []
    for a, b in zip(critical[:-1], critical[1:]):
        n_sub = max(1, int(np.ceil((b - a) / target)))
        n_sub = min(n_sub, _MAX_ELEMENTS)
        for i in range(n_sub):
            nodes.append(a + (b - a) * i / n_sub)
    nodes.append(critical[-1])
    return np.array(sorted(set(nodes)), dtype=float)


def _element_stiffness(EI_kn_m2: float, length_m: float) -> np.ndarray:
    L = length_m
    return (
        EI_kn_m2
        / L ** 3
        * np.array(
            [
                [12.0, 6.0 * L, -12.0, 6.0 * L],
                [6.0 * L, 4.0 * L ** 2, -6.0 * L, 2.0 * L ** 2],
                [-12.0, -6.0 * L, 12.0, -6.0 * L],
                [6.0 * L, 2.0 * L ** 2, -6.0 * L, 4.0 * L ** 2],
            ]
        )
    )


def _distributed_feq(w1: float, w2: float, length_m: float) -> np.ndarray:
    """Work-equivalent nodal loads for a linearly varying downward load.

    w1, w2 in kN/m at the element ends; returns [F1, M1, F2, M2]
    with forces up + and moments CCW +.

    Derivation: with load q(x) = -w(x) (downward) and the Hermite
    shape functions N, f = int N^T q dx.  For a uniform load this
    gives the familiar [-wL/2, +wL^2/12, -wL/2, -wL^2/12]
    (fixed-end moments +wL^2/12 at the left node and -wL^2/12 at
    the right node, CCW +), which the verification suite checks
    against the fixed-fixed UDL textbook case.
    """
    L = length_m
    return np.array(
        [
            -L * (7.0 * w1 + 3.0 * w2) / 20.0,
            -(L ** 2) * (w1 / 20.0 + w2 / 30.0),
            -L * (3.0 * w1 + 7.0 * w2) / 20.0,
            (L ** 2) * (w1 / 30.0 + w2 / 20.0),
        ]
    )


def _element_end_intensities(
    loads: list[DistributedLoad], x1: float, x2: float
) -> tuple[float, float]:
    """Total distributed intensity at the two ends of one element.

    A load contributes at the left end only when it covers the
    element just right of x1 (``x1_m <= x1 < x2_m``), and at the
    right end only when it covers the element just left of x2
    (``x1_m < x2 <= x2_m``).  Because every load boundary is a node,
    no load starts or ends strictly inside an element, so this is
    exact.
    """
    w1 = sum(
        w.intensity_at(x1) for w in loads if w.x1_m <= x1 < w.x2_m
    )
    w2 = sum(
        w.intensity_at(x2) for w in loads if w.x1_m < x2 <= w.x2_m
    )
    return w1, w2


def solve(spec: BeamSpec) -> Solution:
    """Solve the beam and return displacements, reactions and forces."""
    if spec.Ix_m4 is None:
        raise ValueError("Ix must be set before solving")
    EI = spec.EI_kn_m2
    nodes = _build_nodes(spec)
    n_nodes = len(nodes)
    n_dof = 2 * n_nodes

    K = np.zeros((n_dof, n_dof))
    F = np.zeros(n_dof)
    node_index = {float(x): i for i, x in enumerate(nodes)}

    loads = list(spec.distributed_loads)
    sw = spec.self_weight_load()
    if sw is not None:
        loads.append(sw)

    # Assemble elements.
    elem_data: list[tuple[int, float, np.ndarray, np.ndarray]] = []
    for e in range(n_nodes - 1):
        x1, x2 = float(nodes[e]), float(nodes[e + 1])
        Le = x2 - x1
        w1, w2 = _element_end_intensities(loads, x1, x2)
        k_e = _element_stiffness(EI, Le)
        f_eq = _distributed_feq(w1, w2, Le)
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(dofs, dofs)] += k_e
        F[dofs] += f_eq
        elem_data.append((e, Le, k_e, f_eq))

    # Point loads (down +) and applied moments (CCW +) on nodes.
    for p in spec.point_loads:
        F[2 * node_index[float(p.x_m)]] -= p.p_kn
    for m in spec.moments:
        F[2 * node_index[float(m.x_m)] + 1] += m.m_knm

    # Restrained DOFs.
    restrained: set[int] = set()
    for s in spec.supports:
        i = node_index[float(s.x_m)]
        restrained.add(2 * i)
        if s.kind == "fixed":
            restrained.add(2 * i + 1)
    free = np.array([d for d in range(n_dof) if d not in restrained], dtype=int)

    u = np.zeros(n_dof)
    u[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])

    # Reactions from equilibrium at restrained DOFs.
    R_full = K @ u - F
    reactions: list[Reaction] = []
    for s in spec.supports:
        i = node_index[float(s.x_m)]
        moment = float(R_full[2 * i + 1]) if s.kind == "fixed" else 0.0
        reactions.append(
            Reaction(
                x_m=s.x_m,
                kind=s.kind,
                vertical_kn=float(R_full[2 * i]),
                moment_knm=moment,
            )
        )

    # Element end forces.
    elements: list[Element] = []
    for e, Le, k_e, f_eq in elem_data:
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        u_e = u[dofs]
        f_end = k_e @ u_e - f_eq
        x1, x2 = float(nodes[e]), float(nodes[e + 1])
        w1, w2 = _element_end_intensities(loads, x1, x2)
        elements.append(Element(x1, x2, w1, w2, f_end, u_e))

    # Equilibrium residuals (should be ~0).
    res_f = sum(r.vertical_kn for r in reactions)
    res_f -= sum(p.p_kn for p in spec.point_loads)
    res_f -= sum(w.total_load_kn() for w in loads)
    res_m = sum(r.vertical_kn * r.x_m + r.moment_knm for r in reactions)
    res_m -= sum(p.p_kn * p.x_m for p in spec.point_loads)
    for w in loads:
        total = w.total_load_kn()
        a = w.x2_m - w.x1_m
        w1, w2 = w.w1_kn_m, w.w2
        if (w1 + w2) > 0:
            x_bar = w.x1_m + a * (2.0 * w2 + w1) / (3.0 * (w1 + w2))
        else:
            x_bar = w.x1_m + a / 2.0
        res_m -= total * x_bar
    res_m -= sum(m.m_knm for m in spec.moments)

    return Solution(
        spec=spec,
        nodes_x_m=nodes,
        v_m=u[0::2],
        theta_rad=u[1::2],
        reactions=reactions,
        elements=elements,
        equilibrium_force_residual_kn=float(res_f),
        equilibrium_moment_residual_knm=float(res_m),
    )
