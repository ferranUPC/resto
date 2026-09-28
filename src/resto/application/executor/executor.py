"""The Executor's engine: one `_Executor` per `Study`, driven by `execute_study` (see the
package docstring)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any, cast

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import (
    StepFailed,
    crash,
    describe,
    draft_of,
    fail,
    promote,
)
from resto.application.executor.plan_validation import ok_results
from resto.application.executor.planning import plan_phase
from resto.application.executor.recorder import StudyRecorder, data
from resto.application.executor.spend import StudySpend
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.ask_expert import ask_expert
from resto.application.use_cases.build_scenario import build_scenario
from resto.application.use_cases.run_simulation import run_simulation
from resto.application.use_cases.update_note_status import update_note_status
from resto.application.use_cases.write_note import write_note
from resto.domain.constants import DEFAULT_SEEDS, NOTE_VERIFY_LIMIT
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.entities.study import Study, StudyStatus
from resto.domain.services.experiment_design import mode_for
from resto.domain.services.ids import result_id_for, scenario_id_for
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode, Question
from resto.domain.value_objects.step_record import (
    StepErrorKind,
    StepRecord,
    StepStatus,
    Usage,
)
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
from resto.domain.value_objects.tasks import (
    DemandTask,
    ExpertTask,
    NetworkTask,
    NoteScenario,
    NoteTask,
    ScenarioTask,
)


def execute_study(
    question: Question, parse_usage: Usage, deps: StudyDeps, *, max_rounds: int
) -> Study:
    """Runs a parsed `Question` to a closed `Study` (`completed`, `failed` or `awaiting_user`)
    and returns it. `parse_usage` is what the Input Parser spent: its call is the study's first."""
    return _Executor(deps, question, parse_usage, max_rounds).run()


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


