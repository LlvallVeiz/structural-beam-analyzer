"""Unit handling for structural-beam-analyzer.

All internal computation is SI: length in metres, force in kN,
moment in kN*m, stress in MPa, E in MPa.  Section data from the AISC
catalogue is stored in US customary units (inches) and converted here.

Conversions
-----------
1 in   = 0.0254 m
1 in^2 = 6.4516e-4 m^2
1 in^3 = 1.63871e-5 m^3
1 in^4 = 4.16231e-7 m^4
1 lb/ft = 0.0145939 kN/m
1 ksi  = 6.89476 MPa
"""

IN_TO_M = 0.0254
IN2_TO_M2 = IN_TO_M ** 2
IN3_TO_M3 = IN_TO_M ** 3
IN4_TO_M4 = IN_TO_M ** 4
LB_FT_TO_KN_M = 0.0145939
KSI_TO_MPA = 6.89476
MPA_TO_KN_M2 = 1000.0  # 1 MPa = 1000 kN/m^2


def in_to_m(value_in: float) -> float:
    """Inches to metres."""
    return value_in * IN_TO_M


def in2_to_m2(value_in2: float) -> float:
    """Square inches to square metres."""
    return value_in2 * IN2_TO_M2


def in3_to_m3(value_in3: float) -> float:
    """Cubic inches to cubic metres."""
    return value_in3 * IN3_TO_M3


def in4_to_m4(value_in4: float) -> float:
    """Inches^4 to metres^4."""
    return value_in4 * IN4_TO_M4


def lb_ft_to_kn_m(value_lb_ft: float) -> float:
    """Pounds per foot to kN/m."""
    return value_lb_ft * LB_FT_TO_KN_M


def ksi_to_mpa(value_ksi: float) -> float:
    """ksi to MPa."""
    return value_ksi * KSI_TO_MPA
