from typing import Any

import pytest

from resto.domain.entities.study import Phase, Study, StudyStatus
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import StepError, StepErrorKind, StepRecord, StepStatus
from resto.domain.value_objects.study_plan import ClarificationRequest, StudyPlan
from tests.unit.domain._samples import report

PLAN = StudyPlan(network_id="n1", rationale="results exist")
EVIDENCE = (Evidence(kind=EvidenceKind.QUERY, ref="query_edgedata(r1,E12)"),)
OK = StepRecord(tool="run_simulation", status=StepStatus.OK)
FAILED = StepRecord(
    tool="build_scenario",
    status=StepStatus.FAILED,
    error=StepError(StepErrorKind.USER_INPUT, "unknown edge", ("E99",)),
)
SKIPPED = StepRecord(tool="run_simulation", status=StepStatus.SKIPPED)


def _question(**kw):  # noqa: ANN003, ANN202
    base: dict[str, Any] = dict(text="what happens at peak?", intent=Intent.DESCRIBE)
    base.update(kw)
    return Question(**base)


PROPOSED = _question(text="close E12 at peak", intent=Intent.RUN)


def _answer() -> ExpertAnswer:
    return ExpertAnswer(
        answer="E12",
        basis=Basis.OBSERVED,
        confidence=0.9,
        evidence=EVIDENCE,
        values=(Edges(edge_ids=("E12",)),),
    )


def _abstain(proposed: Question = PROPOSED) -> ExpertAnswer:
    return ExpertAnswer(
        answer="need a run",
        basis=Basis.EXTRAPOLATED,
        confidence=0.3,
        needs_simulation=True,
        proposed_experiment=proposed,
    )


def _round(answer: ExpertAnswer, *, forced_by_limit: bool = False) -> ExpertRound:
    return ExpertRound(question="q", answer=answer, forced_by_limit=forced_by_limit)


def _free_loop(rounds: int) -> tuple[Phase, ...]:
    """`rounds` phases: every round but the last asks for PROPOSED; the last answers, forced by
    the limit when it is round 3."""
    phases = []
    for k in range(rounds):
        last = k == rounds - 1
        answer = _answer() if last else _abstain()
        phases.append(
            Phase(
                question=_question() if k == 0 else PROPOSED,
                plan=PLAN,
                round=_round(answer, forced_by_limit=last and rounds == 3),
            )
        )
    return tuple(phases)


# --- Phase ----------------------------------------------------------------------------------


def test_steps_require_a_plan_except_the_failed_planning() -> None:
    with pytest.raises(ValueError, match="failed planning"):
        Phase(question=_question(), steps=(OK,))
    Phase(question=_question(), steps=(FAILED,))


def test_experiments_and_the_round_require_a_plan() -> None:
    with pytest.raises(ValueError, match="need a plan"):
        Phase(question=_question(), round=_round(_answer()))


def test_a_phase_holds_a_plan_or_a_clarification() -> None:
    with pytest.raises(ValueError, match="either"):
        Phase(question=_question(), plan=PLAN, clarification=ClarificationRequest("two networks"))


def test_steps_after_the_first_failure_are_skipped() -> None:
    with pytest.raises(ValueError, match="skipped"):
        Phase(question=_question(), plan=PLAN, steps=(FAILED, OK))
    phase = Phase(question=_question(), plan=PLAN, steps=(OK, FAILED, SKIPPED))
    assert phase.failed_step == FAILED


# --- Study: the loop ------------------------------------------------------------------------


def test_a_study_has_at_least_one_phase() -> None:
    with pytest.raises(ValueError):
        Study(study_id="s", status=StudyStatus.PLANNING, phases=())


def test_each_phase_asks_the_previous_proposed_experiment() -> None:
    first = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    other = _question(text="something else", intent=Intent.RUN)
    with pytest.raises(ValueError, match="proposed"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(first, Phase(question=other)))
    Study(study_id="s", status=StudyStatus.RUNNING, phases=(first, Phase(question=PROPOSED)))


def test_a_phase_follows_only_a_round_that_asked_for_it() -> None:
    first = Phase(question=_question(), plan=PLAN)
    with pytest.raises(ValueError, match="proposed"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(first, Phase(question=PROPOSED)))


def test_max_rounds_is_enforced() -> None:
    with pytest.raises(ValueError):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=_free_loop(3), max_rounds=2)
    study = Study(study_id="s", status=StudyStatus.RUNNING, phases=_free_loop(2))
    assert len(study.rounds) == 2
    assert study.rounds_left == 1


def test_the_last_free_round_and_only_it_is_forced_by_the_limit() -> None:
    Study(study_id="s", status=StudyStatus.RUNNING, phases=_free_loop(3))
    early = Phase(
        question=_question(), plan=PLAN, round=_round(_answer(), forced_by_limit=True)
    )
    with pytest.raises(ValueError, match="forced by the limit"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(early,))
    *head, last = _free_loop(3)
    unmarked = Phase(question=last.question, plan=PLAN, round=_round(_answer()))
    with pytest.raises(ValueError, match="forced by the limit"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(*head, unmarked))


def test_a_round_forced_by_the_limit_answers() -> None:
    with pytest.raises(ValueError, match="must answer"):
        _round(_abstain(), forced_by_limit=True)


