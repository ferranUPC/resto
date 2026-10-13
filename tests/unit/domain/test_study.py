from typing import Any

import pytest

from resto.domain.entities.study import Phase, Study, StudyResolution, StudyStage
from resto.domain.events import (
    ExpertRoundHeld,
    NetworksAdded,
    NotesWritten,
    PhaseStarted,
    PlanMade,
    ReportComposed,
    SimulationsRecorded,
    StepTraced,
    StudyCreated,
)
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.outcomes import NeedsUser, WindowMissing
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import (
    StepError,
    StepErrorKind,
    StepRecord,
    StepStatus,
    Usage,
)
from resto.domain.value_objects.study_action import (
    AskExpert,
    Close,
    ConsultExpert,
    Finished,
    OpenPhase,
    ParseRequest,
    PlanPhase,
    RunPlan,
)
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    RunSimulationStep,
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


TEXT = "what happens at peak?"
PARSED = StepRecord("parse", StepStatus.OK, {"text": TEXT}, usage=Usage(input_tokens=50))
PARSE_FAILED = StepRecord(
    "parse",
    StepStatus.FAILED,
    {"text": TEXT},
    error=StepError(StepErrorKind.AGENT, "no question"),
    usage=Usage(input_tokens=50),
)


def _study(stage: StudyStage, *phases: Phase, **kw: Any) -> Study:
    kw.setdefault("parse", PARSED)
    return Study("s", stage, phases, TEXT, **kw)


# --- Study: the parse step (ADR-0041 §2) ------------------------------------------------------


def test_a_study_without_phases_is_at_parsing() -> None:
    with pytest.raises(ValueError, match="at parsing"):
        _study(S.PLANNING, parse=None)
    _study(S.PARSING, parse=None)


def test_a_study_with_phases_has_an_ok_parse_step() -> None:
    phase = Phase(question=_question())
    with pytest.raises(ValueError, match="ok parse"):
        _study(S.PLANNING, phase, parse=None)
    with pytest.raises(ValueError, match="ok parse"):
        _study(S.PLANNING, phase, parse=PARSE_FAILED)
    with pytest.raises(ValueError, match="Input Parser"):
        _study(S.PLANNING, phase, parse=PLANNED)


def test_a_study_failed_at_parsing_has_a_failed_parse_step_and_no_phases() -> None:
    study = _study(S.PARSING, resolution=R.FAILED, parse=PARSE_FAILED)
    assert study.failed_step == PARSE_FAILED
    with pytest.raises(ValueError, match="failed"):
        _study(S.PARSING, resolution=R.FAILED, parse=None)
    with pytest.raises(ValueError, match="failed if and only if"):
        _study(S.PARSING, resolution=R.FAILED, parse=PARSED)
    with pytest.raises(ValueError, match="failed if and only if"):
        _study(S.PARSING, parse=PARSE_FAILED)


def test_an_open_study_at_parsing_has_no_parse_step() -> None:
    with pytest.raises(ValueError, match="no parse step"):
        _study(S.PARSING, parse=PARSED)


def test_a_study_without_phases_is_open_or_failed() -> None:
    with pytest.raises(ValueError, match="open or failed"):
        _study(S.PARSING, resolution=R.AWAITING_USER, parse=PARSED)
    with pytest.raises(ValueError, match="open or failed"):
        _study(S.PARSING, resolution=R.COMPLETED, parse=PARSED)


def test_a_study_requires_the_text_of_the_request() -> None:
    with pytest.raises(ValueError, match="text"):
        Study("s", S.PARSING, (), " ")


def test_the_question_keeps_the_mode_the_user_chose() -> None:
    phase = Phase(question=_question(mode=Mode.FREE))
    with pytest.raises(ValueError, match="mode"):
        _study(S.PLANNING, phase, mode=Mode.FORCED)
    _study(S.PLANNING, phase, mode=Mode.FREE)


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


def test_a_study_with_a_question_is_at_parsing_only_when_it_is_ambiguous() -> None:
    with pytest.raises(ValueError, match="parsing"):
        _study(S.PARSING, Phase(question=_question()))


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


