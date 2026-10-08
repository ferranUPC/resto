from __future__ import annotations

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