def test_forced_mode_has_one_phase_and_never_asks_for_a_simulation() -> None:
    forced = _question(mode=Mode.FORCED)
    asks = Phase(question=forced, plan=PLAN, round=_round(_abstain()))
    with pytest.raises(ValueError, match="forced mode"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(asks,))
    answers = Phase(question=forced, plan=PLAN, round=_round(_answer()))
    Study(study_id="s", status=StudyStatus.COMPLETED, phases=(answers,), report=report())


def test_later_phases_cannot_ask_the_user() -> None:
    first = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    later = Phase(question=PROPOSED, clarification=ClarificationRequest("two demands match"))
    with pytest.raises(ValueError, match="phase 0"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(first, later))


# --- Study: status --------------------------------------------------------------------------


def test_ambiguous_question_waits_for_the_user() -> None:
    q = _question(ambiguities=("which network?",))
    with pytest.raises(ValueError, match="ambiguous"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(Phase(question=q),))
    with pytest.raises(ValueError, match="ambiguous"):
        Study(
            study_id="s", status=StudyStatus.AWAITING_USER, phases=(Phase(question=q, plan=PLAN),)
        )
    Study(study_id="s", status=StudyStatus.AWAITING_USER, phases=(Phase(question=q),))


def test_a_coordinator_clarification_waits_for_the_user() -> None:
    phase = Phase(question=_question(), clarification=ClarificationRequest("two networks match"))
    with pytest.raises(ValueError, match="clarification"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(phase,))
    Study(study_id="s", status=StudyStatus.AWAITING_USER, phases=(phase,))


def test_awaiting_user_needs_something_to_ask() -> None:
    with pytest.raises(ValueError, match="awaiting_user"):
        Study(study_id="s", status=StudyStatus.AWAITING_USER, phases=(Phase(question=_question()),))


def test_a_study_fails_if_and_only_if_a_step_failed() -> None:
    failing = Phase(question=_question(), plan=PLAN, steps=(OK, FAILED, SKIPPED))
    with pytest.raises(ValueError, match="failed"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(failing,))
    ok = Phase(question=_question(), plan=PLAN, steps=(OK,))
    with pytest.raises(ValueError, match="failed"):
        Study(study_id="s", status=StudyStatus.FAILED, phases=(ok,))
    Study(study_id="s", status=StudyStatus.FAILED, phases=(failing,))


def test_the_failed_step_is_in_the_last_phase() -> None:
    first = Phase(question=_question(), plan=PLAN, steps=(FAILED,), round=_round(_abstain()))
    with pytest.raises(ValueError, match="last phase"):
        Study(study_id="s", status=StudyStatus.FAILED, phases=(first, Phase(question=PROPOSED)))


def test_a_failed_planning_fails_the_study() -> None:
    first = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    unplanned = Phase(question=PROPOSED, steps=(FAILED,))
    study = Study(study_id="s", status=StudyStatus.FAILED, phases=(first, unplanned))
    assert study.phases[-1].failed_step == FAILED


def test_a_report_is_composed_if_and_only_if_the_study_completed() -> None:
    answered = Phase(question=_question(), plan=PLAN, round=_round(_answer()))
    with pytest.raises(ValueError, match="report"):
        Study(study_id="s", status=StudyStatus.COMPLETED, phases=(answered,))
    with pytest.raises(ValueError, match="report"):
        Study(study_id="s", status=StudyStatus.RUNNING, phases=(answered,), report=report())
    Study(study_id="s", status=StudyStatus.COMPLETED, phases=(answered,), report=report())


def test_a_completed_study_ends_on_an_expert_answer() -> None:
    unanswered = Phase(question=_question(), plan=PLAN)
    with pytest.raises(ValueError, match="Expert answer"):
        Study(study_id="s", status=StudyStatus.COMPLETED, phases=(unanswered,), report=report())


def test_question_is_the_first_phase_question() -> None:
    study = Study(study_id="s", status=StudyStatus.RUNNING, phases=_free_loop(2))
    assert study.question == _question()


# --- StepRecord / ExpertAnswer --------------------------------------------------------------


def test_a_step_carries_an_error_if_and_only_if_it_failed() -> None:
    with pytest.raises(ValueError):
        StepRecord(tool="build_scenario", status=StepStatus.FAILED)
    with pytest.raises(ValueError):
        StepRecord(tool="build_scenario", status=StepStatus.OK, error=FAILED.error)


def test_a_step_error_needs_a_message() -> None:
    with pytest.raises(ValueError):
        StepError(StepErrorKind.AGENT, " ")


def test_answer_without_evidence_must_abstain() -> None:
    with pytest.raises(ValueError, match="evidence"):
        ExpertAnswer(
            answer="E12 is congested",
            basis=Basis.OBSERVED,
            confidence=0.9,
            values=(Edges(edge_ids=("E12",)),),
        )


def test_answer_without_typed_values_must_abstain() -> None:
    with pytest.raises(ValueError, match="typed value"):
        ExpertAnswer(
            answer="E12 is congested", basis=Basis.OBSERVED, confidence=0.9, evidence=EVIDENCE
        )