# --- Study: transitions (ADR-0041 §4) -------------------------------------------------------

USAGE = Usage(input_tokens=50)
BASELINE, TREATMENT = ExperimentRole.BASELINE, ExperimentRole.TREATMENT


def test_opening_a_study_starts_at_the_request_with_no_phases() -> None:
    study, events = Study.open("s1", TEXT, Mode.FORCED, max_rounds=2)

    assert (study.study_id, study.stage, study.resolution) == ("s1", S.PARSING, None)
    assert (study.text, study.mode, study.phases, study.parse) == (TEXT, Mode.FORCED, (), None)
    assert study.max_rounds == 2
    assert events == (StudyCreated(TEXT, Mode.FORCED),)


def test_a_new_study_needs_the_input_parser() -> None:
    study, _ = Study.open("s1", TEXT, max_rounds=2)

    assert study.next_action() == ParseRequest(TEXT)


def test_the_question_opens_phase_0_at_planning() -> None:
    study, _ = Study.open("s1", TEXT, max_rounds=2)

    study, events = study.accept_question(PARSED, _question())

    assert (study.stage, study.resolution) == (S.PLANNING, None)
    assert study.phases == (Phase(question=_question()),)
    assert study.parse == PARSED
    assert events == (_traced(PARSED), PhaseStarted(0))


def test_the_users_mode_overrides_the_parsers() -> None:
    study, _ = Study.open("s1", TEXT, Mode.FORCED, max_rounds=2)

    study, _ = study.accept_question(PARSED, _question(mode=Mode.FREE))

    assert study.question.mode is Mode.FORCED


def test_an_ambiguous_question_waits_for_the_user_at_parsing() -> None:
    ambiguous = _question(ambiguities=("which network?",))
    study, _ = Study.open("s1", TEXT, max_rounds=3)

    study, events = study.accept_question(PARSED, ambiguous)

    assert (study.stage, study.resolution) == (S.PARSING, R.AWAITING_USER)
    assert study.parse == PARSED
    assert events == (_traced(PARSED), PhaseStarted(0))
    assert study.next_action() == Finished()


def test_a_failed_parse_fails_the_study_at_parsing_with_no_phases() -> None:
    study, _ = Study.open("s1", TEXT, max_rounds=3)

    study, events = study.record_failure(PARSE_FAILED)

    assert (study.stage, study.resolution) == (S.PARSING, R.FAILED)
    assert (study.phases, study.parse) == ((), PARSE_FAILED)
    assert events == (_traced(PARSE_FAILED),)
    assert study.next_action() == Finished()


def test_the_question_is_accepted_only_at_parsing() -> None:
    with pytest.raises(ValueError, match="parsing"):
        _opened().accept_question(PARSED, _question())


def test_the_question_comes_with_an_ok_parse_step() -> None:
    study, _ = Study.open("s1", TEXT, max_rounds=3)
    with pytest.raises(ValueError, match="ok parse"):
        study.accept_question(PARSE_FAILED, _question())


def test_a_study_has_no_question_before_the_parser_runs() -> None:
    study, _ = Study.open("s1", TEXT, max_rounds=3)
    with pytest.raises(ValueError, match="no question"):
        _ = study.question


FULL_PLAN = StudyPlan(
    network_id=FromStep(0),
    rationale="the base and the closure of E12",
    steps=(
        ObtainNetworkStep("RIVERSIDE"),
        ObtainDemandStep(FromStep(0), seed=1, depends_on=(0,)),
        BuildScenarioStep(
            FromStep(0), FromStep(1), "base", BASELINE, "the base", depends_on=(0, 1)
        ),
        RunSimulationStep(FromStep(2), seeds=(1, 2), depends_on=(2,)),
        BuildScenarioStep(
            FromStep(0), FromStep(1), "closed", TREATMENT, "E12 closed", depends_on=(0, 1)
        ),
        RunSimulationStep(FromStep(4), seeds=(1, 2), depends_on=(4,)),
    ),
)
NETWORK = StepRecord("obtain_network", StepStatus.OK, produced_ids=("net1",))
DEMAND = StepRecord("obtain_demand", StepStatus.OK, produced_ids=("dem1",))
BUILT_BASE = StepRecord("build_scenario", StepStatus.OK, produced_ids=("scen-base",))
RAN_BASE = StepRecord("run_simulation", StepStatus.OK, produced_ids=("rb1", "rb2"))
BUILT_CLOSED = StepRecord("build_scenario", StepStatus.OK, produced_ids=("scen-closed",))
RAN_CLOSED = StepRecord("run_simulation", StepStatus.OK, produced_ids=("rc1", "rc2"))


