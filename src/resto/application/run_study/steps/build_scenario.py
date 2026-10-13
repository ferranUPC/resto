"""`build_scenario`: reuse the stored scenario with ok results, else draft and build it."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.agents.scenario_builder import ScenarioBuilderAgent
from resto.application.ports.repositories import ResultRepository, ScenarioRepository
from resto.application.run_study.failures import draft_of, fail, promote
from resto.application.run_study.steps import StepContext
from resto.application.use_cases.build_scenario import BuildScenario
from resto.domain.entities.study import Transition
from resto.domain.services.ids import scenario_id_for
from resto.domain.services.reuse import reused_scenario_results
from resto.domain.value_objects.step_record import StepErrorKind
from resto.domain.value_objects.study_plan import BuildScenarioStep
from resto.domain.value_objects.tasks import ScenarioTask


@dataclass(frozen=True, slots=True)
class BuildScenarioExecutor:
    builder: ScenarioBuilderAgent
    scenarios: ScenarioRepository
    results: ResultRepository
    build_scenario: BuildScenario

    def execute(self, step: BuildScenarioStep, ctx: StepContext) -> Transition:
        ids = dict(step.refs())
        task = ScenarioTask(
            network_id=ids["network"],
            demand_id=ids["demand"],
            interventions=step.interventions,
            context_tags=step.context_tags,
        )
        requested = scenario_id_for(
            task.network_id, task.demand_id, task.interventions, task.context_tags
        )
        stored_ids = reused_scenario_results(
            self.scenarios.get(requested), self.results.list(requested)
        )
        if stored_ids:
            return ctx.record(step, (requested,), reused=stored_ids)
        run = ctx.spend.agent_call(lambda: self.builder.build(task))
        draft = draft_of(run, "scenario_builder")
        if draft.rejected:
            fail(
                StepErrorKind.USER_INPUT,
                f"the Scenario Builder rejected {len(draft.rejected)} intervention(s)",
                *(f"{r.intervention.type}: {r.reason}" for r in draft.rejected),
                usage=run.usage,
            )
        scenario = promote(lambda: self.build_scenario.execute(task, run), run.usage)
        return ctx.record(step, (scenario.scenario_id,), run.usage)
