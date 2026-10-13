"""Planning one phase (ADR-0025, ADR-0039): the planner call and the plan's semantic check
(`plan_validation`). One path: planner, then validation, then the `plan` step recorded."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from resto.application.ports.repositories import DemandRepository, NetworkRepository
from resto.application.run_study.failures import StepFailed
from resto.application.run_study.plan_validation import plan_problems
from resto.application.run_study.spend import StudySpend
from resto.application.run_study.step_data import data
from resto.domain.entities.study import Study, Transition
from resto.domain.services.planner import PlanningContext, PlanningError
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.step_record import StepError, StepErrorKind, StepRecord, StepStatus
from resto.domain.value_objects.study_plan import StudyPlan

Planner = Callable[[Question, PlanningContext], StudyPlan]
"""The planning function (`resto.domain.services.planner.plan_study` in production). It raises
`PlanningError` for a question it cannot plan. Injected so the tests control the plan without an
agent."""


@dataclass(frozen=True, slots=True)
class PlanStage:
    planner: Planner
    networks: NetworkRepository
    demands: DemandRepository

    def execute(self, study: Study, spend: StudySpend) -> Transition:
        """Plans the current phase and records its `plan` step: accepted when the plan validates,
        otherwise a failed `plan` step of kind `planning` (the planner could not plan it, or the
        plan did not validate). The planner is no agent and spends nothing."""
        k = study.phase_index
        phase = study.current_phase
        network_id = study.network_id
        realised = study.realised_arms
        task = {"phase": k, "question": data(phase.question)}
        try:
            plan = self.planner(
                phase.question, PlanningContext(phase=k, network_id=network_id, realised=realised)
            )
        except PlanningError as e:
            error = StepError(StepErrorKind.PLANNING, f"the question cannot be planned: {e}")
            return study.record_failure(StepFailed(error).record("plan", task))
        problems = plan_problems(
            plan,
            phase.question,
            phase=k,
            realised=realised,
            network_id=network_id,
            networks=self.networks,
            demands=self.demands,
        )
        if problems:
            error = StepError(
                StepErrorKind.PLANNING, f"the plan of phase {k} is invalid", tuple(problems)
            )
            return study.reject_plan(plan, StepFailed(error).record("plan", task))
        return study.accept_plan(plan, StepRecord("plan", StepStatus.OK, task))