class _Executor:
    def __init__(self, deps: StudyDeps, question: Question, parse_usage: Usage, max_rounds: int):
        self.deps = deps
        self.max_rounds = max_rounds
        self.spend = StudySpend(deps.budget, parse_usage)
        self.network_id: str | None = None
        self.ledger: EvidenceLedger | None = None
        self.recorder = StudyRecorder(
            question,
            parse_usage,
            max_rounds=max_rounds,
            studies=deps.studies,
            tracer=deps.tracer,
        )

    # -- flow ---------------------------------------------------------------------------------

    def run(self) -> Study:
        if self.recorder.study.status is StudyStatus.AWAITING_USER:
            return self.recorder.study
        while True:
            plan = plan_phase(self.recorder, self.spend, self.deps, self.network_id)
            if plan is None or not self._execute(plan):
                return self.recorder.study
            round_ = self._ask_expert()
            if round_ is None:
                return self.recorder.study
            proposed = round_.answer.proposed_experiment
            if not round_.answer.needs_simulation or proposed is None:
                break
            self.recorder.open_phase(proposed)
        self._write_notes()
        self._compose()
        return self.recorder.study

    # -- execution ----------------------------------------------------------------------------

    def _execute(self, plan: StudyPlan) -> bool:
        reused = tuple(
            Experiment(
                r.scenario_id,
                r.arm,
                r.role,
                r.purpose,
                ok_results(self.deps.results, r.scenario_id),
                True,
            )
            for r in plan.reused
        )
        if reused:
            self.recorder.replace_phase(replace(self.recorder.phase, experiments=reused))
        produced: dict[int, str] = {}
        built: dict[int, int] = {}  # build step index -> index of its Experiment in the phase
        for i, step in enumerate(plan.steps):
            resolved = _resolve(step, produced)
            task = data(resolved)
            pending = plan.steps[i + 1 :]
            try:
                record, experiment = self._run_step(resolved, task)
            except StepFailed as failed:
                self.recorder.record_failure(resolved.kind, task, failed, pending=pending)
                return False
            except Exception as e:
                self.recorder.record_failure(resolved.kind, task, crash(e), pending=pending)
                return False
            produced[i] = record.produced_ids[-1] if record.produced_ids else ""
            experiments = self.recorder.phase.experiments
            if experiment is not None:
                built[i] = len(experiments)
                experiments = (*experiments, experiment)
            elif isinstance(step, RunSimulationStep) and isinstance(step.scenario_id, FromStep):
                j = built[step.scenario_id.step]
                target = experiments[j]
                ids = (*target.result_ids, *record.produced_ids)
                target = replace(target, result_ids=tuple(dict.fromkeys(ids)))
                experiments = (*experiments[:j], target, *experiments[j + 1 :])
            self.recorder.record(record, experiments=experiments)
        self.network_id = produced[plan.network_id.step] if isinstance(
            plan.network_id, FromStep
        ) else plan.network_id
        self.recorder.add_networks(self.network_id)
        return True

    def _run_step(
        self, step: PlanStep, task: Mapping[str, Any]
    ) -> tuple[StepRecord, Experiment | None]:
        match step:
            case GenerateNetworkStep():
                network_task = NetworkTask(
                    source=step.source,
                    goals=step.goals,
                    modifications=step.modifications,
                    min_scc_ratio=step.min_scc_ratio,
                    probe_teleport_threshold=step.probe_teleport_threshold,
                    max_rounds=step.max_rounds,
                )
                return self._author_network(network_task, task), None
            case DeriveNetworkStep():
                network_task = NetworkTask(
                    base_network_id=_id(step.base_network_id),
                    goals=step.goals,
                    modifications=step.modifications,
                    min_scc_ratio=step.min_scc_ratio,
                    probe_teleport_threshold=step.probe_teleport_threshold,
                    max_rounds=step.max_rounds,
                )
                return self._author_network(network_task, task), None
            case GenerateDemandStep():
                return self._generate_demand(step, task), None
            case RerouteDemandStep():
                return self._reroute(step, task), None
            case BuildScenarioStep():
                return self._build_scenario(step, task)
            case RunSimulationStep():
                return self._run_simulations(step, task), None
        raise TypeError(f"unknown plan step {step!r}")  # pragma: no cover

    def _author_network(self, network_task: NetworkTask, task: Mapping[str, Any]) -> StepRecord:
        run = self.spend.agent_call(lambda: self.deps.agents.network_author.author(network_task))
        draft_of(run, "network_author")
        network = promote(lambda: self.deps.promotions.network(network_task, run), run.usage)
        self.recorder.add_networks(network.network_id)
        tool = "derive_network" if network_task.base_network_id else "generate_network"
        return StepRecord(tool, StepStatus.OK, task, (network.network_id,), usage=run.usage)

    def _generate_demand(self, step: GenerateDemandStep, task: Mapping[str, Any]) -> StepRecord:
        demand_task = DemandTask(
            network_id=_id(step.network_id),
            profile=step.profile,
            seed=step.seed,
            sources=step.sources,
            control_edges=step.control_edges,
            tolerance=step.tolerance,
            max_calibration_rounds=step.max_calibration_rounds,
        )
        run = self.spend.agent_call(lambda: self.deps.agents.demand_generator.generate(demand_task))
        draft_of(run, "demand_generator")
        demand = promote(lambda: self.deps.promotions.demand(demand_task, run), run.usage)
        return StepRecord(step.kind, StepStatus.OK, task, (demand.demand_id,), usage=run.usage)

    def _reroute(self, step: RerouteDemandStep, task: Mapping[str, Any]) -> StepRecord:
        demand = self.deps.demands.get(_id(step.demand_id))
        network = self.deps.networks.get(_id(step.network_id))
        if demand is None or network is None:
            fail(StepErrorKind.AGENT, "reroute_demand names a demand or network not stored")
        rerouted = promote(lambda: self.deps.promotions.reroute(demand, network), Usage())
        return StepRecord(step.kind, StepStatus.OK, task, (rerouted.demand_id,))

    def _build_scenario(
        self, step: BuildScenarioStep, task: Mapping[str, Any]
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
        if self.deps.scenarios.get(requested) is not None:
            scenario_id = requested
        else:
            builder = self.deps.agents.scenario_builder
            run = self.spend.agent_call(lambda: builder.build(scenario_task))
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
                    networks=self.deps.networks,
                    demands=self.deps.demands,
                    scenarios=self.deps.scenarios,
                    network_query_factory=self.deps.network_query_factory,
                    runner=self.deps.runner,
                    out_dir=self.deps.out_dir / "scenarios",
                ),
                usage,
            )
            scenario_id = scenario.scenario_id
        record = StepRecord(step.kind, StepStatus.OK, task, (scenario_id,), usage=usage)
        return record, Experiment(scenario_id, step.arm, step.role, step.purpose)

    def _run_simulations(self, step: RunSimulationStep, task: Mapping[str, Any]) -> StepRecord:
        scenario = self.deps.scenarios.get(_id(step.scenario_id))
        if scenario is None:
            fail(StepErrorKind.AGENT, f"scenario {step.scenario_id!r} is not stored")
        if scenario.is_online:
            fail(
                StepErrorKind.INFRASTRUCTURE,
                "online scenarios (traci_api scripts) need the E2.5 runner",
                scenario.scenario_id,
            )
        seeds = step.seeds or DEFAULT_SEEDS
        existing = {s: self._existing_ok(scenario.scenario_id, s) for s in seeds}
        new_seeds = [s for s, result in existing.items() if result is None]
        self.spend.reserve_simulations(len(new_seeds))
        result_ids: list[str] = []
        ran = 0
        for seed in seeds:
            result = existing[seed]
            if result is None:
                ran += 1
                self.spend.count_simulation()
                result = run_simulation(
                    scenario,
                    seed,
                    runner=self.deps.runner,
                    results=self.deps.results,
                    out_dir=self.deps.out_dir / "results",
                )
                if result.status is RunStatus.FAILED:
                    fail(
                        StepErrorKind.INFRASTRUCTURE,
                        f"SUMO failed on scenario {scenario.scenario_id!r} with seed {seed}",
                        result.error or "",
                        f"logs: {self.deps.out_dir / 'results' / result.result_id}",
                        usage=Usage(simulations=ran),
                    )
                self._verify_notes(scenario, result)
            result_ids.append(result.result_id)
        return StepRecord(
            step.kind, StepStatus.OK, task, tuple(result_ids), usage=Usage(simulations=ran)
        )

    def _existing_ok(self, scenario_id: str, seed: int) -> SimulationResult | None:
        result = self.deps.results.get(result_id_for(scenario_id, seed, RunMode.BATCH.value))
        return result if result is not None and result.status is RunStatus.OK else None

    def _verify_notes(self, scenario: Scenario, result: SimulationResult) -> None:
        """ADR-0026: a new ok result settles the unverified notes about its scenario."""
        hits = self.deps.notes.search(
            "",
            scenario.network_id,
            {"scenario_id": scenario.scenario_id, "status": [NoteStatus.UNVERIFIED.value]},
            limit=NOTE_VERIFY_LIMIT,
        )
        for note, _ in hits:
            status = update_note_status(note, result, notes=self.deps.notes)
            if status is not None:
                self.recorder.trace(
                    "note_status",
                    {"note_id": note.note_id, "result_id": result.result_id, "status": status},
                )

    # -- the Expert ---------------------------------------------------------------------------

    def _ask_expert(self) -> ExpertRound | None:
        round_no = self.recorder.phase_index + 1
        assert self.network_id is not None
        # TODO(E5.3): one network per ExpertTask. Arms on a derived network have their results in
        # `result_ids` (readable), but the Expert's topology tools and `ask_expert`'s edge check
        # see only the study's network (docs/tfm-work-plan.md, E5.3).
        task = ExpertTask(
            question=self.recorder.study.question.text,
            mode=mode_for(self.recorder.study.question, round_no, self.max_rounds),
            network_id=self.network_id,
            result_ids=self.recorder.result_ids(),
        )
        ledger = EvidenceLedger()
        try:
            run = self.spend.agent_call(lambda: self.deps.agents.expert.answer(task, ledger))
            draft_of(run, "expert")
            network = self.deps.networks.get(task.network_id)
            if network is None:
                fail(StepErrorKind.INFRASTRUCTURE, f"network {task.network_id!r} disappeared")
            query = self.deps.network_query_factory(network.net_xml.path)
            round_ = promote(lambda: ask_expert(task, run, ledger, query=query), run.usage)
        except StepFailed as failed:
            self.recorder.record_failure("ask_expert", data(task), failed)
            return None
        except Exception as e:
            self.recorder.record_failure("ask_expert", data(task), crash(e))
            return None
        question = self.recorder.study.question
        forced_by_limit = question.mode is Mode.FREE and round_no == self.max_rounds
        round_ = replace(round_, forced_by_limit=forced_by_limit)
        self.ledger = ledger
        record = StepRecord("ask_expert", StepStatus.OK, data(task), usage=run.usage)
        self.recorder.record(record, round_=round_)
        return round_

    # -- closing ------------------------------------------------------------------------------

    def _write_notes(self) -> None:
        final = self.recorder.phase.round
        assert final is not None and self.ledger is not None and self.network_id is not None
        ledger, network_id = self.ledger, self.network_id
        try:
            task = NoteTask(round=final, scenarios=self._allow_list())
            run = self.spend.agent_call(lambda: self.deps.agents.note_writer.write(task))
            written = write_note(
                run,
                ledger,
                task,
                network_id=network_id,
                study_id=self.recorder.study.study_id,
                notes=self.deps.notes,
            )
        except Exception as e:
            self.recorder.trace("note_writer_failed", {"error": describe(e)})
            return
        self.recorder.set_note_ids(tuple(n.note_id for n in written))

    def _allow_list(self) -> tuple[NoteScenario, ...]:
        """Every scenario of the study, plus the predicted id of each arm of the original question
        that was not realised and keeps the topology (ADR-0026)."""
        entries: dict[str, NoteScenario] = {}
        experiments = [e for p in self.recorder.study.phases for e in p.experiments]
        for e in experiments:
            entries.setdefault(
                e.scenario_id,
                NoteScenario(e.scenario_id, e.arm, e.role, e.purpose, bool(e.result_ids)),
            )
        base = next((e for e in experiments if e.arm == BASE_ARM), None)
        base_scenario = self.deps.scenarios.get(base.scenario_id) if base is not None else None
        if base_scenario is None:
            return tuple(entries.values())
        realised = {e.arm for e in experiments}
        question = self.recorder.study.question
        for arm in question.effective_arms:
            if arm.label in realised or arm.topology_changes:
                continue
            predicted = scenario_id_for(
                base_scenario.network_id,
                base_scenario.demand_id,
                arm.interventions,
                question.context_tags,
            )
            entries.setdefault(
                predicted,
                NoteScenario(
                    predicted,
                    arm.label,
                    ExperimentRole.TREATMENT,
                    f"arm {arm.label!r} as asked, not simulated in this study",
                    simulated=False,
                ),
            )
        return tuple(entries.values())

    def _compose(self) -> None:
        study = self.recorder.study
        task = {"study_id": study.study_id}
        try:
            run = self.spend.agent_call(lambda: self.deps.agents.composer.compose(study))
            draft_of(run, "composer")
            report = promote(lambda: self.deps.promotions.report(study, run), run.usage)
        except StepFailed as failed:
            self.recorder.record_failure("compose_report", task, failed)
            return
        except Exception as e:
            self.recorder.record_failure("compose_report", task, crash(e))
            return
        record = StepRecord("compose_report", StepStatus.OK, task, usage=run.usage)
        self.recorder.record(record, status=StudyStatus.COMPLETED, report=report)
