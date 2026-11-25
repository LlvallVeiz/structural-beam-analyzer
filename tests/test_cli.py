"""CLI tests -- every subcommand end to end (in-process)."""

import json

import pytest

from beam_analyzer.cli import main
from test_io import SS_CENTRAL, SS_UDL


def test_check_passes(capsys):
    assert main(["check"]) == 0
    out = capsys.readouterr().out
    assert "Verification: 12/12 cases passed" in out


def test_sections_list(capsys):
    assert main(["sections", "--list"]) == 0
    out = capsys.readouterr().out
    assert "W10x30" in out
    assert "W24x68" in out


def test_sections_show(capsys):
    assert main(["sections", "--show", "W10x30"]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["designation"] == "W10x30"
    assert data["Ix_in4"] == pytest.approx(170.0, rel=1e-3)
    assert data["Sx_in3"] == pytest.approx(32.4, rel=1e-3)


def test_sections_lightest(capsys):
    assert main(["sections", "--lightest", "100"]) == 0
    out = capsys.readouterr().out
    assert "W12x26" in out


def test_example_list(capsys):
    assert main(["example", "list"]) == 0
    out = capsys.readouterr().out
    assert "ss_central_point" in out
    assert "cantilever_tip" in out


def test_analyze_writes_outputs(tmp_path, capsys):
    case = tmp_path / "case.json"
    case.write_text(json.dumps(SS_CENTRAL), encoding="utf-8")
    out_dir = tmp_path / "out"
    assert main(["analyze", str(case), "--out", str(out_dir)]) == 0
    assert (out_dir / "report.md").exists()
    assert (out_dir / "report.html").exists()
    assert (out_dir / "diagram.png").exists()
    assert (out_dir / "metrics.json").exists()
    out = capsys.readouterr().out
    assert "Mmax: 15.000 kN*m" in out
    assert "Verdict: PASS" in out


def test_batch_writes_summary(tmp_path, capsys):
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "a.json").write_text(json.dumps(SS_CENTRAL), encoding="utf-8")
    (in_dir / "b.json").write_text(json.dumps(SS_UDL), encoding="utf-8")
    out_dir = tmp_path / "out"
    assert main(["batch", str(in_dir), "--out", str(out_dir)]) == 0
    assert (out_dir / "summary.csv").exists()
    out = capsys.readouterr().out
    assert "2 cases written" in out


def test_version_flag():
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
