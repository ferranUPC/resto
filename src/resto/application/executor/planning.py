"""Planning one phase (ADR-0025, ADR-0039): the planner call and the plan's semantic check
(`plan_validation`). One path: planner, then validation, then the `plan` step recorded."""

from __future__ import annotations

from dataclasses import replace

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed
from resto.application.executor.plan_validation import plan_problems
from resto.application.executor.recorder import StudyRecorder, data
from resto.domain.services.planner import PlanningContext, PlanningError
from resto.domain.value_objects.step_record import StepError, StepErrorKind, StepRecord, StepStatus
from resto.domain.value_objects.study_plan import StudyPlan


def plan_phase(
    recorder: StudyRecorder, deps: StudyDeps, network_id: str | None
) -> StudyPlan | None:
    """The valid plan of the current phase, recorded as its `plan` step; or nothing, once the
    planner could not plan it or the plan did not validate (both a failed `plan` step of kind
    `planning`)."""
    k = recorder.phase_index
    phase = recorder.phase
    realised = _realised(recorder)
    task = {"phase": k, "question": data(phase.question)}
    try:
        plan = deps.planner(
            phase.question, PlanningContext(phase=k, network_id=network_id, realised=realised)
        )
    except PlanningError as e:
        error = StepError(StepErrorKind.PLANNING, f"the question cannot be planned: {e}")
        recorder.record_failure("plan", task, StepFailed(error))
        return None
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
        recorder.record_failure(
            "plan", task, StepFailed(error), phase=replace(phase, plan=plan), pending=plan.steps
        )
        return None
    recorder.plan_made(plan, StepRecord("plan", StepStatus.OK, task))
    return plan


def _realised(recorder: StudyRecorder) -> tuple[str, ...]:
    """The arms the phases before the current one realised, in order."""
    return tuple(e.arm for p in recorder.study.phases[:-1] for e in p.experiments)
