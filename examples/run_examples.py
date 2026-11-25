"""Run every example case and write its outputs.

Usage (from the project root)::

    PYTHONPATH=src python examples/run_examples.py

Outputs land in ``examples/output/<name>/``:
``report.md``, ``report.html``, ``diagram.png``, ``diagram.svg`` and
``metrics.json``.  A summary table is printed on stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from beam_analyzer.io import analyse, load_case, metrics_dict, write_case_outputs  # noqa: E402


def main() -> int:
    examples_dir = ROOT / "examples"
    out_root = examples_dir / "output"
    rows = []
    for case_path in sorted(examples_dir.glob("*.json")):
        spec, section = load_case(case_path)
        result = analyse(spec, section)
        write_case_outputs(result, out_root / spec.name)
        rows.append(metrics_dict(result))
        print(
            f"{spec.name:<32} Mmax {rows[-1]['max_moment_kNm']:>9.3f} kN*m  "
            f"delta {rows[-1]['max_deflection_mm']:>8.3f} mm  "
            f"{rows[-1]['verdict']}"
        )
    print(f"\n{len(rows)} examples written to {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
