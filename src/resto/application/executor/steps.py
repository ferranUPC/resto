"""Executing one phase's plan: every step in order, `FromStep` resolved against the ids the earlier
steps produced, one handler per step kind, stop at the first failure (ADR-0025). Owns the phase's
experiment bookkeeping: which build step each run feeds."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, assert_never, cast

from resto.application.executor.deps import StudyDeps, StudySettings
from resto.application.executor.failures import (
    StepFailed,
    StepNeedsUser,
    crash,
    draft_of,
    fail,
    promote,
)
from resto.application.executor.recorder import StudyRecorder, data
from resto.application.executor.spend import StudySpend
from resto.application.ports.llm import AgentRun
from resto.application.use_cases.run_simulation import attempt_dir
from resto.domain.constants import DEFAULT_SEEDS, NOTE_VERIFY_LIMIT
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.services.experiment_design import study_window
from resto.domain.services.ids import result_id_for, scenario_id_for
from resto.domain.services.reuse import (
    accepts_found_demand,
    accepts_found_network,
    reused_results,
    reused_scenario_results,
    seeds_to_run,
)
from resto.domain.value_objects.drafts import DemandDraft, NetworkDraft
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.outcomes import Found, NeedsUser
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.step_record import StepErrorKind, StepRecord, StepStatus, Usage
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    PlanStep,
    RerouteDemandStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.tasks import (
    NetworkTask,
    ObtainDemandTask,
    ObtainNetworkTask,
    ScenarioTask,
)


def execute_plan(
    plan: StudyPlan,
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
    settings: StudySettings,
) -> str | None:
    """Runs `plan` in the current phase and returns the study's network id; or nothing, once a
    step failed (the study is recorded `failed`) or needed the user (`awaiting_user`), with the
    pending steps skipped."""
    produced: dict[int, str] = {}
    # Keyed by build step, not by scenario id: two build steps can share one (see the spec).
    built: dict[int, int] = {}  # build step index -> index of its Experiment in the phase
    for i, step in enumerate(plan.steps):
        resolved = _resolve(step, produced)
        task = data(resolved)
        pending = plan.steps[i + 1 :]
        try:
            record, experiment = _run_step(resolved, task, recorder, spend, deps, settings)
        except StepFailed as failed:
            recorder.record_failure(resolved.kind, task, failed, pending=pending)
            return None
        except StepNeedsUser as needs:
            recorder.record_needs_user(resolved.kind, task, needs, pending=pending)
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
        produced[plan.network_id.step] if isinstance(plan.network_id, FromStep) else plan.network_id
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


def _or(step_value: int | None, configured: int) -> int:
    """A step's own limit when it sets one, else the configured one."""
    return configured if step_value is None else step_value


def _run_step(
    step: PlanStep,
    task: Mapping[str, Any],
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
    settings: StudySettings,
) -> tuple[StepRecord, Experiment | None]:
    match step:
        case ObtainNetworkStep():
            return _obtain_network(step, task, recorder, spend, deps, settings), None
        case DeriveNetworkStep():
            return _derive_network(step, task, recorder, spend, deps, settings), None
        case ObtainDemandStep():
            return _obtain_demand(step, task, spend, deps, settings, recorder.phase.question), None
        case RerouteDemandStep():
            return _reroute(step, task, deps), None
        case BuildScenarioStep():
            return _build_scenario(step, task, spend, deps)
        case RunSimulationStep():
            return _run_simulations(step, task, recorder, spend, deps), None
        case _:
            assert_never(step)


def _obtain_network(
    step: ObtainNetworkStep,
    task: Mapping[str, Any],
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
    settings: StudySettings,
) -> StepRecord:
    network_task = ObtainNetworkTask(
        network_ref=step.network_ref,
        goals=step.goals,
        min_scc_ratio=step.min_scc_ratio,
        probe_teleport_threshold=step.probe_teleport_threshold,
        max_rounds=_or(step.max_rounds, settings.network_max_rounds),
    )
    run = spend.agent_call(lambda: deps.agents.network_author.obtain(network_task))
    outcome = draft_of(run, "network_author")
    if isinstance(outcome, NeedsUser):
        raise StepNeedsUser(outcome, run.usage)
    if isinstance(outcome, Found):
        if not accepts_found_network(outcome, deps.networks.get(outcome.id)):
            fail(
                StepErrorKind.AGENT,
                f"the Network Author found network {outcome.id!r}, which is not stored",
                usage=run.usage,
            )
        network_id = outcome.id
    else:
        draft_run = cast("AgentRun[NetworkDraft]", run)
        network_id = promote(
            lambda: deps.promotions.network(network_task, draft_run), run.usage
        ).network_id
    recorder.add_networks(network_id)
    return StepRecord(step.kind, StepStatus.OK, task, (network_id,), usage=run.usage)


