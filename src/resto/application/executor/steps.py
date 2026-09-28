"""Executing one phase's plan: every step in order, `FromStep` resolved against the ids the earlier
steps produced, one handler per step kind, stop at the first failure (ADR-0025). Owns the phase's
experiment bookkeeping: which build step each run feeds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, assert_never, cast

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, draft_of, fail, promote
from resto.application.executor.plan_validation import ok_results
from resto.application.executor.recorder import StudyRecorder, data
from resto.application.executor.spend import StudySpend
from resto.application.use_cases.build_scenario import build_scenario
from resto.application.use_cases.run_simulation import run_simulation
from resto.application.use_cases.update_note_status import update_note_status
from resto.domain.constants import DEFAULT_SEEDS, NOTE_VERIFY_LIMIT
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.services.ids import result_id_for, scenario_id_for
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.step_record import StepErrorKind, StepRecord, StepStatus, Usage
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    GenerateDemandStep,
    GenerateNetworkStep,
    PlanStep,
    RerouteDemandStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.tasks import DemandTask, NetworkTask, ScenarioTask


def execute_plan(
    plan: StudyPlan, recorder: StudyRecorder, spend: StudySpend, deps: StudyDeps
) -> str | None:
    """Runs `plan` in the current phase and returns the study's network id; or nothing, once a
    step failed and the study was recorded as `failed` with the pending steps skipped."""
    reused = tuple(
        Experiment(
            r.scenario_id,
            r.arm,
            r.role,
            r.purpose,
            ok_results(deps.results, r.scenario_id),
            True,
        )
        for r in plan.reused
    )
    if reused:
        recorder.replace_phase(replace(recorder.phase, experiments=reused))
    produced: dict[int, str] = {}
    # Keyed by build step, not by scenario id: two build steps can share one (see the spec).
    built: dict[int, int] = {}  # build step index -> index of its Experiment in the phase
    for i, step in enumerate(plan.steps):
        resolved = _resolve(step, produced)
        task = data(resolved)
        pending = plan.steps[i + 1 :]
        try:
            record, experiment = _run_step(resolved, task, recorder, spend, deps)
        except StepFailed as failed:
            recorder.record_failure(resolved.kind, task, failed, pending=pending)
            return None
        except Exception as e:
            recorder.record_failure(resolved.kind, task, crash(e), pending=pending)
            return None
        produced[i] = record.produced_ids[-1] if record.produced_ids else ""
        experiments = recorder.phase.experiments
        if experiment is not None:
            built[i] = len(experiments)
            experiments = (*experiments, experiment)
        elif isinstance(step, RunSimulationStep) and isinstance(step.scenario_id, FromStep):
            j = built[step.scenario_id.step]
            target = experiments[j]
            ids = (*target.result_ids, *record.produced_ids)
            target = replace(target, result_ids=tuple(dict.fromkeys(ids)))
            experiments = (*experiments[:j], target, *experiments[j + 1 :])
        recorder.record(record, experiments=experiments)
    network_id = (
        produced[plan.network_id.step]
        if isinstance(plan.network_id, FromStep)
        else plan.network_id
    )
    recorder.add_networks(network_id)
    return network_id


_ID_FIELDS = ("base_network_id", "network_id", "demand_id", "scenario_id")


def _resolve(step: PlanStep, produced: Mapping[int, str]) -> PlanStep:
    """`step` with every `FromStep` replaced by the id that step produced."""
    changes = {
        name: produced[ref.step]
        for name in _ID_FIELDS
        if isinstance(ref := getattr(step, name, None), FromStep)
    }
    resolved: PlanStep = replace(cast(Any, step), **changes)
    return resolved


def _id(ref: str | FromStep) -> str:
    if isinstance(ref, FromStep):  # _resolve ran first: a FromStep here is a bug
        raise TypeError(f"unresolved {ref}")
    return ref


def _run_step(
    step: PlanStep,
    task: Mapping[str, Any],
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> tuple[StepRecord, Experiment | None]:
    match step:
        case GenerateNetworkStep() | DeriveNetworkStep():
            return _author_network(step, task, recorder, spend, deps), None
        case GenerateDemandStep():
            return _generate_demand(step, task, spend, deps), None
        case RerouteDemandStep():
            return _reroute(step, task, deps), None
        case BuildScenarioStep():
            return _build_scenario(step, task, spend, deps)
        case RunSimulationStep():
            return _run_simulations(step, task, recorder, spend, deps), None
        case _:
            assert_never(step)


def _network_task(step: GenerateNetworkStep | DeriveNetworkStep) -> NetworkTask:
    """The Network Author's task: from a source for a generate step, from a base for a derive."""
    source: NetworkSource | None = None
    base_network_id: str | None = None
    if isinstance(step, GenerateNetworkStep):
        source = step.source
    else:
        base_network_id = _id(step.base_network_id)
    return NetworkTask(
        source=source,
        base_network_id=base_network_id,
        goals=step.goals,
        modifications=step.modifications,
        min_scc_ratio=step.min_scc_ratio,
        probe_teleport_threshold=step.probe_teleport_threshold,
        max_rounds=step.max_rounds,
    )