def _opened(question: Question | None = None, *, max_rounds: int = 3) -> Study:
    """A study whose Input Parser produced `question`: phase 0 at planning."""
    parsing, _ = Study.open("s1", TEXT, max_rounds=max_rounds)
    return parsing.accept_question(PARSED, question or _question())[0]


def _traced(record: StepRecord, phase: int = 0) -> StepTraced:
    return StepTraced(
        phase, record.tool, record.status, record.produced_ids, record.usage, record.error
    )


def test_accepting_a_plan_records_its_step_and_starts_running() -> None:
    study, events = _opened().accept_plan(FULL_PLAN, PLANNED)

    assert (study.stage, study.resolution) == (S.RUNNING, None)
    assert study.phases[0].plan == FULL_PLAN
    assert study.phases[0].steps == (PLANNED,)
    assert events == (PlanMade(0, FULL_PLAN),)


def test_a_plan_is_accepted_only_at_planning() -> None:
    running, _ = _opened().accept_plan(FULL_PLAN, PLANNED)
    with pytest.raises(ValueError, match="planning"):
        running.accept_plan(FULL_PLAN, PLANNED)


def test_a_failed_planning_fails_the_study_at_planning_with_no_plan() -> None:
    study, events = _opened().record_failure(PLAN_FAILED)

    assert (study.stage, study.resolution) == (S.PLANNING, R.FAILED)
    assert study.phases[0].plan is None
    assert study.phases[0].steps == (PLAN_FAILED,)
    assert events == (_traced(PLAN_FAILED),)


def test_rejecting_a_plan_keeps_it_with_every_step_skipped() -> None:
    study, events = _opened().reject_plan(FULL_PLAN, PLAN_FAILED)

    assert (study.stage, study.resolution) == (S.PLANNING, R.FAILED)
    phase = study.phases[0]
    assert phase.plan == FULL_PLAN
    assert phase.steps[0] == PLAN_FAILED
    assert [s.tool for s in phase.steps[1:]] == [s.kind for s in FULL_PLAN.steps]
    assert {s.status for s in phase.steps[1:]} == {StepStatus.SKIPPED}
    assert events == (_traced(PLAN_FAILED),)


def _running(*records: StepRecord, plan: StudyPlan = FULL_PLAN) -> Study:
    study, _ = _opened().accept_plan(plan, PLANNED)
    for record in records:
        study, _ = study.record_step(record)
    return study


def test_an_ok_step_is_appended_to_the_current_phase() -> None:
    study, events = _running().record_step(NETWORK)

    assert study.phases[0].steps == (PLANNED, NETWORK)
    assert (study.stage, study.resolution) == (S.RUNNING, None)
    assert events == (_traced(NETWORK),)


def test_a_recorded_step_is_the_next_step_of_the_plan() -> None:
    with pytest.raises(ValueError, match="obtain_network"):
        _running().record_step(DEMAND)
    with pytest.raises(ValueError, match="every step"):
        _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED).record_step(OK)


def test_a_built_scenario_becomes_an_experiment_of_its_arm() -> None:
    study, _ = _running(NETWORK, DEMAND).record_step(BUILT_BASE)

    assert study.phases[0].experiments == (Experiment("scen-base", "base", BASELINE, "the base"),)


def test_a_reused_scenario_is_an_experiment_with_its_stored_results() -> None:
    study, _ = _running(NETWORK, DEMAND).record_step(BUILT_BASE, reused_result_ids=("rb1",))

    (experiment,) = study.phases[0].experiments
    assert (experiment.result_ids, experiment.reused) == (("rb1",), True)


