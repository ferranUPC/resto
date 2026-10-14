from __future__ import annotations

from dataclasses import replace

import pytest
from golden import run
from golden.framework import (
    ExpectedOutcome,
    ExpectedResolution,
    GoldenPath,
    ObservedOutcome,
    Run,
    SameNetworkId,
    Severity,
    check,
    compare_outcome,
    observe_outcome,
)
from golden.paths.gp9 import GP9
from golden.setups.fake import AgentScript, FakeSetup

from resto.domain.entities.study import StudyResolution
from tests.unit.application._world import BASELINE_PLAN, DESCRIBE, answers

SCRIPT = AgentScript(question=DESCRIBE, plans=(BASELINE_PLAN,), expert=(answers(),))
NETWORK = "abc123"  # the id of the network the shared World stores
COMPLETED = ExpectedResolution(StudyResolution.COMPLETED)


def _path(expected: ExpectedOutcome, name: str = "throwaway") -> GoldenPath:
    return GoldenPath(name, "how congested is the peak?", expected)


def _check(expected: ExpectedOutcome) -> str:
    diff = check(FakeSetup({"throwaway": SCRIPT}), _path(expected))
    return "ok" if diff.ok and not diff.warnings else diff.render()


def test_an_outcome_that_is_met_passes_through_the_real_use_cases() -> None:
    expected = ExpectedOutcome(resolution=COMPLETED, network=SameNetworkId(NETWORK))

    assert _check(expected) == "ok"


def test_a_wrong_resolution_fails_and_the_diff_names_the_resolution() -> None:
    expected = ExpectedOutcome(resolution=ExpectedResolution(StudyResolution.AWAITING_USER))

    text = _check(expected)

    assert "resolution" in text and "awaiting_user" in text and "completed" in text


def test_a_different_network_id_fails_and_the_diff_names_the_network() -> None:
    text = _check(ExpectedOutcome(network=SameNetworkId("another-net")))

    assert "network" in text and "another-net" in text and NETWORK in text


def test_a_part_left_empty_is_not_compared() -> None:
    assert _check(ExpectedOutcome()) == "ok"


def test_a_check_that_is_not_hard_is_a_warning_and_does_not_fail() -> None:
    soft = ExpectedResolution(StudyResolution.FAILED, Severity.WARNING)

    diff = compare_outcome(
        ExpectedOutcome(resolution=soft), ObservedOutcome(StudyResolution.COMPLETED, None)
    )

    assert diff.ok
    assert [m.what for m in diff.warnings] == ["resolution"]
    assert "warning" in diff.render()


def test_a_hard_mismatch_next_to_a_warning_still_fails() -> None:
    expected = ExpectedOutcome(
        resolution=ExpectedResolution(StudyResolution.FAILED, Severity.WARNING),
        network=SameNetworkId("x"),
    )

    diff = compare_outcome(expected, ObservedOutcome(StudyResolution.COMPLETED, "y"))

    assert not diff.ok and len(diff.warnings) == 1


def test_the_network_is_the_first_one_of_the_study() -> None:
    setup = FakeSetup({"throwaway": SCRIPT})
    study = setup.run(_path(ExpectedOutcome())).study

    assert observe_outcome(study) == ObservedOutcome(StudyResolution.COMPLETED, NETWORK)


class _Wobbly:
    """Wraps the fake; the second repetition uses another network."""

    repetitions = 3
    compare_repetitions = True

    def __init__(self) -> None:
        self._inner = FakeSetup({"throwaway": SCRIPT})
        self._runs = 0

    def run(self, path: GoldenPath) -> Run:
        result = self._inner.run(path)
        self._runs += 1
        if self._runs == 2:
            study = replace(result.study, network_ids=("another-net",))
            return Run(study, result.events)
        return result


def test_repetitions_that_differ_in_the_observed_outcome_are_reported() -> None:
    diff = check(_Wobbly(), _path(ExpectedOutcome()))

    assert not diff.ok
    assert "repetition 1 differs from repetition 0" in diff.render()


def test_gp9_is_an_outcome_and_passes() -> None:
    assert isinstance(GP9.expected, ExpectedOutcome)
    assert check(FakeSetup(), GP9).ok


def test_gp9_fails_when_the_study_does_not_wait_for_the_user() -> None:
    unflagged = FakeSetup({"gp9": SCRIPT})

    text = check(unflagged, GP9).render()

    assert "resolution" in text and "awaiting_user" in text


def test_a_warning_is_printed_and_the_command_exits_zero(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    soft = _path(
        ExpectedOutcome(resolution=ExpectedResolution(StudyResolution.FAILED, Severity.WARNING)),
        name="gp2",
    )
    monkeypatch.setattr(run, "discover", lambda: (soft,))

    code = run.main(["--setup", "fake"])

    out = capsys.readouterr().out
    assert code == 0
    assert "PASS gp2" in out and "warning" in out and "resolution" in out


def test_a_hard_outcome_mismatch_exits_one(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    wrong = _path(ExpectedOutcome(network=SameNetworkId("nope")), name="gp2")
    monkeypatch.setattr(run, "discover", lambda: (wrong,))

    assert run.main(["--setup", "fake"]) == 1
    assert "FAIL gp2" in capsys.readouterr().out
