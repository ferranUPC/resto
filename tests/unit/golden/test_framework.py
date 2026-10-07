from __future__ import annotations

from dataclasses import replace

from golden.framework import (
    ExpectedPhase,
    ExpectedStep,
    ExpectedTrace,
    compare,
    observe,
)

from resto.application.ports.tracing import (
    ExpertRoundHeld,
    ModelCall,
    PhaseStarted,
    PlanMade,
    StepTraced,
    StudyCreated,
    TraceEvent,
)
from resto.domain.entities.study import Study, StudyStatus
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.step_record import StepStatus, Usage
from tests.unit.domain._fixtures import ASKED, PROPOSED, study_with_rounds


def _step(
    phase: int, tool: str, status: StepStatus = StepStatus.OK, ids: tuple[str, ...] = ()
) -> StepTraced:
    return StepTraced(phase, tool, status, ids, Usage(), None)


def _experiment(arm: str, *, reused: bool, scenario_id: str = "sc1") -> Experiment:
    return Experiment(scenario_id, arm, ExperimentRole.BASELINE, "p", ("r1",), reused)


def _study(*, reused: bool = False, basis: Basis = Basis.OBSERVED) -> Study:
    return study_with_rounds(1, basis=basis, experiments=((_experiment("base", reused=reused),),))


def _events(study: Study, tool_ids: tuple[str, ...] = ()) -> list[TraceEvent]:
    plan = study.phases[0].plan
    assert plan is not None
    return [
        StudyCreated(ASKED, Usage()),
        PhaseStarted(0),
        PlanMade(0, plan),
        _step(0, "obtain_network", ids=tool_ids),
        _step(0, "build_scenario"),
        _step(0, "run_simulation"),
        ExpertRoundHeld(0, 1),
    ]


EXPECTED = ExpectedTrace(
    (
        ExpectedPhase(
            steps=(
                ExpectedStep("obtain_network"),
                ExpectedStep("build_scenario"),
                ExpectedStep("run_simulation"),
            ),
            arms=(),
            reused=(False,),
            round=1,
            basis=Basis.OBSERVED,
            forced_by_limit=False,
        ),
    )
)


def test_a_trace_that_matches_its_expectation_has_no_difference() -> None:
    study = _study()
    assert compare(EXPECTED, observe(study, _events(study))).ok


def test_a_wrong_tool_order_names_the_phase_and_both_sequences() -> None:
    study = _study()
    events = _events(study)
    events[3], events[4] = events[4], events[3]

    diff = compare(EXPECTED, observe(study, events))

    assert not diff.ok
    text = diff.render()
    assert "phase 0" in text
    assert "obtain_network" in text and "build_scenario" in text
    assert "expected" in text and "observed" in text


def test_a_wrong_status_is_reported() -> None:
    study = _study()
    events = _events(study)
    events[4] = _step(0, "build_scenario", StepStatus.FAILED)

    diff = compare(EXPECTED, observe(study, events))

    assert "failed" in diff.render()
    assert "phase 0" in diff.render()


def test_a_wrong_attribute_is_reported_with_its_name() -> None:
    study = _study(reused=True)

    diff = compare(EXPECTED, observe(study, _events(study)))

    text = diff.render()
    assert "phase 0" in text and "reused" in text
    assert "(False,)" in text and "(True,)" in text


def test_basis_and_reused_are_read_from_the_study() -> None:
    study = _study(reused=True, basis=Basis.INFERRED)

    (phase,) = observe(study, _events(study))

    assert phase.reused == (True,)
    assert phase.basis is Basis.INFERRED
    assert phase.round == 1
    assert phase.forced_by_limit is False


def test_an_attribute_the_expectation_leaves_out_is_not_compared() -> None:
    study = _study(reused=True, basis=Basis.EXTRAPOLATED)
    loose = ExpectedTrace((replace(EXPECTED.phases[0], reused=None, basis=None),))

    assert compare(loose, observe(study, _events(study))).ok


def test_an_expected_phase_that_never_started_is_missing() -> None:
    study = _study()
    expected = ExpectedTrace((*EXPECTED.phases, ExpectedPhase(steps=())))

    text = compare(expected, observe(study, _events(study))).render()

    assert "phase 1" in text and "missing" in text


def test_a_phase_the_expectation_does_not_have_is_extra() -> None:
    study = _study()
    events = [*_events(study), PhaseStarted(1), _step(1, "obtain_network")]

    text = compare(EXPECTED, observe(study, events)).render()

    assert "phase 1" in text and "extra" in text


def test_free_text_tokens_and_ids_are_not_compared() -> None:
    study = _study()
    events = _events(study, tool_ids=("net-1",))
    noisy = [
        replace(e, usage=Usage(input_tokens=99)) if isinstance(e, StepTraced) else e for e in events
    ]
    noisy.insert(2, ModelCall(Usage(input_tokens=500)))
    noisy[0] = StudyCreated(PROPOSED, Usage(input_tokens=7))
    other = replace(study, study_id="another-id")

    assert compare(EXPECTED, observe(other, noisy)).ok


def test_an_expected_study_status_is_compared_when_given() -> None:
    study = _study()
    expected = replace(EXPECTED, status=StudyStatus.AWAITING_USER)

    diff = compare(expected, observe(study, _events(study)), study.status)

    text = diff.render()
    assert text.startswith("study, status:")
    assert "awaiting_user" in text and f"observed {study.status.value}" in text


def test_a_study_status_the_expectation_leaves_out_is_not_compared() -> None:
    study = _study()

    assert compare(EXPECTED, observe(study, _events(study)), StudyStatus.FAILED).ok


def test_an_event_type_outside_allowed_events_is_reported() -> None:
    study = _study()
    expected = replace(EXPECTED, allowed_events=(StudyCreated, PhaseStarted, StepTraced))

    text = compare(expected, observe(study, _events(study)), events=_events(study)).render()

    assert text.startswith("study, events: expected only")
    assert "ExpertRoundHeld" in text and "PlanMade" in text


def test_events_inside_allowed_events_pass() -> None:
    study = _study()
    expected = replace(
        EXPECTED,
        allowed_events=(StudyCreated, PhaseStarted, PlanMade, StepTraced, ExpertRoundHeld),
    )

    assert compare(expected, observe(study, _events(study)), events=_events(study)).ok
