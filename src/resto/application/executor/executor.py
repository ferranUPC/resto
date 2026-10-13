"""The study flow (ADR-0023, ADR-0030): the phase loop and nothing else. Every phase is a
function of its own module; the loop owns the study's network id and the last evidence ledger and
hands them to the phases that read them."""

from __future__ import annotations

from resto.application.executor.closing import compose, write_notes
from resto.application.executor.deps import StudyDeps, StudySettings
from resto.application.executor.expert_round import ask_expert_round
from resto.application.executor.planning import plan_phase
from resto.application.executor.recorder import StudyRecorder
from resto.application.executor.spend import StudySpend
from resto.application.executor.steps import execute_plan
from resto.domain.entities.study import Study, StudyResolution
from resto.domain.services.ids import new_id
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.step_record import Usage


def execute_study(
    question: Question,
    parse_usage: Usage,
    deps: StudyDeps,
    settings: StudySettings,
    *,
    max_rounds: int,
) -> Study:
    """Runs a parsed `Question` until the `Study` has a resolution (`completed`, `failed` or
    `awaiting_user`) and returns it. `parse_usage` is what the Input Parser spent: its call is
    the study's first."""
    recorder = StudyRecorder(
        Study.open(new_id(), question, parse_usage, max_rounds=max_rounds),
        studies=deps.studies,
        tracer=deps.tracer,
    )
    recorder.model_call(parse_usage)
    spend = StudySpend(settings.budget, parse_usage, recorder.model_call)
    if recorder.study.resolution is StudyResolution.AWAITING_USER:
        return recorder.study
    network_id: str | None = None
    while True:
        plan = plan_phase(recorder, deps, network_id)
        if plan is None:
            return recorder.study
        network_id = execute_plan(plan, recorder, spend, deps, settings)
        if network_id is None:
            return recorder.study
        recorder.apply(recorder.study.consult_expert())
        answered = ask_expert_round(recorder, spend, deps)
        if answered is None:
            return recorder.study
        final, ledger = answered
        if final.answer.needs_simulation:
            recorder.apply(recorder.study.open_phase())
            continue
        write_notes(
            final,
            ledger,
            recorder,
            spend,
            deps.networks,
            deps.scenarios,
            deps.agents.note_writer,
            deps.write_note,
        )
        compose(recorder, spend, deps)
        return recorder.study