def test_a_run_joins_the_experiment_of_the_step_that_built_its_scenario() -> None:
    study = _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED)

    base, closed = study.phases[0].experiments
    assert (base.scenario_id, base.result_ids) == ("scen-base", ("rb1", "rb2"))
    assert (closed.scenario_id, closed.result_ids) == ("scen-closed", ("rc1", "rc2"))


def test_a_run_on_a_reused_scenario_adds_its_results_without_repeats() -> None:
    reused, _ = _running(NETWORK, DEMAND).record_step(BUILT_BASE, reused_result_ids=("rb1",))

    study, _ = reused.record_step(RAN_BASE, reused_result_ids=("rb1",))

    assert study.phases[0].experiments[0].result_ids == ("rb1", "rb2")


def test_an_ok_simulation_step_tells_its_new_results_from_the_reused_ones() -> None:
    built = _running(NETWORK, DEMAND, BUILT_BASE)

    _, events = built.record_step(RAN_BASE, reused_result_ids=("rb1",))

    assert events == (
        _traced(RAN_BASE),
        SimulationsRecorded(0, "scen-base", new_result_ids=("rb2",), reused_result_ids=("rb1",)),
    )


def test_a_run_on_a_stored_scenario_joins_no_experiment() -> None:
    plan = StudyPlan(
        network_id="net1",
        rationale="results exist",
        steps=(ObtainNetworkStep("RIVERSIDE"), RunSimulationStep("scen-stored", seeds=(1,))),
    )
    ran = StepRecord("run_simulation", StepStatus.OK, produced_ids=("r1",))

    study, events = _running(NETWORK, plan=plan).record_step(ran)

    assert study.phases[0].experiments == ()
    assert events[-1] == SimulationsRecorded(0, "scen-stored", ("r1",), ())


def test_only_scenarios_and_runs_reuse_results_and_only_those_they_hold() -> None:
    with pytest.raises(ValueError, match="reuse"):
        _running().record_step(NETWORK, reused_result_ids=("r1",))
    with pytest.raises(ValueError, match="reuse"):
        _running(NETWORK, DEMAND, BUILT_BASE).record_step(RAN_BASE, reused_result_ids=("r9",))


def test_a_failed_step_skips_the_rest_of_the_plan() -> None:
    failed = StepRecord(
        "build_scenario",
        StepStatus.FAILED,
        error=StepError(StepErrorKind.USER_INPUT, "unknown edge"),
    )

    study, events = _running(NETWORK, DEMAND).record_failure(failed)

    assert (study.stage, study.resolution) == (S.RUNNING, R.FAILED)
    assert [s.status for s in study.phases[0].steps[3:]] == [
        StepStatus.FAILED,
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
        StepStatus.SKIPPED,
    ]
    assert events == (_traced(failed),)


def test_a_step_that_needs_the_user_skips_the_rest_and_waits_for_the_user() -> None:
    study, events = _running(NETWORK).record_needs_user(WAITING, NEEDS)

    assert (study.stage, study.resolution) == (S.RUNNING, R.AWAITING_USER)
    phase = study.phases[0]
    assert phase.needs_user == NEEDS
    assert [s.status for s in phase.steps[2:]] == [StepStatus.NEEDS_USER] + [StepStatus.SKIPPED] * 4
    assert events == (_traced(WAITING),)


def test_a_closed_study_takes_no_more_transitions() -> None:
    failed, _ = _opened().record_failure(PLAN_FAILED)
    with pytest.raises(ValueError, match="failed"):
        failed.record_failure(PLAN_FAILED)


def _ran(**kw: Any) -> Study:
    """Phase 0 with every step of FULL_PLAN recorded."""
    return _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED, **kw)


def test_networks_are_added_without_repeats() -> None:
    study, events = _running().add_networks("net1", "net2", "net1")
    assert study.network_ids == ("net1", "net2")
    assert events == (NetworksAdded(("net1", "net2")),)

    again, events = study.add_networks("net2", "net3")
    assert again.network_ids == ("net1", "net2", "net3")
    assert events == (NetworksAdded(("net3",)),)


