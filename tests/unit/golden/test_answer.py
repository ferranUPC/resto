"""The answer part of the Expected outcome: KPIs with a relative tolerance, `basis` and
`forced_by_limit`, read from the typed values of the final Expert round."""

from __future__ import annotations

import pytest
from golden.framework import (
    ExpectedAnswer,
    ExpectedKpi,
    ExpectedOutcome,
    GoldenPath,
    ObservedAnswer,
    ObservedOutcome,
    Severity,
    check,
    compare_outcome,
    observe_outcome,
)
from golden.paths import gp2, gp3, gp4
from golden.paths.gp9 import GP9
from golden.setups.fake import AgentScript, FakeSetup

from resto.domain.entities.study import StudyResolution
from resto.domain.value_objects.answer_value import Measure, Quantity
from resto.domain.value_objects.expert_answer import Basis
from tests.unit.application._world import (
    BASELINE_PLAN,
    DESCRIBE_CHANGE,
    PROPOSED,
    TREATMENT_PLAN,
    abstains,
    answers,
)

DELAY = ExpectedKpi(Measure.MEAN_DELAY, reference=43.0, tolerance=0.05)


def _observed(
    *values: Quantity, basis: Basis = Basis.OBSERVED, forced: bool = False
) -> ObservedOutcome:
    return ObservedOutcome(
        StudyResolution.COMPLETED, "net", ObservedAnswer(tuple(values), basis, forced)
    )


def _delay(value: float) -> Quantity:
    return Quantity(Measure.MEAN_DELAY, value)


def _diff(expected: ExpectedAnswer, observed: ObservedOutcome) -> str:
    diff = compare_outcome(ExpectedOutcome(answer=expected), observed)
    return "ok" if diff.ok and not diff.warnings else diff.render()


@pytest.mark.parametrize("seconds", [42.0, 43.0, 44.0])
def test_a_kpi_inside_its_tolerance_passes(seconds: float) -> None:
    assert _diff(ExpectedAnswer((DELAY,)), _observed(_delay(seconds))) == "ok"


@pytest.mark.parametrize("seconds", [90.0, 10.0])
def test_a_kpi_outside_its_tolerance_fails_and_the_diff_names_the_answer(seconds: float) -> None:
    text = _diff(ExpectedAnswer((DELAY,)), _observed(_delay(seconds)))

    assert "answer" in text and "mean_delay" in text and "43" in text and f"{seconds:g}" in text


def test_the_edge_of_the_tolerance_passes_and_just_outside_fails() -> None:
    kpi = ExpectedKpi(Measure.MEAN_DELAY, reference=40.0, tolerance=0.10)

    assert kpi.accepts(44.0) and kpi.accepts(36.0)
    assert not kpi.accepts(44.01) and not kpi.accepts(35.99)


def test_a_kpi_the_expert_did_not_give_fails() -> None:
    other = Quantity(Measure.MEAN_TRAVEL_TIME, 85.0)

    assert "not given" in _diff(ExpectedAnswer((DELAY,)), _observed(other))


def test_a_kpi_on_an_edge_matches_only_that_edge_and_network() -> None:
    kpi = ExpectedKpi(Measure.TRAVEL_TIME, 30.0, 0.1, edge_id="E12", network_id="net")
    right = Quantity(Measure.TRAVEL_TIME, 30.0, edge_id="E12", network_id="net")
    wrong_network = Quantity(Measure.TRAVEL_TIME, 30.0, edge_id="E12", network_id="other")

    assert _diff(ExpectedAnswer((kpi,)), _observed(right)) == "ok"
    assert "not given" in _diff(ExpectedAnswer((kpi,)), _observed(wrong_network))


def test_basis_and_forced_by_limit_are_compared_when_set() -> None:
    expected = ExpectedAnswer(basis=Basis.EXTRAPOLATED, forced_by_limit=True)

    text = _diff(expected, _observed(_delay(43.0)))

    assert "basis" in text and "extrapolated" in text and "observed" in text
    assert "forced_by_limit" in text


def test_basis_and_forced_by_limit_are_ignored_when_empty() -> None:
    observed = _observed(_delay(43.0), basis=Basis.INFERRED, forced=True)

    assert _diff(ExpectedAnswer((DELAY,)), observed) == "ok"


def test_no_final_answer_fails_every_set_item() -> None:
    gone = ObservedOutcome(StudyResolution.FAILED, "net", None)

    text = _diff(ExpectedAnswer((DELAY,), basis=Basis.OBSERVED), gone)

    assert "not given" in text and "basis" in text


def test_a_kpi_warning_does_not_fail() -> None:
    soft = ExpectedKpi(Measure.MEAN_DELAY, 43.0, 0.05, severity=Severity.WARNING)

    diff = compare_outcome(ExpectedOutcome(answer=ExpectedAnswer((soft,))), _observed(_delay(90.0)))

    assert diff.ok and len(diff.warnings) == 1


@pytest.mark.parametrize("tolerance", [-0.1, float("nan")])
def test_a_tolerance_must_be_a_finite_relative_value(tolerance: float) -> None:
    with pytest.raises(ValueError, match="tolerance"):
        ExpectedKpi(Measure.MEAN_DELAY, 43.0, tolerance)


def test_a_kpi_scope_must_fit_its_measure() -> None:
    with pytest.raises(ValueError, match="network-wide"):
        ExpectedKpi(Measure.MEAN_DELAY, 43.0, 0.1, edge_id="E12", network_id="net")
    with pytest.raises(ValueError, match="per edge"):
        ExpectedKpi(Measure.TRAVEL_TIME, 43.0, 0.1)


def test_an_abstaining_round_is_skipped_when_reading_the_answer() -> None:
    script = AgentScript(
        question=DESCRIBE_CHANGE,
        plans=(BASELINE_PLAN, TREATMENT_PLAN),
        expert=(abstains(PROPOSED), answers(_delay(31.0))),
    )
    study = FakeSetup({"two": script}).run(GoldenPath("two", "x", ExpectedOutcome())).study

    observed = observe_outcome(study).answer

    assert study.rounds[0].answer.needs_simulation
    assert observed is not None and observed.values == (_delay(31.0),)


def test_a_study_that_never_answered_has_no_answer() -> None:
    assert observe_outcome(FakeSetup().run(GP9).study).answer is None


@pytest.mark.parametrize("path", [gp2.PATH, gp3.PATH, gp4.GP4], ids=lambda p: p.name)
def test_the_migrated_paths_pass_as_outcomes(path: GoldenPath) -> None:
    assert isinstance(path.expected, ExpectedOutcome) and path.expected.answer is not None
    assert check(FakeSetup(), path).mismatches == ()


def test_gp3_is_the_dod_request_in_one_phase() -> None:
    study = FakeSetup().run(gp3.PATH).study

    assert gp3.PATH.request == "what if we close lane 1 of E12?"
    assert len(study.phases) == 1


def test_gp4_requires_the_basis_and_the_limit_flag_of_forced_mode() -> None:
    assert isinstance(gp4.GP4.expected, ExpectedOutcome)
    answer = gp4.GP4.expected.answer

    assert answer is not None
    assert answer.basis is Basis.EXTRAPOLATED and answer.forced_by_limit is False
