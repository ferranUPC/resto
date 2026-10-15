"""`scripts/diff_concentration.py`: the size table behind the PR body and the third review axis."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "diff_concentration.py"
spec = importlib.util.spec_from_file_location("diff_concentration", SCRIPT)
assert spec is not None and spec.loader is not None
diff_concentration = importlib.util.module_from_spec(spec)
sys.modules["diff_concentration"] = diff_concentration
spec.loader.exec_module(diff_concentration)

NUMSTAT = (
    "300\t10\tsrc/resto/a/big.py\n"
    "100\t0\tsrc/resto/b/small.py\n"
    "500\t5\ttests/unit/test_big.py\n"
    "-\t-\timage.png\n"
    "7\t1\tdocs/x.md\n"
)


def test_areas_split_src_tests_and_other_and_binaries_are_skipped() -> None:
    changes = diff_concentration.parse_numstat(NUMSTAT)

    assert "image.png" not in changes
    report = diff_concentration.summarise(changes)
    assert "src    +400 -10" in report
    assert "tests  +500 -5" in report
    assert "other  +7 -1" in report


def test_largest_file_comes_first_with_its_cumulative_share() -> None:
    report = diff_concentration.summarise(diff_concentration.parse_numstat(NUMSTAT))

    first_row = report.split("cumulative share of 900)\n")[1].splitlines()[0]
    assert first_row.endswith("tests/unit/test_big.py")
    assert "55%" in first_row
