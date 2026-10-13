"""Planning one phase (ADR-0025, ADR-0039): the planner call and the plan's semantic check
(`plan_validation`). One path: planner, then validation, then the `plan` step recorded."""

from __future__ import annotations

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed
from resto.application.executor.plan_validation import plan_problems
from resto.application.executor.recorder import StudyRecorder, data
from resto.domain.services.planner import PlanningContext, PlanningError
from resto.domain.value_objects.step_record import StepError, StepErrorKind, StepRecord, StepStatus


def plan_phase(recorder: StudyRecorder, deps: StudyDeps, network_id: str | None) -> None:
    """Plans the current phase and records its `plan` step: accepted when the plan validates,
    otherwise a failed `plan` step of kind `planning` (the planner could not plan it, or the plan
    did not validate)."""
    study = recorder.study
    k = study.phase_index
    phase = study.current_phase
    realised = study.realised_arms
    task = {"phase": k, "question": data(phase.question)}
    try:
        plan = deps.planner(
            phase.question, PlanningContext(phase=k, network_id=network_id, realised=realised)
        )
    except PlanningError as e:
        error = StepError(StepErrorKind.PLANNING, f"the question cannot be planned: {e}")
        recorder.apply(study.record_failure(StepFailed(error).record("plan", task)))
        return
    problems = plan_problems(
        plan,
        phase.question,
        phase=k,
        realised=realised,
        network_id=network_id,
        networks=deps.networks,
        demands=deps.demands,
        scenarios=deps.scenarios,
    )
    if problems:
        error = StepError(
            StepErrorKind.PLANNING, f"the plan of phase {k} is invalid", tuple(problems)
        )
        recorder.apply(study.reject_plan(plan, StepFailed(error).record("plan", task)))
        return
    recorder.apply(study.accept_plan(plan, StepRecord("plan", StepStatus.OK, task)))