def _author_network(
    step: GenerateNetworkStep | DeriveNetworkStep,
    task: Mapping[str, Any],
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> StepRecord:
    network_task = _network_task(step)
    run = spend.agent_call(lambda: deps.agents.network_author.author(network_task))
    draft_of(run, "network_author")
    network = promote(lambda: deps.promotions.network(network_task, run), run.usage)
    recorder.add_networks(network.network_id)
    tool = "derive_network" if network_task.base_network_id else "generate_network"
    return StepRecord(tool, StepStatus.OK, task, (network.network_id,), usage=run.usage)


def _generate_demand(
    step: GenerateDemandStep, task: Mapping[str, Any], spend: StudySpend, deps: StudyDeps
) -> StepRecord:
    demand_task = DemandTask(
        network_id=_id(step.network_id),
        profile=step.profile,
        seed=step.seed,
        sources=step.sources,
        control_edges=step.control_edges,
        tolerance=step.tolerance,
        max_calibration_rounds=step.max_calibration_rounds,
    )
    run = spend.agent_call(lambda: deps.agents.demand_generator.generate(demand_task))
    draft_of(run, "demand_generator")
    demand = promote(lambda: deps.promotions.demand(demand_task, run), run.usage)
    return StepRecord(step.kind, StepStatus.OK, task, (demand.demand_id,), usage=run.usage)


def _reroute(step: RerouteDemandStep, task: Mapping[str, Any], deps: StudyDeps) -> StepRecord:
    demand = deps.demands.get(_id(step.demand_id))
    network = deps.networks.get(_id(step.network_id))
    if demand is None or network is None:
        fail(StepErrorKind.AGENT, "reroute_demand names a demand or network not stored")
    rerouted = promote(lambda: deps.promotions.reroute(demand, network), Usage())
    return StepRecord(step.kind, StepStatus.OK, task, (rerouted.demand_id,))


def _build_scenario(
    step: BuildScenarioStep, task: Mapping[str, Any], spend: StudySpend, deps: StudyDeps
) -> tuple[StepRecord, Experiment]:
    scenario_task = ScenarioTask(
        network_id=_id(step.network_id),
        demand_id=_id(step.demand_id),
        interventions=step.interventions,
        context_tags=step.context_tags,
        allow_script=step.allow_script,
    )
    requested = scenario_id_for(
        scenario_task.network_id,
        scenario_task.demand_id,
        scenario_task.interventions,
        scenario_task.context_tags,
    )
    usage = Usage()
    if deps.scenarios.get(requested) is not None:
        scenario_id = requested
    else:
        builder = deps.agents.scenario_builder
        run = spend.agent_call(lambda: builder.build(scenario_task))
        draft = draft_of(run, "scenario_builder")
        usage = run.usage
        if draft.rejected:
            fail(
                StepErrorKind.USER_INPUT,
                f"the Scenario Builder rejected {len(draft.rejected)} intervention(s)",
                *(f"{r.intervention.type}: {r.reason}" for r in draft.rejected),
                usage=usage,
            )
        scenario = promote(
            lambda: build_scenario(
                scenario_task,
                run,
                networks=deps.networks,
                demands=deps.demands,
                scenarios=deps.scenarios,
                network_query_factory=deps.network_query_factory,
                runner=deps.runner,
                out_dir=deps.out_dir / "scenarios",
            ),
            usage,
        )
        scenario_id = scenario.scenario_id
    record = StepRecord(step.kind, StepStatus.OK, task, (scenario_id,), usage=usage)
    return record, Experiment(scenario_id, step.arm, step.role, step.purpose)


def _run_simulations(
    step: RunSimulationStep,
    task: Mapping[str, Any],
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> StepRecord:
    scenario = deps.scenarios.get(_id(step.scenario_id))
    if scenario is None:
        fail(StepErrorKind.AGENT, f"scenario {step.scenario_id!r} is not stored")
    if scenario.is_online:
        fail(
            StepErrorKind.INFRASTRUCTURE,
            "online scenarios (traci_api scripts) need the E2.5 runner",
            scenario.scenario_id,
        )
    seeds = step.seeds or DEFAULT_SEEDS
    existing = {s: _existing_ok(deps, scenario.scenario_id, s) for s in seeds}
    new_seeds = [s for s, result in existing.items() if result is None]
    spend.reserve_simulations(len(new_seeds))
    result_ids: list[str] = []
    ran = 0
    for seed in seeds:
        result = existing[seed]
        if result is None:
            ran += 1
            spend.count_simulation()
            result = run_simulation(
                scenario,
                seed,
                runner=deps.runner,
                results=deps.results,
                out_dir=deps.out_dir / "results",
            )
            if result.status is RunStatus.FAILED:
                fail(
                    StepErrorKind.INFRASTRUCTURE,
                    f"SUMO failed on scenario {scenario.scenario_id!r} with seed {seed}",
                    result.error or "",
                    f"logs: {deps.out_dir / 'results' / result.result_id}",
                    usage=Usage(simulations=ran),
                )
            _verify_notes(scenario, result, recorder, deps)
        result_ids.append(result.result_id)
    return StepRecord(
        step.kind, StepStatus.OK, task, tuple(result_ids), usage=Usage(simulations=ran)
    )


def _existing_ok(deps: StudyDeps, scenario_id: str, seed: int) -> SimulationResult | None:
    result = deps.results.get(result_id_for(scenario_id, seed, RunMode.BATCH.value))
    return result if result is not None and result.status is RunStatus.OK else None


def _verify_notes(
    scenario: Scenario, result: SimulationResult, recorder: StudyRecorder, deps: StudyDeps
) -> None:
    """ADR-0026: a new ok result settles the unverified notes about its scenario."""
    hits = deps.notes.search(
        "",
        scenario.network_id,
        {"scenario_id": scenario.scenario_id, "status": [NoteStatus.UNVERIFIED.value]},
        limit=NOTE_VERIFY_LIMIT,
    )
    for note, _ in hits:
        status = update_note_status(note, result, notes=deps.notes)
        if status is not None:
            recorder.trace(
                "note_status",
                {"note_id": note.note_id, "result_id": result.result_id, "status": status},
            )