def test_adding_only_known_networks_changes_nothing() -> None:
    study, _ = _running().add_networks("net1")
    assert study.add_networks("net1") == (study, ())


def test_the_expert_is_consulted_once_every_step_of_the_plan_is_recorded() -> None:
    with pytest.raises(ValueError, match="every step"):
        _running(NETWORK).consult_expert()

    study, events = _ran().consult_expert()

    assert (study.stage, events) == (S.CONSULTING_EXPERT, ())


def _consulting(**kw: Any) -> Study:
    return _ran(**kw).consult_expert()[0]


def test_an_expert_answer_moves_the_study_to_closing() -> None:
    study, events = _consulting().record_expert_round(EXPERT_OK, _round(_answer()))

    assert study.stage is S.CLOSING
    assert study.phases[0].round == _round(_answer())
    assert study.phases[0].steps[-1] == EXPERT_OK
    assert events == (_traced(EXPERT_OK), ExpertRoundHeld(0, 1))


def test_an_expert_round_that_asks_for_a_simulation_opens_the_proposed_phase() -> None:
    asked, _ = _consulting().record_expert_round(EXPERT_OK, _round(_abstain()))
    assert asked.stage is S.CONSULTING_EXPERT

    study, events = asked.open_phase()

    assert (study.stage, study.phase_index) == (S.PLANNING, 1)
    assert study.current_phase == Phase(question=PROPOSED)
    assert events == (PhaseStarted(1),)


def test_a_phase_opens_only_on_an_experiment_the_expert_proposed() -> None:
    with pytest.raises(ValueError, match="consulting_expert"):
        _ran().open_phase()
    with pytest.raises(ValueError, match="proposed"):
        _consulting().open_phase()


def _second_phase(question: Question, max_rounds: int = 3) -> Study:
    study, _ = _opened(question, max_rounds=max_rounds).accept_plan(PLAN, PLANNED)
    study, _ = study.record_step(NETWORK)
    study, _ = study.consult_expert()
    study, _ = study.record_expert_round(EXPERT_OK, _round(_abstain()))
    return study.open_phase()[0]


def test_the_next_round_counts_the_rounds_held() -> None:
    assert _consulting().next_round_no == 1
    assert _second_phase(_question()).next_round_no == 2


def test_round_max_rounds_of_a_free_study_is_forced_by_the_limit() -> None:
    study = _second_phase(_question(), max_rounds=2)
    assert study.next_round_forced_by_limit
    study, _ = study.accept_plan(PLAN, PLANNED)
    study, _ = study.record_step(NETWORK)
    study, _ = study.consult_expert()

    closed, events = study.record_expert_round(EXPERT_OK, _round(_answer()))

    assert closed.rounds[-1].forced_by_limit
    assert events[-1] == ExpertRoundHeld(1, 2)


def test_only_the_last_round_allowed_is_forced_by_the_limit_and_only_in_free_mode() -> None:
    assert not _consulting().next_round_forced_by_limit
    forced, _ = _opened(_question(mode=Mode.FORCED), max_rounds=1).accept_plan(PLAN, PLANNED)
    assert not forced.next_round_forced_by_limit


def test_result_ids_are_every_experiments_results_in_order_without_repeats() -> None:
    rebuild = StudyPlan(
        network_id="net1",
        rationale="the base again, found stored",
        steps=(
            ObtainNetworkStep("RIVERSIDE"),
            ObtainDemandStep(FromStep(0), seed=1, depends_on=(0,)),
            BuildScenarioStep(
                FromStep(0), FromStep(1), "base", BASELINE, "again", depends_on=(0, 1)
            ),
        ),
    )
    study, _ = _consulting().record_expert_round(EXPERT_OK, _round(_abstain()))
    study, _ = study.open_phase()
    study, _ = study.accept_plan(rebuild, PLANNED)
    study, _ = study.record_step(NETWORK)
    study, _ = study.record_step(DEMAND)

    study, _ = study.record_step(BUILT_BASE, reused_result_ids=("rb1", "rb2"))

    assert study.result_ids == ("rb1", "rb2", "rc1", "rc2")


