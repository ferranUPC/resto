"""`run_simulation`: one batch run per seed, except seeds with a stored ok result."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.repositories import ResultRepository, ScenarioRepository
from resto.application.run_study.failures import fail
from resto.application.run_study.steps import StepContext
from resto.application.use_cases.run_simulation import RunSimulation, attempt_dir
from resto.domain.constants import DEFAULT_SEEDS
from resto.domain.entities.simulation_result import RunMode, RunStatus
from resto.domain.entities.study import Transition
from resto.domain.services.ids import result_id_for
from resto.domain.services.reuse import reused_results, seeds_to_run
from resto.domain.value_objects.step_record import StepErrorKind, Usage
from resto.domain.value_objects.study_plan import RunSimulationStep


@dataclass(frozen=True, slots=True)
class RunSimulationExecutor:
    scenarios: ScenarioRepository
    results: ResultRepository
    run_simulation: RunSimulation

    def execute(self, step: RunSimulationStep, ctx: StepContext) -> Transition:
        scenario_id = dict(step.refs())["scenario"]
        scenario = self.scenarios.get(scenario_id)
        if scenario is None:
            fail(StepErrorKind.AGENT, f"scenario {scenario_id!r} is not stored")
        if scenario.is_online:
            fail(
                StepErrorKind.INFRASTRUCTURE,
                "online scenarios (traci_api scripts) need the E2.5 runner",
                scenario_id,
            )
        seeds = step.seeds or DEFAULT_SEEDS
        batch_ids = (result_id_for(scenario_id, s, RunMode.BATCH.value) for s in seeds)
        stored = [r for rid in batch_ids if (r := self.results.get(rid)) is not None]
        results = reused_results(seeds, stored)
        to_run = seeds_to_run(seeds, stored)
        ctx.spend.reserve_simulations(len(to_run))
        attempt = ctx.study.study_id
        for ran, seed in enumerate(to_run, start=1):
            ctx.spend.count_simulation()
            result = self.run_simulation.execute(scenario, seed, attempt)
            if result.status is RunStatus.FAILED:
                fail(
                    StepErrorKind.INFRASTRUCTURE,
                    f"SUMO failed on scenario {scenario_id!r} with seed {seed}",
                    result.error or "",
                    f"logs: {attempt_dir(self.run_simulation.out_dir, result.result_id, attempt)}",
                    usage=Usage(simulations=ran),
                )
            results[seed] = result
        result_ids = tuple(results[s].result_id for s in seeds)
        reused = tuple(results[s].result_id for s in seeds if s not in to_run)
        return ctx.record(step, result_ids, Usage(simulations=len(to_run)), reused)
