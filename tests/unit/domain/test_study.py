from typing import Any

import pytest

from resto.domain.entities.study import Phase, Study, StudyResolution, StudyStage
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.outcomes import NeedsUser, WindowMissing
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import StepError, StepErrorKind, StepRecord, StepStatus
from resto.domain.value_objects.study_plan import (
    FromStep,
    ObtainNetworkStep,
    StudyPlan,
)
from tests.unit.domain._samples import report

PLAN = StudyPlan(
    network_id=FromStep(0), rationale="results exist", steps=(ObtainNetworkStep("RIVERSIDE"),)
)
EVIDENCE = (Evidence(kind=EvidenceKind.QUERY, ref="query_edgedata(r1,E12)"),)
OK = StepRecord(tool="run_simulation", status=StepStatus.OK)
FAILED = StepRecord(
    tool="build_scenario",
    status=StepStatus.FAILED,
    error=StepError(StepErrorKind.USER_INPUT, "unknown edge", ("E99",)),
)
SKIPPED = StepRecord(tool="run_simulation", status=StepStatus.SKIPPED)
PLANNED = StepRecord(tool="plan", status=StepStatus.OK)
PLAN_FAILED = StepRecord(
    tool="plan", status=StepStatus.FAILED, error=StepError(StepErrorKind.PLANNING, "no plan")
)
EXPERT_OK = StepRecord(tool="ask_expert", status=StepStatus.OK)
EXPERT_FAILED = StepRecord(
    tool="ask_expert", status=StepStatus.FAILED, error=StepError(StepErrorKind.AGENT, "no answer")
)
COMPOSE_FAILED = StepRecord(
    tool="compose_report",
    status=StepStatus.FAILED,
    error=StepError(StepErrorKind.AGENT, "no report"),
)
WAITING = StepRecord(tool="obtain_demand", status=StepStatus.NEEDS_USER)
NEEDS = NeedsUser(WindowMissing(), "I was asked for a demand but no period can be derived")


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
        values=(Edges(edge_ids=("E12",), network_id="abc123"),),
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


def test_steps_after_the_first_failure_are_skipped() -> None:
    with pytest.raises(ValueError, match="skipped"):
        Phase(question=_question(), plan=PLAN, steps=(FAILED, OK))
    phase = Phase(question=_question(), plan=PLAN, steps=(OK, FAILED, SKIPPED))
    assert phase.failed_step == FAILED


# --- Study: the loop ------------------------------------------------------------------------

S = StudyStage
R = StudyResolution


def _study(stage: StudyStage, *phases: Phase, **kw: Any) -> Study:
    return Study("s", stage, phases, **kw)


def test_a_study_has_at_least_one_phase() -> None:
    with pytest.raises(ValueError):
        _study(S.PLANNING)


def test_each_phase_asks_the_previous_proposed_experiment() -> None:
    first = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    other = _question(text="something else", intent=Intent.RUN)
    with pytest.raises(ValueError, match="proposed"):
        _study(S.PLANNING, first, Phase(question=other))
    _study(S.PLANNING, first, Phase(question=PROPOSED))


def test_a_phase_follows_only_a_round_that_asked_for_it() -> None:
    first = Phase(question=_question(), plan=PLAN)
    with pytest.raises(ValueError, match="proposed"):
        _study(S.PLANNING, first, Phase(question=PROPOSED))


def test_max_rounds_is_enforced() -> None:
    with pytest.raises(ValueError):
        _study(S.CLOSING, *_free_loop(3), max_rounds=2)
    study = _study(S.CLOSING, *_free_loop(2))
    assert len(study.rounds) == 2
    assert study.rounds_left == 1


def test_the_last_free_round_and_only_it_is_forced_by_the_limit() -> None:
    _study(S.CLOSING, *_free_loop(3))
    early = Phase(question=_question(), plan=PLAN, round=_round(_answer(), forced_by_limit=True))
    with pytest.raises(ValueError, match="forced by the limit"):
        _study(S.CLOSING, early)
    *head, last = _free_loop(3)
    unmarked = Phase(question=last.question, plan=PLAN, round=_round(_answer()))
    with pytest.raises(ValueError, match="forced by the limit"):
        _study(S.CLOSING, *head, unmarked)


def test_a_round_forced_by_the_limit_answers() -> None:
    with pytest.raises(ValueError, match="must answer"):
        _round(_abstain(), forced_by_limit=True)


def test_forced_mode_has_one_phase_and_never_asks_for_a_simulation() -> None:
    forced = _question(mode=Mode.FORCED)
    asks = Phase(question=forced, plan=PLAN, round=_round(_abstain()))
    with pytest.raises(ValueError, match="forced mode"):
        _study(S.CONSULTING_EXPERT, asks)
    answers = Phase(question=forced, plan=PLAN, round=_round(_answer()))
    _study(S.CLOSING, answers, resolution=R.COMPLETED, report=report())


# --- Study: stage ---------------------------------------------------------------------------


