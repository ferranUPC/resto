from __future__ import annotations

import re
from pathlib import Path

import pytest
from golden import run
from golden.framework import ExpectedPhase, ExpectedTrace, GoldenPath
from golden.paths import discover
from golden.setups.fake import FakeSetup


def test_every_golden_path_is_discovered_once() -> None:
    names = [p.name for p in discover()]

    assert names == sorted(set(names))
    assert {"gp1", "gp2", "gp3", "gp3_single_phase", "gp4", "gp5", "gp9"} <= set(names)


def test_the_fake_setup_passes_every_golden_path(capsys: pytest.CaptureFixture[str]) -> None:
    code = run.main(["--setup", "fake"])

    out = capsys.readouterr().out
    assert code == 0
    assert out.count("PASS") == len(discover()) and "FAIL" not in out


def test_a_path_that_differs_prints_its_diff_and_exits_non_zero(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong = GoldenPath(
        "gp2", "how congested is the peak?", ExpectedTrace((ExpectedPhase(steps=()),))
    )
    monkeypatch.setattr(run, "discover", lambda: (wrong,))

    code = run.main(["--setup", "fake"])

    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL gp2" in out and "phase 0, repetition 0: steps (tool, status)" in out


def test_a_path_without_a_script_fails_instead_of_crashing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    orphan = GoldenPath("orphan", "x", ExpectedTrace(()))
    monkeypatch.setattr(run, "discover", lambda: (orphan,))

    assert run.main(["--setup", "fake"]) == 1
    assert "scripts/orphan.py" in capsys.readouterr().out


def test_the_agentic_setup_is_rejected_with_its_pointers_and_runs_nothing(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(self: FakeSetup, path: GoldenPath) -> None:
        raise AssertionError("nothing may run")

    monkeypatch.setattr(FakeSetup, "run", forbidden)

    code = run.main(["--setup", "agentic"])

    err = capsys.readouterr().err
    assert code != 0
    assert "E12.1" in err and "docs/llm-cost-policy.md" in err


def test_a_run_writes_one_trace_file_per_path_and_repetition_under_a_utc_directory(
    tmp_path: Path,
) -> None:
    assert run.main(["--setup", "fake", "--trace-dir", str(tmp_path)]) == 0

    (stamped,) = tmp_path.iterdir()
    assert re.fullmatch(r"\d{8}T\d{6}Z", stamped.name)
    files = {f.name for f in stamped.glob("*.jsonl")}
    assert len(files) == len(discover()) * FakeSetup().repetitions
    assert "gp1-rep0.jsonl" in files and "gp9-rep2.jsonl" in files


def test_no_trace_writes_no_files(tmp_path: Path) -> None:
    assert run.main(["--setup", "fake", "--no-trace", "--trace-dir", str(tmp_path)]) == 0

    assert list(tmp_path.iterdir()) == []


def test_an_unwritable_trace_directory_warns_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")

    code = run.main(["--setup", "fake", "--trace-dir", str(blocker)])

    captured = capsys.readouterr()
    assert code == 0
    assert "warning" in captured.err and "FAIL" not in captured.out
