"""Executor (ADR-0023, ADR-0025, ADR-0026, ADR-0027): user text -> a closed `Study`, by
deterministic code. It decides nothing about the domain: agents decide, promotion use cases
certify, this module chains them (docs/study-flows.md §2-§3).

    parse -> Study (phase 0) -> [plan -> validate -> execute steps -> ask the Expert]* -> notes
    -> report

- **Agents** are reached through their ports (`application/ports/agents/`), promotions the Executor
  cannot call directly yet (network, demand, reroute, report) through `StudyPromotions`; both are
  bound in the composition root (`interface/cli`).
- **Persistence.** The `Study` is stored after every step. Each state is a new `Study` built with
  `dataclasses.replace`, so the domain invariants check every intermediate state.
- **Failures.** The first failure becomes a failed `StepRecord` with a `StepError` (ADR-0025 §3),
  the pending plan steps are recorded as skipped and the study is `failed` - all in one state. No
  re-ask: the only retry is inside `ToolAgent`.
- **Guards in code.** No re-run of an existing ok `result_id` (checked before the Runner), no
  Builder call for a scenario already stored under the requested id, a per-`Study` budget
  (`StudyBudget`) checked before every agent call and simulation, `max_rounds` with the last round
  forced (ADR-0025 §4).
- **Notes** (ADR-0026) are written once, after the final round; a failing note writer is traced and
  never fails the study. Unverified notes are checked against every *new* ok result only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, TypeVar, cast

from resto.application.ports.agents.composer import ComposerAgent
from resto.application.ports.agents.coordinator import CoordinatorAgent, PlanningContext
from resto.application.ports.agents.demand_generator import DemandGeneratorAgent
from resto.application.ports.agents.expert import ExpertAgent
from resto.application.ports.agents.input_parser import InputParserAgent
from resto.application.ports.agents.network_author import NetworkAuthorAgent
from resto.application.ports.agents.note_writer import NoteWriterAgent
from resto.application.ports.agents.scenario_builder import ScenarioBuilderAgent
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
    StudyRepository,
)
from resto.application.ports.sumo import SumoRunner
from resto.application.ports.tracing import Tracer
from resto.application.schemas import adapter_for
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.ask_expert import ask_expert
from resto.application.use_cases.build_scenario import (
    NetworkQueryFactory,
    UnknownTargetError,
    build_scenario,
)
from resto.application.use_cases.run_simulation import run_simulation
from resto.application.use_cases.update_note_status import update_note_status
from resto.application.use_cases.write_note import write_note
from resto.domain.constants import (
    DEFAULT_MAX_ROUNDS,
    DEFAULT_SEEDS,
    DEFAULT_STUDY_MAX_AGENT_CALLS,
    DEFAULT_STUDY_MAX_SIMULATIONS,
    DEFAULT_STUDY_MAX_TOKENS,
    NOTE_VERIFY_LIMIT,
)
from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.entities.study import Phase, Study, StudyStatus
from resto.domain.services.experiment_design import reference_arms, required_arms
from resto.domain.services.ids import new_id, result_id_for, scenario_id_for
from resto.domain.value_objects.arm import BASE_ARM, Arm
from resto.domain.value_objects.demand_source import HistoricalDbSource
from resto.domain.value_objects.drafts import DemandDraft, NetworkDraft
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import (
    StepError,
    StepErrorKind,
    StepRecord,
    StepStatus,
    Usage,
)
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    ClarificationRequest,
    DeriveNetworkStep,
    FromStep,
    GenerateDemandStep,
    GenerateNetworkStep,
    PlanStep,
    Produces,
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
from resto.domain.value_objects.topology_modification import TopologyModification

T = TypeVar("T")


class ParserFailed(RuntimeError):
    """The Input Parser produced no valid `Question`: no `Study` exists (ADR-0025 §3), the CLI
    reports the error."""


@dataclass(frozen=True, slots=True)
class StudyBudget:
    """What one `Study` may spend in total, on top of each agent call's own `Budget`
    (ADR-0023 §5). Exhausting it fails the step about to run with `StepError(budget)`."""

    max_tokens: int = DEFAULT_STUDY_MAX_TOKENS
    max_simulations: int = DEFAULT_STUDY_MAX_SIMULATIONS
    max_agent_calls: int = DEFAULT_STUDY_MAX_AGENT_CALLS


@dataclass(frozen=True, slots=True)
class StudyAgents:
    parser: InputParserAgent
    coordinator: CoordinatorAgent
    network_author: NetworkAuthorAgent
    demand_generator: DemandGeneratorAgent
    scenario_builder: ScenarioBuilderAgent
    expert: ExpertAgent
    note_writer: NoteWriterAgent
    composer: ComposerAgent


@dataclass(frozen=True, slots=True)
class StudyPromotions:
    """The promotions not implemented yet (E5.4, E6.1, E6.2), injected so the Executor does not
    change when they land. A `ValueError` means the draft was rejected (`StepError(agent)`); any
    other exception is `infrastructure`. `network` promotes both a created and a derived network
    (the task says which)."""

    network: Callable[[NetworkTask, AgentRun[NetworkDraft]], Network]
    demand: Callable[[DemandTask, AgentRun[DemandDraft]], Demand]
    reroute: Callable[[Demand, Network], Demand]
    report: Callable[[Study, AgentRun[Report]], Report]


@dataclass(frozen=True, slots=True)
class StudyDeps:
    agents: StudyAgents
    promotions: StudyPromotions
    networks: NetworkRepository
    demands: DemandRepository
    scenarios: ScenarioRepository
    results: ResultRepository
    notes: NoteRepository
    studies: StudyRepository
    runner: SumoRunner
    network_query_factory: NetworkQueryFactory
    tracer: Tracer
    out_dir: Path
    has_historical_demand: bool = False
    budget: StudyBudget = field(default_factory=StudyBudget)


def run_study(
    text: str,
    deps: StudyDeps,
    *,
    mode: Mode | None = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> Study:
    """Runs the user's request to a closed `Study` (`completed`, `failed` or `awaiting_user`) and
    returns it; every intermediate state is in `deps.studies`. `mode`, when given, is the user's
    choice and overrides the parser's.

    Raises:
        ParserFailed: no valid `Question`, so no `Study` was created.
    """
    try:
        run = deps.agents.parser.parse(text)
    except Exception as e:
        raise ParserFailed(f"the Input Parser failed: {type(e).__name__}: {e}") from e
    if run.stop_reason is not StopReason.OUTPUT or run.output is None:
        raise ParserFailed(f"the Input Parser stopped on {run.stop_reason} without a Question")
    question = run.output if mode is None else replace(run.output, mode=mode)
    return _Executor(deps, question, run.usage, max_rounds).run()


def mode_for(question: Question, round_no: int, max_rounds: int) -> Mode:
    """Forced when the user asked for it, and always on round `max_rounds` (ADR-0025 §4)."""
    if question.mode is Mode.FORCED or round_no == max_rounds:
        return Mode.FORCED
    return Mode.FREE


def needed_arms(question: Question, phase: int) -> tuple[str, ...]:
    """The arms a phase must have realised (ADR-0025 §2 per arm, ADR-0027 §2); phases >= 1 are
    planned as `run`."""
    if phase >= 1 or question.intent in (Intent.RUN, Intent.COMPARE):
        return required_arms(question)
    if question.intent is Intent.COUNTERFACTUAL:
        return reference_arms(question)
    return (BASE_ARM,)


class _StepFailed(Exception):
    """Internal: the step being run failed; carries its classification and what it spent."""

    def __init__(self, error: StepError, usage: Usage | None = None) -> None:
        super().__init__(error.message)
        self.error = error
        self.usage = usage or Usage()


def _fail(kind: StepErrorKind, message: str, *details: str, usage: Usage | None = None) -> None:
    raise _StepFailed(StepError(kind, message, tuple(details)), usage)


def _data(value: Any) -> Mapping[str, Any]:
    dumped: Mapping[str, Any] = adapter_for(type(value)).dump_python(value, mode="json")
    return dumped


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


def _str_refs(step: PlanStep) -> tuple[tuple[Produces, str], ...]:
    """The ids a step names directly (not through `FromStep`), by kind."""
    refs: tuple[tuple[Produces, str | FromStep], ...]
    match step:
        case DeriveNetworkStep():
            refs = (("network", step.base_network_id),)
        case GenerateDemandStep():
            refs = (("network", step.network_id),)
        case RerouteDemandStep():
            refs = (("demand", step.demand_id), ("network", step.network_id))
        case BuildScenarioStep():
            refs = (("network", step.network_id), ("demand", step.demand_id))
        case RunSimulationStep():
            refs = (("scenario", step.scenario_id),)
        case _:
            refs = ()
    return tuple((kind, ref) for kind, ref in refs if isinstance(ref, str))


class _Executor:
    def __init__(self, deps: StudyDeps, question: Question, parse_usage: Usage, max_rounds: int):
        self.deps = deps
        self.max_rounds = max_rounds
        self.tokens = parse_usage.input_tokens + parse_usage.output_tokens
        self.agent_calls = 1
        self.simulations = 0
        self.network_id: str | None = None
        self.ledger: EvidenceLedger | None = None
        status = StudyStatus.AWAITING_USER if question.is_ambiguous else StudyStatus.PLANNING
        self.study = Study(new_id(), status, (Phase(question),), max_rounds=max_rounds)
        self._store()
        self._trace("study_created", {"question": _data(question), "parse_usage": parse_usage})

    # -- flow ---------------------------------------------------------------------------------

    def run(self) -> Study:
        if self.study.status is StudyStatus.AWAITING_USER:
            return self.study
        while True:
            plan = self._plan()
            if plan is None or not self._execute(plan):
                return self.study
            round_ = self._ask_expert()
            if round_ is None:
                return self.study
            proposed = round_.answer.proposed_experiment
            if not round_.answer.needs_simulation or proposed is None:
                break
            self._set(phases=(*self.study.phases, Phase(proposed)))
        self._write_notes()
        self._compose()
        return self.study

    # -- planning -----------------------------------------------------------------------------

    def _plan(self) -> StudyPlan | None:
        k = self._k
        phase = self._phase
        context = PlanningContext(
            phase=k,
            network_id=self.network_id,
            experiments=tuple(e for p in self.study.phases[:-1] for e in p.experiments),
            has_historical_demand=self.deps.has_historical_demand,
        )
        task = {"phase": k, "question": _data(phase.question)}
        try:
            coordinator = self.deps.agents.coordinator
            run = self._agent_call(lambda: coordinator.plan(phase.question, context))
            output = self._output(run, "coordinator")
        except _StepFailed as failed:
            self._record_failure("plan", task, failed)
            return None
        if isinstance(output, ClarificationRequest):
            if k == 0:
                self._trace("clarification", {"reason": output.reason})
                self._set_phase(
                    replace(phase, clarification=output), status=StudyStatus.AWAITING_USER
                )
                return None
            failure = _StepFailed(
                StepError(
                    StepErrorKind.AGENT,
                    f"the Coordinator could not plan the experiment proposed in round {k}",
                    (output.reason, *output.candidates),
                ),
                run.usage,
            )
            self._record_failure("plan", task, failure)
            return None
        try:
            self._validate(output, phase.question)
        except _StepFailed as failed:
            failed.usage = run.usage
            self._record_failure(
                "plan", task, failed, phase=replace(phase, plan=output), pending=output.steps
            )
            return None
        self._set_phase(
            replace(
                phase,
                plan=output,
                steps=(StepRecord("plan", StepStatus.OK, task, usage=run.usage),),
            ),
            status=StudyStatus.RUNNING,
        )
        return output

    def _validate(self, plan: StudyPlan, question: Question) -> None:
        """Semantics of the plan against stored state and the question (study-flows.md §5); the
        syntax already held when the plan was built. Every problem found goes in the details."""
        problems: list[str] = []
        if isinstance(plan.network_id, str) and self.deps.networks.get(plan.network_id) is None:
            problems.append(f"unknown network {plan.network_id!r}")
        if self.network_id is not None and plan.network_id != self.network_id:
            problems.append(
                f"phase {self._k} plans on network {plan.network_id!r}, "
                f"the study is about {self.network_id!r}"
            )
        lookup: dict[Produces, Callable[[str], object]] = {
            "network": self.deps.networks.get,
            "demand": self.deps.demands.get,
            "scenario": self.deps.scenarios.get,
        }
        run_targets: set[int] = set()
        for i, step in enumerate(plan.steps):
            for kind, ref in _str_refs(step):
                if kind != "scenario" and lookup[kind](ref) is None:
                    problems.append(f"step {i}: unknown {kind} {ref!r}")
            if (
                isinstance(step, GenerateDemandStep)
                and not self.deps.has_historical_demand
                and any(isinstance(s, HistoricalDbSource) for s in step.sources)
            ):
                problems.append(
                    f"step {i}: historical demand requested, but the database lacks the "
                    "historical_demand capability"
                )
            if isinstance(step, RunSimulationStep):
                if isinstance(step.scenario_id, FromStep):
                    run_targets.add(step.scenario_id.step)
                else:
                    problems.append(
                        f"step {i}: run_simulation must run a scenario built by this plan "
                        "(plan a build_scenario step: an existing scenario costs no agent call)"
                    )
        arms = {a.label: a for a in question.effective_arms}
        for i, step in enumerate(plan.steps):
            if isinstance(step, BuildScenarioStep):
                if i not in run_targets:
                    problems.append(f"step {i}: arm {step.arm!r} is built but never run")
                problems += self._arm_problems(
                    f"step {i}",
                    arms.get(step.arm),
                    step.interventions,
                    on_study_network=step.network_id == plan.network_id,
                    derived_by=self._derivation(plan, step.network_id),
                )
        for reused in plan.reused:
            problems += self._reused_problems(plan, reused.scenario_id, arms.get(reused.arm))
        problems += self._coverage_problems(plan, question)
        if problems:
            _fail(StepErrorKind.AGENT, f"the plan of phase {self._k} is invalid", *problems)

    def _derivation(
        self, plan: StudyPlan, network_ref: str | FromStep
    ) -> tuple[TopologyModification, ...] | None:
        if isinstance(network_ref, FromStep):
            step = plan.steps[network_ref.step]
            if isinstance(step, DeriveNetworkStep):
                return step.modifications
        return None

    @staticmethod
    def _arm_problems(
        where: str,
        arm: Arm | None,
        interventions: tuple[Intervention, ...],
        *,
        on_study_network: bool,
        derived_by: tuple[TopologyModification, ...] | None = None,
    ) -> list[str]:
        """An arm is realised by its own interventions, on the study's network unless it changes
        the topology (then on the network deriving exactly its changes). Unknown labels are left
        to the coverage check."""
        expected = arm.interventions if arm is not None else ()
        topology = arm.topology_changes if arm is not None else ()
        problems = []
        if interventions != expected:
            problems.append(f"{where}: its interventions are not those of its arm")
        if topology and on_study_network:
            problems.append(f"{where}: its arm changes the topology, but runs on the study network")
        if not topology and not on_study_network:
            problems.append(f"{where}: its arm keeps the topology, but runs on another network")
        if topology and derived_by is not None and derived_by != topology:
            problems.append(f"{where}: its network is derived with other changes than its arm's")
        return problems

    def _reused_problems(self, plan: StudyPlan, scenario_id: str, arm: Arm | None) -> list[str]:
        scenario = self.deps.scenarios.get(scenario_id)
        if scenario is None:
            return [f"reused scenario {scenario_id!r} does not exist"]
        if not self._ok_results(scenario_id):
            return [f"reused scenario {scenario_id!r} has no ok results"]
        return self._arm_problems(
            f"reused scenario {scenario_id!r}",
            arm,
            scenario.interventions,
            on_study_network=scenario.network_id == plan.network_id,
        )

    def _coverage_problems(self, plan: StudyPlan, question: Question) -> list[str]:
        """The plan realises exactly the arms the phase needs that no earlier phase realised
        (ADR-0027 §2, decided with the user for E5.10)."""
        realised = {e.arm for p in self.study.phases[:-1] for e in p.experiments}
        expected = [a for a in needed_arms(question, self._k) if a not in realised]
        actual = set(plan.arms)
        problems = [f"arm {a!r} is needed but not planned" for a in expected if a not in actual]
        for arm in sorted(actual - set(expected)):
            if arm in realised:
                problems.append(f"arm {arm!r} was already realised in an earlier phase")
            else:
                problems.append(f"arm {arm!r} is not needed by this phase")
        return problems

    # -- execution ----------------------------------------------------------------------------

    def _execute(self, plan: StudyPlan) -> bool:
        reused = tuple(
            Experiment(
                r.scenario_id, r.arm, r.role, r.purpose, self._ok_results(r.scenario_id), True
            )
            for r in plan.reused
        )
        if reused:
            self._set_phase(replace(self._phase, experiments=reused))
        produced: dict[int, str] = {}
        built: dict[int, int] = {}  # build step index -> index of its Experiment in the phase
        for i, step in enumerate(plan.steps):
            resolved = _resolve(step, produced)
            task = _data(resolved)
            try:
                record, experiment = self._run_step(resolved, task)
            except _StepFailed as failed:
                self._record_failure(resolved.kind, task, failed, pending=plan.steps[i + 1 :])
                return False
            except Exception as e:
                self._record_failure(resolved.kind, task, _crash(e), pending=plan.steps[i + 1 :])
                return False
            produced[i] = record.produced_ids[-1] if record.produced_ids else ""
            experiments = self._phase.experiments
            if experiment is not None:
                built[i] = len(experiments)
                experiments = (*experiments, experiment)
            elif isinstance(step, RunSimulationStep) and isinstance(step.scenario_id, FromStep):
                j = built[step.scenario_id.step]
                target = experiments[j]
                ids = (*target.result_ids, *record.produced_ids)
                target = replace(target, result_ids=tuple(dict.fromkeys(ids)))
                experiments = (*experiments[:j], target, *experiments[j + 1 :])
            self._record(record, experiments=experiments)
        self.network_id = produced[plan.network_id.step] if isinstance(
            plan.network_id, FromStep
        ) else plan.network_id
        self._add_networks(self.network_id)
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
        run = self._agent_call(lambda: self.deps.agents.network_author.author(network_task))
        self._output(run, "network_author")
        network = self._promote(lambda: self.deps.promotions.network(network_task, run), run.usage)
        self._add_networks(network.network_id)
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
        run = self._agent_call(lambda: self.deps.agents.demand_generator.generate(demand_task))
        self._output(run, "demand_generator")
        demand = self._promote(lambda: self.deps.promotions.demand(demand_task, run), run.usage)
        return StepRecord(step.kind, StepStatus.OK, task, (demand.demand_id,), usage=run.usage)

    def _reroute(self, step: RerouteDemandStep, task: Mapping[str, Any]) -> StepRecord:
        demand = self.deps.demands.get(_id(step.demand_id))
        network = self.deps.networks.get(_id(step.network_id))
        if demand is None or network is None:
            _fail(StepErrorKind.AGENT, "reroute_demand names a demand or network not stored")
        assert demand is not None and network is not None
        rerouted = self._promote(lambda: self.deps.promotions.reroute(demand, network), Usage())
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
            run = self._agent_call(lambda: self.deps.agents.scenario_builder.build(scenario_task))
            draft = self._output(run, "scenario_builder")
            usage = run.usage
            if draft.rejected:
                _fail(
                    StepErrorKind.USER_INPUT,
                    f"the Scenario Builder rejected {len(draft.rejected)} intervention(s)",
                    *(f"{r.intervention.type}: {r.reason}" for r in draft.rejected),
                    usage=usage,
                )
            scenario = self._promote(
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
            _fail(StepErrorKind.AGENT, f"scenario {step.scenario_id!r} is not stored")
        assert scenario is not None
        if scenario.is_online:
            _fail(
                StepErrorKind.INFRASTRUCTURE,
                "online scenarios (traci_api scripts) need the E2.5 runner",
                scenario.scenario_id,
            )
        seeds = step.seeds or DEFAULT_SEEDS
        existing = {s: self._existing_ok(scenario.scenario_id, s) for s in seeds}
        new_seeds = [s for s, result in existing.items() if result is None]
        self._check_budget(simulations=len(new_seeds))
        result_ids: list[str] = []
        ran = 0
        for seed in seeds:
            result = existing[seed]
            if result is None:
                ran += 1
                self.simulations += 1
                result = run_simulation(
                    scenario,
                    seed,
                    runner=self.deps.runner,
                    results=self.deps.results,
                    out_dir=self.deps.out_dir / "results",
                )
                if result.status is RunStatus.FAILED:
                    _fail(
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
                self._trace(
                    "note_status",
                    {"note_id": note.note_id, "result_id": result.result_id, "status": status},
                )

    # -- the Expert ---------------------------------------------------------------------------

    def _ask_expert(self) -> ExpertRound | None:
        round_no = self._k + 1
        assert self.network_id is not None
        # TODO(E5.3): one network per ExpertTask. Arms on a derived network have their results in
        # `result_ids` (readable), but the Expert's topology tools and `ask_expert`'s edge check
        # see only the study's network (docs/tfm-work-plan.md, E5.3).
        task = ExpertTask(
            question=self.study.question.text,
            mode=mode_for(self.study.question, round_no, self.max_rounds),
            network_id=self.network_id,
            result_ids=self._result_ids(),
        )
        ledger = EvidenceLedger()
        try:
            run = self._agent_call(lambda: self.deps.agents.expert.answer(task, ledger))
            self._output(run, "expert")
            network = self.deps.networks.get(task.network_id)
            if network is None:
                _fail(StepErrorKind.INFRASTRUCTURE, f"network {task.network_id!r} disappeared")
            assert network is not None
            query = self.deps.network_query_factory(network.net_xml.path)
            round_ = self._promote(lambda: ask_expert(task, run, ledger, query=query), run.usage)
        except _StepFailed as failed:
            self._record_failure("ask_expert", _data(task), failed)
            return None
        except Exception as e:
            self._record_failure("ask_expert", _data(task), _crash(e))
            return None
        forced_by_limit = self.study.question.mode is Mode.FREE and round_no == self.max_rounds
        round_ = replace(round_, forced_by_limit=forced_by_limit)
        self.ledger = ledger
        record = StepRecord("ask_expert", StepStatus.OK, _data(task), usage=run.usage)
        self._record(record, round_=round_)
        return round_

    # -- closing ------------------------------------------------------------------------------

    def _write_notes(self) -> None:
        final = self._phase.round
        assert final is not None and self.ledger is not None and self.network_id is not None
        ledger, network_id = self.ledger, self.network_id
        try:
            task = NoteTask(round=final, scenarios=self._allow_list())
            run = self._agent_call(lambda: self.deps.agents.note_writer.write(task))
            written = write_note(
                run,
                ledger,
                task,
                network_id=network_id,
                study_id=self.study.study_id,
                notes=self.deps.notes,
            )
        except Exception as e:
            self._trace("note_writer_failed", {"error": _describe(e)})
            return
        self._set(note_ids=tuple(n.note_id for n in written))
        self._trace("notes_written", {"note_ids": [n.note_id for n in written]})

    def _allow_list(self) -> tuple[NoteScenario, ...]:
        """Every scenario of the study, plus the predicted id of each arm of the original question
        that was not realised and keeps the topology (ADR-0026)."""
        entries: dict[str, NoteScenario] = {}
        experiments = [e for p in self.study.phases for e in p.experiments]
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
        question = self.study.question
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
        task = {"study_id": self.study.study_id}
        try:
            run = self._agent_call(lambda: self.deps.agents.composer.compose(self.study))
            self._output(run, "composer")
            report = self._promote(lambda: self.deps.promotions.report(self.study, run), run.usage)
        except _StepFailed as failed:
            self._record_failure("compose_report", task, failed)
            return
        except Exception as e:
            self._record_failure("compose_report", task, _crash(e))
            return
        record = StepRecord("compose_report", StepStatus.OK, task, usage=run.usage)
        self._record(record, status=StudyStatus.COMPLETED, report=report)

    # -- agent calls, budget, promotion -------------------------------------------------------

    def _agent_call(self, call: Callable[[], AgentRun[T]]) -> AgentRun[T]:
        self._check_budget(agent_calls=1)
        self.agent_calls += 1
        try:
            run = call()
        except Exception as e:
            _fail(StepErrorKind.INFRASTRUCTURE, f"agent call failed: {_describe(e)}")
            raise  # unreachable: _fail raises
        self.tokens += run.usage.input_tokens + run.usage.output_tokens
        return run

    @staticmethod
    def _output(run: AgentRun[T], agent: str) -> T:
        """The draft of a finished run, classified before any promotion sees it: a run cut by
        its budget is `budget`, any other run without a draft is `agent`."""
        if run.stop_reason is StopReason.OUTPUT and run.output is not None:
            return run.output
        if run.stop_reason is StopReason.BUDGET:
            _fail(StepErrorKind.BUDGET, f"{agent} ran out of its budget", usage=run.usage)
        _fail(
            StepErrorKind.AGENT,
            f"{agent} stopped on {run.stop_reason} without a draft",
            usage=run.usage,
        )
        raise AssertionError("unreachable")

    def _check_budget(self, *, agent_calls: int = 0, simulations: int = 0) -> None:
        budget = self.deps.budget
        if agent_calls and self.agent_calls + agent_calls > budget.max_agent_calls:
            _fail(
                StepErrorKind.BUDGET,
                "the study's agent-call budget is exhausted",
                f"{self.agent_calls} of {budget.max_agent_calls} agent calls used",
            )
        if agent_calls and self.tokens >= budget.max_tokens:
            _fail(
                StepErrorKind.BUDGET,
                "the study's token budget is exhausted",
                f"{self.tokens} of {budget.max_tokens} tokens used",
            )
        if simulations and self.simulations + simulations > budget.max_simulations:
            _fail(
                StepErrorKind.BUDGET,
                "the study's simulation budget is exhausted",
                f"{self.simulations} of {budget.max_simulations} simulations used, "
                f"{simulations} more needed",
            )

    @staticmethod
    def _promote(call: Callable[[], T], usage: Usage) -> T:
        """Runs a promotion: a target the network lacks is the user's (`user_input`), any other
        rejected draft the agent's (`agent`), anything else `infrastructure`."""
        try:
            return call()
        except _StepFailed:
            raise
        except UnknownTargetError as e:
            _fail(StepErrorKind.USER_INPUT, str(e), usage=usage)
        except NotImplementedError as e:
            _fail(StepErrorKind.INFRASTRUCTURE, _describe(e), usage=usage)
        except ValueError as e:
            _fail(StepErrorKind.AGENT, str(e), usage=usage)
        except Exception as e:
            _fail(StepErrorKind.INFRASTRUCTURE, _describe(e), usage=usage)
        raise AssertionError("unreachable")

    # -- study state --------------------------------------------------------------------------

    @property
    def _k(self) -> int:
        return len(self.study.phases) - 1

    @property
    def _phase(self) -> Phase:
        return self.study.phases[-1]

    def _ok_results(self, scenario_id: str) -> tuple[str, ...]:
        ok = [r for r in self.deps.results.list(scenario_id) if r.status is RunStatus.OK]
        return tuple(r.result_id for r in sorted(ok, key=lambda r: r.seed))

    def _result_ids(self) -> tuple[str, ...]:
        ids = (r for p in self.study.phases for e in p.experiments for r in e.result_ids)
        return tuple(dict.fromkeys(ids))

    def _add_networks(self, *network_ids: str) -> None:
        merged = tuple(dict.fromkeys((*self.study.network_ids, *network_ids)))
        if merged != self.study.network_ids:
            self.study = replace(self.study, network_ids=merged)

    def _record(
        self,
        record: StepRecord,
        *,
        experiments: tuple[Experiment, ...] | None = None,
        round_: ExpertRound | None = None,
        status: StudyStatus | None = None,
        report: Report | None = None,
    ) -> None:
        phase = self._phase
        phase = replace(
            phase,
            steps=(*phase.steps, record),
            experiments=phase.experiments if experiments is None else experiments,
            round=phase.round if round_ is None else round_,
        )
        self._trace_step(record)
        self._set_phase(phase, status=status, report=report)

    def _record_failure(
        self,
        tool: str,
        task: Mapping[str, Any],
        failure: _StepFailed,
        *,
        phase: Phase | None = None,
        pending: Sequence[PlanStep] = (),
    ) -> None:
        """The failed step, the plan steps left unrun and the `failed` status, in one state."""
        phase = phase or self._phase
        record = StepRecord(tool, StepStatus.FAILED, task, error=failure.error, usage=failure.usage)
        skipped = tuple(StepRecord(s.kind, StepStatus.SKIPPED) for s in pending)
        self._trace_step(record)
        self._set_phase(
            replace(phase, steps=(*phase.steps, record, *skipped)), status=StudyStatus.FAILED
        )

    def _set_phase(
        self, phase: Phase, *, status: StudyStatus | None = None, report: Report | None = None
    ) -> None:
        self._set(
            phases=(*self.study.phases[:-1], phase),
            status=status or self.study.status,
            report=report if report is not None else self.study.report,
        )

    def _set(self, **changes: Any) -> None:
        self.study = replace(self.study, **changes)
        self._store()

    def _store(self) -> None:
        self.deps.studies.store(self.study)

    def _trace_step(self, record: StepRecord) -> None:
        self._trace(
            "step",
            {
                "phase": self._k,
                "tool": record.tool,
                "status": record.status,
                "produced_ids": list(record.produced_ids),
                "usage": record.usage,
                "error": record.error,
            },
        )

    def _trace(self, event: str, payload: Mapping[str, Any]) -> None:
        self.deps.tracer.emit(self.study.study_id, event, payload)


def _describe(e: BaseException) -> str:
    if isinstance(e, _StepFailed):
        return e.error.message
    return f"{type(e).__name__}: {e}"


def _crash(e: BaseException) -> _StepFailed:
    """An exception nothing classified: the environment's fault (logs in the trace)."""
    return _StepFailed(StepError(StepErrorKind.INFRASTRUCTURE, _describe(e)))
