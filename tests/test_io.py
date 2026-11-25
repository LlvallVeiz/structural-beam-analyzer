"""JSON input/output and batch-mode tests."""

import json

import pytest

from beam_analyzer.io import (
    analyse,
    load_case,
    metrics_dict,
    run_batch,
    spec_from_dict,
    write_case_outputs,
)

SS_CENTRAL = {
    "name": "ss-central-point",
    "length_m": 6.0,
    "E_MPa": 200000,
    "section": {"type": "aisc", "designation": "W10x30", "Fy_MPa": 345},
    "supports": [
        {"x_m": 0, "type": "pin"},
        {"x_m": 6, "type": "roller"},
    ],
    "loads": [{"type": "point", "x_m": 3, "P_kN": 10}],
}

SS_UDL = {
    "name": "ss-udl",
    "length_m": 6.0,
    "E_MPa": 200000,
    "section": {"type": "rectangular", "b_m": 0.2, "h_m": 0.4, "Fy_MPa": 24},
    "supports": [
        {"x_m": 0, "type": "pin"},
        {"x_m": 6, "type": "roller"},
    ],
    "loads": [{"type": "udl", "x1_m": 0, "x2_m": 6, "w_kN_m": 5}],
}


def test_spec_from_dict_aisc():
    spec, section = spec_from_dict(SS_CENTRAL)
    assert spec.name == "ss-central-point"
    assert spec.length_m == 6.0
    assert section.name == "W10x30"
    assert spec.fy_mpa == 345.0
    assert len(spec.point_loads) == 1
    assert spec.point_loads[0].p_kn == 10.0


def test_spec_from_dict_rectangular_and_custom():
    spec, section = spec_from_dict(SS_UDL)
    assert section.name == "RECT 200x400"
    assert section.Ix_m4 == pytest.approx(0.2 * 0.4 ** 3 / 12.0)
    assert spec.fy_mpa == 24.0

    custom = dict(SS_CENTRAL)
    custom["section"] = {
        "type": "custom", "name": "BUILT-UP", "Ix_m4": 2.5e-4,
        "Sx_m3": 1.2e-3, "Zx_m3": 1.4e-3, "area_m2": 0.01,
        "depth_m": 0.4, "web_area_m2": 0.008, "weight_kn_m": 0.5,
    }
    spec, section = spec_from_dict(custom)
    assert section.name == "BUILT-UP"
    assert section.Ix_m4 == 2.5e-4


def test_spec_from_dict_rejects_unknown_types():
    bad = dict(SS_CENTRAL)
    bad["section"] = {"type": "i-beam", "designation": "W10x30"}
    with pytest.raises(ValueError):
        spec_from_dict(bad)
    bad = json.loads(json.dumps(SS_CENTRAL))
    bad["loads"] = [{"type": "wind", "x_m": 3, "P_kN": 10}]
    with pytest.raises(ValueError):
        spec_from_dict(bad)


def test_load_case_from_file(tmp_path):
    path = tmp_path / "case.json"
    path.write_text(json.dumps(SS_CENTRAL), encoding="utf-8")
    spec, section = load_case(path)
    assert spec.name == "ss-central-point"
    assert section.name == "W10x30"


def test_metrics_dict_values():
    spec, section = spec_from_dict(SS_CENTRAL)
    result = analyse(spec, section)
    m = metrics_dict(result)
    assert m["name"] == "ss-central-point"
    assert m["reactions_kN"] == pytest.approx([5.0, 5.0])
    assert m["max_moment_kNm"] == pytest.approx(15.0)
    assert m["max_shear_kN"] == pytest.approx(5.0)
    # delta = P L^3 / (48 EI) with the W10x30's own Ix (170 in^4).
    ei = 200_000.0 * 1000.0 * section.Ix_m4
    assert m["max_deflection_mm"] == pytest.approx(
        10.0 * 6.0 ** 3 / (48.0 * ei) * 1000.0, rel=1e-3
    )
    assert m["verdict"] == "PASS"
    assert m["equilibrium_force_residual_kN"] == pytest.approx(0.0, abs=1e-6)


def test_write_case_outputs(tmp_path):
    spec, section = spec_from_dict(SS_CENTRAL)
    result = analyse(spec, section)
    paths = write_case_outputs(result, tmp_path / "out")
    for key in ("report_md", "report_html", "diagram_png", "diagram_svg", "metrics"):
        assert paths[key].exists(), key
    metrics = json.loads(paths["metrics"].read_text(encoding="utf-8"))
    assert metrics["max_moment_kNm"] == pytest.approx(15.0)


def test_run_batch_writes_summary_csv(tmp_path):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.json").write_text(json.dumps(SS_CENTRAL), encoding="utf-8")
    (in_dir / "b.json").write_text(json.dumps(SS_UDL), encoding="utf-8")
    rows = run_batch(in_dir, tmp_path / "out")
    assert len(rows) == 2
    assert {r["name"] for r in rows} == {"ss-central-point", "ss-udl"}
    summary = tmp_path / "out" / "summary.csv"
    assert summary.exists()
    lines = summary.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3  # header + 2 cases
    assert "ss-central-point" in lines[1] or "ss-central-point" in lines[2]
    assert (tmp_path / "out" / "ss-udl" / "report.md").exists()