def test_an_open_study_at_each_stage() -> None:
    q = _question()
    assert _study(S.PLANNING, Phase(question=q)).resolution is None
    _study(S.RUNNING, Phase(question=q, plan=PLAN, steps=(PLANNED, OK)))
    _study(S.CONSULTING_EXPERT, Phase(question=q, plan=PLAN, steps=(PLANNED, OK)))
    asked = Phase(question=q, plan=PLAN, steps=(PLANNED, OK, EXPERT_OK), round=_round(_abstain()))
    _study(S.CONSULTING_EXPERT, asked)
    _study(S.PLANNING, asked, Phase(question=PROPOSED))
    answered = Phase(question=q, plan=PLAN, steps=(PLANNED, EXPERT_OK), round=_round(_answer()))
    _study(S.CLOSING, answered)


def test_a_study_is_parsing_if_and_only_if_its_question_is_ambiguous() -> None:
    with pytest.raises(ValueError, match="parsing"):
        _study(S.PARSING, Phase(question=_question()))
    ambiguous = _question(ambiguities=("which network?",))
    with pytest.raises(ValueError, match="parsing"):
        _study(S.PLANNING, Phase(question=ambiguous), resolution=R.AWAITING_USER)


def test_a_study_at_planning_has_not_accepted_the_plan_of_its_last_phase() -> None:
    with pytest.raises(ValueError, match="planning"):
        _study(S.PLANNING, Phase(question=_question(), plan=PLAN, steps=(PLANNED,)))


def test_a_study_past_planning_has_accepted_the_plan_of_its_last_phase() -> None:
    first = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    for stage in (S.RUNNING, S.CONSULTING_EXPERT, S.CLOSING):
        with pytest.raises(ValueError, match="accepted plan"):
            _study(stage, first, Phase(question=PROPOSED))


def test_a_running_study_has_not_consulted_the_expert_in_its_last_phase() -> None:
    asked = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    with pytest.raises(ValueError, match="running"):
        _study(S.RUNNING, asked)


def test_the_expert_is_consulted_once_every_step_of_the_plan_ran() -> None:
    stopped = Phase(question=_question(), plan=PLAN, steps=(PLANNED, FAILED, SKIPPED))
    with pytest.raises(ValueError, match="consulting_expert"):
        _study(S.CONSULTING_EXPERT, stopped, resolution=R.FAILED)


def test_an_expert_answer_that_needs_no_simulation_moves_the_study_to_closing() -> None:
    answered = Phase(question=_question(), plan=PLAN, round=_round(_answer()))
    with pytest.raises(ValueError, match="closing"):
        _study(S.CONSULTING_EXPERT, answered)


def test_a_study_closes_on_an_expert_answer() -> None:
    with pytest.raises(ValueError, match="Expert answer"):
        _study(S.CLOSING, Phase(question=_question(), plan=PLAN))
    asked = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    with pytest.raises(ValueError, match="Expert answer"):
        _study(S.CLOSING, asked)


# --- Study: resolution ----------------------------------------------------------------------


def test_ambiguous_question_waits_for_the_user_at_parsing() -> None:
    q = _question(ambiguities=("which network?",))
    with pytest.raises(ValueError, match="ambiguous"):
        _study(S.PARSING, Phase(question=q))
    with pytest.raises(ValueError, match="ambiguous"):
        _study(S.PARSING, Phase(question=q, plan=PLAN), resolution=R.AWAITING_USER)
    _study(S.PARSING, Phase(question=q), resolution=R.AWAITING_USER)


def test_awaiting_user_needs_something_to_ask() -> None:
    with pytest.raises(ValueError, match="awaiting_user"):
        _study(S.PLANNING, Phase(question=_question()), resolution=R.AWAITING_USER)


def test_a_study_waits_for_the_user_only_at_parsing_or_running() -> None:
    waiting = Phase(
        question=_question(), plan=PLAN, steps=(PLANNED, WAITING, SKIPPED), needs_user=NEEDS
    )
    _study(S.RUNNING, waiting, resolution=R.AWAITING_USER)
    with pytest.raises(ValueError, match="awaiting_user"):
        _study(S.CONSULTING_EXPERT, waiting, resolution=R.AWAITING_USER)


def test_a_study_fails_if_and_only_if_a_step_failed() -> None:
    failing = Phase(question=_question(), plan=PLAN, steps=(OK, FAILED, SKIPPED))
    with pytest.raises(ValueError, match="failed"):
        _study(S.RUNNING, failing)
    ok = Phase(question=_question(), plan=PLAN, steps=(OK,))
    with pytest.raises(ValueError, match="failed"):
        _study(S.RUNNING, ok, resolution=R.FAILED)
    _study(S.RUNNING, failing, resolution=R.FAILED)


def test_the_failed_step_is_in_the_last_phase() -> None:
    first = Phase(question=_question(), plan=PLAN, steps=(OK, FAILED), round=_round(_abstain()))
    with pytest.raises(ValueError, match="last phase"):
        _study(S.PLANNING, first, Phase(question=PROPOSED), resolution=R.FAILED)


