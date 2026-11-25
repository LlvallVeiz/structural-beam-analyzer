"""structural-beam-analyzer: beam reactions, shear/moment diagrams,
deflection and stress checks (Euler-Bernoulli, direct-stiffness FEM).
"""

from .diagrams import compute_diagrams
from .io import analyse, load_case, run_batch
from .model import (
    AppliedMoment,
    BeamSpec,
    DistributedLoad,
    PointLoad,
    Support,
)
from .sections import get_section, list_sections, rectangular_section
from .solver import solve
from .stress import check_stress

__version__ = "1.0.0"
__all__ = [
    "analyse",
    "load_case",
    "run_batch",
    "solve",
    "compute_diagrams",
    "check_stress",
    "get_section",
    "list_sections",
    "rectangular_section",
    "BeamSpec",
    "Support",
    "PointLoad",
    "DistributedLoad",
    "AppliedMoment",
    "__version__",
]
