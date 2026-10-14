"""`obtain_demand`: the Demand Generator finds, asks for or generates the demand (ADR-0037)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from resto.application.ports.agents.demand_generator import DemandGeneratorAgent
from resto.application.ports.llm import AgentRun
from resto.application.ports.repositories import DemandRepository
from resto.application.promoters.demand import DemandPromoter
from resto.application.run_study.failures import StepNeedsUser, draft_of, fail, promote
from resto.application.run_study.steps import StepContext
from resto.domain.entities.study import Transition
from resto.domain.services.experiment_design import study_window
from resto.domain.services.reuse import accepts_found_demand
from resto.domain.value_objects.drafts import DemandDraft
from resto.domain.value_objects.outcomes import Found, NeedsUser
from resto.domain.value_objects.step_record import StepErrorKind
from resto.domain.value_objects.study_plan import ObtainDemandStep
from resto.domain.value_objects.tasks import ObtainDemandTask


@dataclass(frozen=True, slots=True)
class ObtainDemandExecutor:
    generator: DemandGeneratorAgent
    demands: DemandRepository
    promoter: DemandPromoter
    max_calibration_rounds: int
    """Calibration rounds for a step that sets none (`RESTO_CALIBRATION_MAX_ROUNDS`)."""

    def execute(self, step: ObtainDemandStep, ctx: StepContext) -> Transition:
        rounds = step.max_calibration_rounds
        task = ObtainDemandTask(
            network_id=dict(step.refs())["network"],
            seed=step.seed,
            demand_ref=step.demand_ref,
            window=study_window(ctx.study.current_phase.question),
            tolerance=step.tolerance,
            max_calibration_rounds=self.max_calibration_rounds if rounds is None else rounds,
        )
        run = ctx.spend.agent_call(lambda: self.generator.obtain(task))
        outcome = draft_of(run, "demand_generator")
        if isinstance(outcome, NeedsUser):
            raise StepNeedsUser(outcome, run.usage)
        if isinstance(outcome, Found):
            stored = self.demands.get(outcome.id)
            if not accepts_found_demand(outcome, stored, network_id=task.network_id):
                fail(
                    StepErrorKind.AGENT,
                    f"the Demand Generator found demand {outcome.id!r}, which is not stored "
                    f"for network {task.network_id!r}",
                    usage=run.usage,
                )
            demand_id = outcome.id
        else:
            draft_run = cast("AgentRun[DemandDraft]", run)
            demand = promote(lambda: self.promoter.promote(draft_run, task), run.usage)
            self.demands.store(demand)
            demand_id = demand.demand_id
        return ctx.record(step, (demand_id,), run.usage)