def _derive_network(
    step: DeriveNetworkStep,
    task: Mapping[str, Any],
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
    settings: StudySettings,
) -> StepRecord:
    network_task = NetworkTask(
        base_network_id=_id(step.base_network_id),
        goals=step.goals,
        modifications=step.modifications,
        min_scc_ratio=step.min_scc_ratio,
        probe_teleport_threshold=step.probe_teleport_threshold,
        max_rounds=_or(step.max_rounds, settings.network_max_rounds),
    )
    run = spend.agent_call(lambda: deps.agents.network_author.author(network_task))
    draft_of(run, "network_author")
    network = promote(lambda: deps.promotions.network(network_task, run), run.usage)
    recorder.add_networks(network.network_id)
    return StepRecord(step.kind, StepStatus.OK, task, (network.network_id,), usage=run.usage)


def _obtain_demand(
    step: ObtainDemandStep,
    task: Mapping[str, Any],
    spend: StudySpend,
    deps: StudyDeps,
    settings: StudySettings,
    question: Question,
) -> StepRecord:
    demand_task = ObtainDemandTask(
        network_id=_id(step.network_id),
        seed=step.seed,
        demand_ref=step.demand_ref,
        window=study_window(question),
        tolerance=step.tolerance,
        max_calibration_rounds=_or(step.max_calibration_rounds, settings.calibration_max_rounds),
    )
    run = spend.agent_call(lambda: deps.agents.demand_generator.obtain(demand_task))
    outcome = draft_of(run, "demand_generator")
    if isinstance(outcome, NeedsUser):
        raise StepNeedsUser(outcome, run.usage)
    if isinstance(outcome, Found):
        stored = deps.demands.get(outcome.id)
        if not accepts_found_demand(outcome, stored, network_id=demand_task.network_id):
            fail(
                StepErrorKind.AGENT,
                f"the Demand Generator found demand {outcome.id!r}, which is not stored "
                f"for network {demand_task.network_id!r}",
                usage=run.usage,
            )
        demand_id = outcome.id
    else:
        draft_run = cast("AgentRun[DemandDraft]", run)
        demand_id = promote(
            lambda: deps.promotions.demand(demand_task, draft_run), run.usage
        ).demand_id
    return StepRecord(step.kind, StepStatus.OK, task, (demand_id,), usage=run.usage)


def _reroute(step: RerouteDemandStep, task: Mapping[str, Any], deps: StudyDeps) -> StepRecord:
    demand = deps.demands.get(_id(step.demand_id))
    network = deps.networks.get(_id(step.network_id))
    if demand is None or network is None:
        fail(StepErrorKind.AGENT, "reroute_demand names a demand or network not stored")
    rerouted = promote(lambda: deps.promotions.reroute(demand, network), Usage())
    return StepRecord(step.kind, StepStatus.OK, task, (rerouted.demand_id,))


def _build_scenario(
    step: BuildScenarioStep,
    task: Mapping[str, Any],
    spend: StudySpend,
    deps: StudyDeps,
) -> tuple[StepRecord, Experiment]:
    scenario_task = ScenarioTask(
        network_id=_id(step.network_id),
        demand_id=_id(step.demand_id),
        interventions=step.interventions,
        context_tags=step.context_tags,
    )
    requested = scenario_id_for(
        scenario_task.network_id,
        scenario_task.demand_id,
        scenario_task.interventions,
        scenario_task.context_tags,
    )
    stored_ids = reused_scenario_results(
        deps.scenarios.get(requested), deps.results.list(requested)
    )
    if stored_ids:
        record = StepRecord(step.kind, StepStatus.OK, task, (requested,))
        return record, Experiment(requested, step.arm, step.role, step.purpose, stored_ids, True)
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
        lambda: deps.build_scenario.execute(scenario_task, run),
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
    stored = _stored_batch_results(deps, scenario.scenario_id, seeds)
    results = reused_results(seeds, stored)
    to_run = seeds_to_run(seeds, stored)
    spend.reserve_simulations(len(to_run))
    attempt = recorder.study.study_id
    for ran, seed in enumerate(to_run, start=1):
        spend.count_simulation()
        result = deps.run_simulation.execute(scenario, seed, attempt)
        if result.status is RunStatus.FAILED:
            fail(
                StepErrorKind.INFRASTRUCTURE,
                f"SUMO failed on scenario {scenario.scenario_id!r} with seed {seed}",
                result.error or "",
                f"logs: {attempt_dir(deps.run_simulation.out_dir, result.result_id, attempt)}",
                usage=Usage(simulations=ran),
            )
        _verify_notes(scenario, result, recorder, deps)
        results[seed] = result
    result_ids = tuple(results[s].result_id for s in seeds)
    return StepRecord(
        step.kind, StepStatus.OK, task, result_ids, usage=Usage(simulations=len(to_run))
    )


def _stored_batch_results(
    deps: StudyDeps, scenario_id: str, seeds: tuple[int, ...]
) -> list[SimulationResult]:
    """The results stored for the batch runs of `scenario_id` with `seeds`, ok or failed."""
    ids = (result_id_for(scenario_id, s, RunMode.BATCH.value) for s in seeds)
    return [r for rid in ids if (r := deps.results.get(rid)) is not None]


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
        status = deps.update_note_status.execute(note, result)
        if status is not None:
            recorder.note_status_changed(note.note_id, result.result_id, status)