def test_realised_arms_are_those_of_the_phases_before_the_current_one() -> None:
    study, _ = _ran().consult_expert()
    assert study.realised_arms == ()
    study, _ = study.record_expert_round(EXPERT_OK, _round(_abstain()))
    study, _ = study.open_phase()

    assert study.realised_arms == ("base", "closed")


def _closing() -> Study:
    return _consulting().record_expert_round(EXPERT_OK, _round(_answer()))[0]


def test_notes_are_recorded_at_closing() -> None:
    with pytest.raises(ValueError, match="closing"):
        _consulting().record_notes(("n1",))

    study, events = _closing().record_notes(("n1", "n2"))

    assert study.note_ids == ("n1", "n2")
    assert events == (NotesWritten(("n1", "n2")),)


def test_the_report_completes_the_study() -> None:
    composed = StepRecord("compose_report", StepStatus.OK)

    study, events = _closing().complete(composed, report())

    assert (study.stage, study.resolution, study.report) == (S.CLOSING, R.COMPLETED, report())
    assert study.phases[0].steps[-1] == composed
    assert events == (_traced(composed), ReportComposed())


def test_a_failed_report_fails_the_study_at_closing() -> None:
    study, _ = _closing().record_failure(COMPOSE_FAILED)
    assert (study.stage, study.resolution) == (S.CLOSING, R.FAILED)


# --- Study: next_action (ADR-0041 §5) -------------------------------------------------------


def test_a_new_study_plans_its_first_phase() -> None:
    assert _opened().next_action() == PlanPhase()


def test_a_running_study_runs_the_plan_it_accepted() -> None:
    assert _running().next_action() == RunPlan(FULL_PLAN)
    assert _running(NETWORK, DEMAND).next_action() == RunPlan(FULL_PLAN)


def test_a_study_that_recorded_every_step_consults_the_expert() -> None:
    done = _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED)

    assert done.next_action() == ConsultExpert()


def test_a_study_consulting_the_expert_asks_it() -> None:
    done = _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED)
    consulting, _ = done.consult_expert()

    assert consulting.next_action() == AskExpert()


def test_an_expert_who_asks_for_a_simulation_opens_a_phase() -> None:
    done = _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED)
    consulting, _ = done.consult_expert()
    asked, _ = consulting.record_expert_round(EXPERT_OK, _round(_abstain()))

    assert asked.stage is S.CONSULTING_EXPERT
    assert asked.next_action() == OpenPhase()
    reopened, _ = asked.open_phase()
    assert reopened.next_action() == PlanPhase()


def test_an_expert_who_answers_closes_the_study() -> None:
    done = _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED)
    consulting, _ = done.consult_expert()
    final = _round(_answer())
    closing, _ = consulting.record_expert_round(EXPERT_OK, final)

    assert closing.next_action() == Close(final)


def test_a_resolved_study_needs_nothing() -> None:
    failed, _ = _opened().record_failure(PLAN_FAILED)
    waiting = _opened(_question(ambiguities=("which network?",)))
    done = _running(NETWORK, DEMAND, BUILT_BASE, RAN_BASE, BUILT_CLOSED, RAN_CLOSED)
    closing, _ = done.consult_expert()[0].record_expert_round(EXPERT_OK, _round(_answer()))
    completed, _ = closing.complete(StepRecord("compose_report", StepStatus.OK), report())

    for study in (failed, waiting, completed):
        assert study.next_action() == Finished()
    assert (failed.resolution, waiting.resolution, completed.resolution) == (
        R.FAILED,
        R.AWAITING_USER,
        R.COMPLETED,
    )


def test_a_study_that_needed_the_user_needs_nothing() -> None:
    waiting, _ = _running().record_needs_user(
        StepRecord("obtain_network", StepStatus.NEEDS_USER), NEEDS
    )

    assert (waiting.stage, waiting.resolution) == (S.RUNNING, R.AWAITING_USER)
    assert waiting.next_action() == Finished()
