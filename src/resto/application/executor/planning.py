"""Planning one phase (ADR-0025): the Coordinator call, its `ClarificationRequest` and the plan's
semantic check (`plan_validation`)."""

from __future__ import annotations

from dataclasses import replace

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, draft_of
from resto.application.executor.plan_validation import plan_problems
from resto.application.executor.recorder import StudyRecorder, data
from resto.application.executor.spend import StudySpend
from resto.application.ports.agents.coordinator import PlanningContext
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.step_record import StepError, StepErrorKind, StepRecord, StepStatus
from resto.domain.value_objects.study_plan import ClarificationRequest, StudyPlan


def plan_phase(
    recorder: StudyRecorder, spend: StudySpend, deps: StudyDeps, network_id: str | None
) -> StudyPlan | None:
    """The valid plan of the current phase, recorded as its `plan` step; or nothing, once the
    study awaits the user (a clarification in phase 0) or has failed."""
    k = recorder.phase_index
    phase = recorder.phase
    earlier = tuple(e for p in recorder.study.phases[:-1] for e in p.experiments)
    context = PlanningContext(
        phase=k,
        network_id=network_id,
        experiments=earlier,
        has_historical_demand=deps.has_historical_demand,
    )
    task = {"phase": k, "question": data(phase.question)}
    try:
        coordinator = deps.agents.coordinator
        run = spend.agent_call(lambda: coordinator.plan(phase.question, context))
        output = draft_of(run, "coordinator")
    except StepFailed as failed:
        recorder.record_failure("plan", task, failed)
        return None
    if isinstance(output, ClarificationRequest):
        if k == 0:
            recorder.trace("clarification", {"reason": output.reason})
            recorder.replace_phase(
                replace(phase, clarification=output), status=StudyStatus.AWAITING_USER
            )
            return None
        failure = StepFailed(
            StepError(
                StepErrorKind.AGENT,
                f"the Coordinator could not plan the experiment proposed in round {k}",
                (output.reason, *output.candidates),
            ),
            run.usage,
        )
        recorder.record_failure("plan", task, failure)
        return None
    problems = plan_problems(
        output,
        phase.question,
        phase=k,
        realised={e.arm for e in earlier},
        network_id=network_id,
        has_historical_demand=deps.has_historical_demand,
        networks=deps.networks,
        demands=deps.demands,
        scenarios=deps.scenarios,
        results=deps.results,
    )
    if problems:
        failure = StepFailed(
            StepError(StepErrorKind.AGENT, f"the plan of phase {k} is invalid", tuple(problems)),
            run.usage,
        )
        recorder.record_failure(
            "plan", task, failure, phase=replace(phase, plan=output), pending=output.steps
        )
        return None
    recorder.replace_phase(
        replace(
            phase,
            plan=output,
            steps=(StepRecord("plan", StepStatus.OK, task, usage=run.usage),),
        ),
        status=StudyStatus.RUNNING,
    )
    return output
