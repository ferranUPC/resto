"""The study flow (ADR-0023, ADR-0030, ADR-0041 §5): a loop that asks the study what comes next,
performs it and applies the outcome. It holds no rule about the study's state: the study answers
`next_action` and every phase is a function of its own module; the loop owns the study's network id
and hands it to the planning phase."""

from __future__ import annotations

from typing import assert_never

from resto.application.executor.closing import close
from resto.application.executor.deps import StudyDeps, StudySettings
from resto.application.executor.expert_round import ask_expert_round
from resto.application.executor.parsing import parse_request
from resto.application.executor.planning import plan_phase
from resto.application.executor.recorder import StudyRecorder
from resto.application.executor.spend import StudySpend
from resto.application.executor.steps import execute_plan
from resto.application.ports.tracing import ModelCall
from resto.domain.entities.study import Study
from resto.domain.services.ids import new_id
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.step_record import Usage
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


def execute_study(
    text: str,
    mode: Mode | None,
    deps: StudyDeps,
    settings: StudySettings,
    *,
    max_rounds: int,
) -> Study:
    """Runs the user's request until the `Study` has a resolution (`completed`, `failed` or
    `awaiting_user`) and returns it. The study is created at the request, with parsing as its
    first stage; `mode`, when given, is the user's choice and overrides the Input Parser's."""
    recorder = StudyRecorder(
        Study.open(new_id(), text, mode, max_rounds=max_rounds),
        studies=deps.studies,
        events=deps.events,
    )
    study_id = recorder.study.study_id

    def model_call(usage: Usage) -> None:
        deps.tracer.emit(study_id, ModelCall(usage))

    spend = StudySpend(settings.budget, model_call)
    network_id: str | None = None
    while True:
        match recorder.study.next_action():
            case Finished():
                return recorder.study
            case ParseRequest():
                parse_request(recorder, spend, deps)
            case PlanPhase():
                plan_phase(recorder, deps, network_id)
            case RunPlan(plan):
                network_id = execute_plan(plan, recorder, spend, deps, settings)
            case ConsultExpert():
                recorder.apply(recorder.study.consult_expert())
            case AskExpert():
                ask_expert_round(recorder, spend, deps)
            case OpenPhase():
                recorder.apply(recorder.study.open_phase())
            case Close(final):
                close(final, recorder, spend, deps)
            case action:
                assert_never(action)