def test_a_failed_study_keeps_the_stage_it_failed_in() -> None:
    q = _question()
    planning = _study(S.PLANNING, Phase(question=q, steps=(PLAN_FAILED,)), resolution=R.FAILED)
    assert planning.phases[-1].failed_step == PLAN_FAILED
    rejected = Phase(question=q, plan=PLAN, steps=(PLAN_FAILED, SKIPPED))
    _study(S.PLANNING, rejected, resolution=R.FAILED)
    running = Phase(question=q, plan=PLAN, steps=(PLANNED, FAILED, SKIPPED))
    _study(S.RUNNING, running, resolution=R.FAILED)
    consulting = Phase(question=q, plan=PLAN, steps=(PLANNED, OK, EXPERT_FAILED))
    _study(S.CONSULTING_EXPERT, consulting, resolution=R.FAILED)
    closing = Phase(
        question=q,
        plan=PLAN,
        steps=(PLANNED, OK, EXPERT_OK, COMPOSE_FAILED),
        round=_round(_answer()),
    )
    _study(S.CLOSING, closing, resolution=R.FAILED)


def test_a_failed_planning_of_a_later_phase_fails_the_study_at_planning() -> None:
    first = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    unplanned = Phase(question=PROPOSED, steps=(PLAN_FAILED,))
    study = _study(S.PLANNING, first, unplanned, resolution=R.FAILED)
    assert study.phases[-1].failed_step == PLAN_FAILED
    with pytest.raises(ValueError, match="accepted plan"):
        _study(S.RUNNING, first, unplanned, resolution=R.FAILED)


def test_a_study_cannot_fail_at_parsing_while_the_parser_runs_outside_it() -> None:
    failed = Phase(question=_question(), steps=(PLAN_FAILED,))
    with pytest.raises(ValueError, match="parsing"):
        _study(S.PARSING, failed, resolution=R.FAILED)


def test_a_report_is_composed_if_and_only_if_the_study_completed() -> None:
    answered = Phase(question=_question(), plan=PLAN, round=_round(_answer()))
    with pytest.raises(ValueError, match="report"):
        _study(S.CLOSING, answered, resolution=R.COMPLETED)
    with pytest.raises(ValueError, match="report"):
        _study(S.CLOSING, answered, report=report())
    _study(S.CLOSING, answered, resolution=R.COMPLETED, report=report())


def test_a_completed_study_ends_at_closing() -> None:
    asked = Phase(question=_question(), plan=PLAN, round=_round(_abstain()))
    with pytest.raises(ValueError, match="closing"):
        _study(S.CONSULTING_EXPERT, asked, resolution=R.COMPLETED, report=report())


def test_question_is_the_first_phase_question() -> None:
    study = _study(S.CLOSING, *_free_loop(2))
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
            values=(Edges(edge_ids=("E12",), network_id="abc123"),),
        )


def test_answer_without_typed_values_must_abstain() -> None:
    with pytest.raises(ValueError, match="typed value"):
        ExpertAnswer(
            answer="E12 is congested", basis=Basis.OBSERVED, confidence=0.9, evidence=EVIDENCE
        )


# --- Study: a step that needed the user ------------------------------------------------------


def _waiting_phase(**kw: Any) -> Phase:
    base: dict[str, Any] = dict(
        question=_question(), plan=PLAN, steps=(OK, WAITING, SKIPPED), needs_user=NEEDS
    )
    base.update(kw)
    return Phase(**base)


def test_a_step_that_needed_the_user_puts_the_study_in_awaiting_user() -> None:
    with pytest.raises(ValueError, match="awaiting_user"):
        _study(S.RUNNING, _waiting_phase())
    with pytest.raises(ValueError, match="awaiting_user"):
        _study(S.RUNNING, _waiting_phase(), resolution=R.FAILED)
    study = _study(S.RUNNING, _waiting_phase(), resolution=R.AWAITING_USER)
    assert study.phases[0].needs_user == NEEDS


def test_a_waiting_study_without_a_message_or_a_step_is_rejected() -> None:
    with pytest.raises(ValueError, match="awaiting_user"):
        _study(
            S.RUNNING,
            Phase(question=_question(), plan=PLAN, steps=(OK,)),
            resolution=R.AWAITING_USER,
        )


def test_a_phase_holds_needs_user_if_and_only_if_a_step_needed_the_user() -> None:
    with pytest.raises(ValueError, match="needs_user"):
        _waiting_phase(needs_user=None)
    with pytest.raises(ValueError, match="needs_user"):
        _waiting_phase(steps=(OK, SKIPPED))


def test_the_steps_after_the_one_that_needed_the_user_are_skipped() -> None:
    with pytest.raises(ValueError, match="skipped"):
        _waiting_phase(steps=(WAITING, OK))


def test_a_step_that_needed_the_user_ends_the_study() -> None:
    first = _waiting_phase(round=_round(_abstain()))
    with pytest.raises(ValueError, match="last phase"):
        _study(S.PLANNING, first, Phase(question=PROPOSED), resolution=R.AWAITING_USER)


def test_a_study_with_a_step_that_needed_the_user_is_not_failed() -> None:
    with pytest.raises(ValueError, match="stops at the first"):
        _waiting_phase(steps=(WAITING, FAILED))
