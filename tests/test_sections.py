"""Section catalogue tests -- values from AISC Steel Construction
Manual, 16th Edition, Tables 1-1 (AISC Shapes Database v16.0)."""

import math

import pytest

from beam_analyzer.sections import (
    get_section,
    lightest_section_for,
    list_sections,
    radius_of_gyration_m,
    rectangular_section,
    required_section_modulus,
)

# Conversion factors (exact definitions).
IN4_TO_M4 = 4.162314256e-7
IN3_TO_M3 = 1.6387064e-5
IN2_TO_M2 = 6.4516e-4


def test_catalogue_has_eleven_shapes():
    names = list_sections()
    assert len(names) == 11
    assert names[0] == "W8x18"  # lightest first (18 lb/ft)
    assert "W24x68" in names
    assert "W10x30" in names


def test_w10x30_properties():
    s = get_section("W10x30")
    assert s.Ix_m4 == pytest.approx(170.0 * IN4_TO_M4, rel=1e-6)
    assert s.Sx_m3 == pytest.approx(32.4 * IN3_TO_M3, rel=1e-6)
    assert s.Zx_m3 == pytest.approx(36.6 * IN3_TO_M3, rel=1e-6)
    assert s.area_m2 == pytest.approx(8.84 * IN2_TO_M2, rel=1e-6)
    assert s.depth_m == pytest.approx(10.47 * 0.0254, rel=1e-6)
    assert s.weight_kn_m == pytest.approx(30.0 * 0.0145939, rel=1e-3)
    assert s.Ix_cm4 == pytest.approx(170.0 * 41.6231, rel=1e-3)
    assert s.Sx_cm3 == pytest.approx(32.4 * 16.387064, rel=1e-3)
    assert "AISC" in s.source


def test_w8x18_and_w24x68_properties():
    # Spot-check the lightest and heaviest shapes in the catalogue.
    s = get_section("W8x18")
    assert s.Ix_m4 == pytest.approx(61.9 * IN4_TO_M4, rel=1e-6)
    assert s.Sx_m3 == pytest.approx(15.2 * IN3_TO_M3, rel=1e-6)
    assert s.Zx_m3 == pytest.approx(17.5 * IN3_TO_M3, rel=1e-6)
    s = get_section("W24x68")
    assert s.Ix_m4 == pytest.approx(1830.0 * IN4_TO_M4, rel=1e-6)
    assert s.Sx_m3 == pytest.approx(154.0 * IN3_TO_M3, rel=1e-6)


def test_lookup_is_case_insensitive():
    assert get_section("w12x26").name == "W12x26"
    assert get_section("  W10x30 ").name == "W10x30"


def test_unknown_section_raises():
    with pytest.raises(KeyError):
        get_section("W99x99")


def test_rectangular_section_geometry():
    s = rectangular_section(0.2, 0.4)
    # I = b h^3 / 12, S = b h^2 / 6, Z = b h^2 / 4.
    assert s.Ix_m4 == pytest.approx(0.2 * 0.4 ** 3 / 12.0)
    assert s.Sx_m3 == pytest.approx(0.2 * 0.4 ** 2 / 6.0)
    assert s.Zx_m3 == pytest.approx(0.2 * 0.4 ** 2 / 4.0)
    assert s.area_m2 == pytest.approx(0.08)
    assert s.web_area_m2 == pytest.approx(0.08)
    with pytest.raises(ValueError):
        rectangular_section(0.0, 0.4)


def test_required_section_modulus():
    # S_req = M / (0.66 * Fy) = 100 / (0.66 * 345 * 1000) m^3.
    assert required_section_modulus(100.0, 345.0) == pytest.approx(
        100.0 / (0.66 * 345.0 * 1000.0)
    )


def test_lightest_section_for_moment():
    # M = 100 kN*m at Fy = 345 MPa needs Sx >= 439 cm^3 (26.8 in^3);
    # the lightest catalogued shape that provides it is W12x26.
    s = lightest_section_for(100.0, 345.0)
    assert s.name == "W12x26"
    assert s.Sx_cm3 >= 439.0
    with pytest.raises(ValueError):
        lightest_section_for(10_000.0, 345.0)


def test_radius_of_gyration():
    # W10x30: rx = sqrt(Ix/A) = 4.38 in = 0.1113 m.
    s = get_section("W10x30")
    assert radius_of_gyration_m(s.Ix_m4, s.area_m2) == pytest.approx(
        4.38 * 0.0254, rel=1e-2
    )
    assert radius_of_gyration_m(4.0, 1.0) == pytest.approx(2.0)
