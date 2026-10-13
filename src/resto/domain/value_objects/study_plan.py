"""The planner's output: a typed, immutable plan the Executor walks (ADR-0023 §2, ADR-0025).

Ids that do not exist at planning time are written as `FromStep(i)`: the Executor substitutes the id
produced by step `i`. Each step variant mirrors the typed task of the use case it calls, with every
such id widened to `str | FromStep`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.step_record import StepRecord
from resto.domain.value_objects.topology_modification import TopologyModification

if TYPE_CHECKING:  # the phase holds its plan: `Phase` is imported for the annotations only
    from resto.domain.entities.study import Phase

Produces = Literal["network", "demand", "scenario", "result"]


@dataclass(frozen=True, slots=True)
class FromStep:
    """The id produced by step `step` of the same plan."""

    step: int

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("FromStep must point to a step index >= 0")


StepInput = tuple[FromStep, Produces]
StepRef = tuple[Produces, str]
"""An id a step names directly, not through `FromStep`, and its kind."""


def _step_inputs(*ids: tuple[Produces, str | FromStep]) -> tuple[StepInput, ...]:
    return tuple((ref, kind) for kind, ref in ids if isinstance(ref, FromStep))


def _refs(*ids: tuple[Produces, str | FromStep]) -> tuple[StepRef, ...]:
    return tuple((kind, ref) for kind, ref in ids if isinstance(ref, str))


def _check_depends_on(inputs: tuple[StepInput, ...], depends_on: tuple[int, ...]) -> None:
    if any(d < 0 for d in depends_on):
        raise ValueError("depends_on holds step indexes >= 0")
    missing = sorted({ref.step for ref, _ in inputs} - set(depends_on))
    if missing:
        raise ValueError(f"FromStep {missing} must also be listed in depends_on")


def _unchanged(phase: Phase, reused: tuple[str, ...]) -> Phase:
    """The effect of a step that builds no scenario and runs nothing: none. Only those two reuse
    stored results."""
    if reused:
        raise ValueError("only build_scenario and run_simulation steps reuse results")
    return phase


@dataclass(frozen=True, slots=True)
class ObtainNetworkStep:
    """The Network Author resolves the network the Parser named: it finds a stored one or has one
    promoted from its draft (ADR-0037 §2). `network_ref` is the Parser's text, verbatim."""

    network_ref: str
    goals: tuple[str, ...] = ()
    min_scc_ratio: float = 0.95
    probe_teleport_threshold: int = 0
    max_rounds: int | None = None
    """Rounds the Network Author may take; none means the configured limit (`.env`)."""
    depends_on: tuple[int, ...] = ()
    kind: Literal["obtain_network"] = "obtain_network"

    def __post_init__(self) -> None:
        if not self.network_ref.strip():
            raise ValueError("an obtain_network step requires the network reference")
        _check_depends_on(self.inputs, self.depends_on)

    def refs(self) -> tuple[StepRef, ...]:
        """None: `network_ref` is the Parser's text, not an id."""
        return ()

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return ()

    @property
    def produces(self) -> Produces:
        return "network"

    def apply(self, phase: Phase, record: StepRecord, reused: tuple[str, ...]) -> Phase:
        return _unchanged(phase, reused)


@dataclass(frozen=True, slots=True)
class DeriveNetworkStep:
    base_network_id: str | FromStep
    modifications: tuple[TopologyModification, ...]
    goals: tuple[str, ...] = ()
    min_scc_ratio: float = 0.95
    probe_teleport_threshold: int = 0
    max_rounds: int | None = None
    """Rounds the Network Author may take; none means the configured limit (`.env`)."""
    depends_on: tuple[int, ...] = ()
    kind: Literal["derive_network"] = "derive_network"

    def __post_init__(self) -> None:
        if not self.modifications:
            raise ValueError("deriving a network requires at least one modification")
        _check_depends_on(self.inputs, self.depends_on)

    def refs(self) -> tuple[StepRef, ...]:
        return _refs(("network", self.base_network_id))

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("network", self.base_network_id))

    @property
    def produces(self) -> Produces:
        return "network"

    def apply(self, phase: Phase, record: StepRecord, reused: tuple[str, ...]) -> Phase:
        return _unchanged(phase, reused)


@dataclass(frozen=True, slots=True)
class ObtainDemandStep:
    """The Demand Generator resolves the demand for a network an earlier step produced:
    `network_id` is a `FromStep` to that step, never an id or the reference (ADR-0037 §3).
    `StudyPlan` enforces it; the Executor's resolved copy of the step holds the id the
    `FromStep` pointed to. `demand_ref` is the Parser's phrase; none means the request names
    no demand and the specialist asks."""

    network_id: str | FromStep
    seed: int
    demand_ref: str | None = None
    tolerance: float = 0.15
    max_calibration_rounds: int | None = None
    """Calibration rounds the Demand Generator may take; none means the configured limit."""
    depends_on: tuple[int, ...] = ()
    kind: Literal["obtain_demand"] = "obtain_demand"

    def __post_init__(self) -> None:
        if self.demand_ref is not None and not self.demand_ref.strip():
            raise ValueError("demand_ref, when given, must not be blank")
        _check_depends_on(self.inputs, self.depends_on)

    def refs(self) -> tuple[StepRef, ...]:
        return _refs(("network", self.network_id))

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("network", self.network_id))

    @property
    def produces(self) -> Produces:
        return "demand"

    def apply(self, phase: Phase, record: StepRecord, reused: tuple[str, ...]) -> Phase:
        return _unchanged(phase, reused)


@dataclass(frozen=True, slots=True)
class RerouteDemandStep:
    """The same trips re-routed on another network (deterministic, no agent)."""

    demand_id: str | FromStep
    network_id: str | FromStep
    depends_on: tuple[int, ...] = ()
    kind: Literal["reroute_demand"] = "reroute_demand"

    def __post_init__(self) -> None:
        _check_depends_on(self.inputs, self.depends_on)

    def refs(self) -> tuple[StepRef, ...]:
        return _refs(("demand", self.demand_id), ("network", self.network_id))

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("demand", self.demand_id), ("network", self.network_id))

    @property
    def produces(self) -> Produces:
        return "demand"

    def apply(self, phase: Phase, record: StepRecord, reused: tuple[str, ...]) -> Phase:
        return _unchanged(phase, reused)


@dataclass(frozen=True, slots=True)
class BuildScenarioStep:
    """`arm`, `role` and `purpose` are the planner's: the Executor copies them into the
    `Experiment` this scenario and its runs become (ADR-0025 §5, ADR-0027 §3)."""

    network_id: str | FromStep
    demand_id: str | FromStep
    arm: str
    role: ExperimentRole
    purpose: str
    interventions: tuple[Intervention, ...] = ()
    context_tags: frozenset[str] = frozenset()
    depends_on: tuple[int, ...] = ()
    kind: Literal["build_scenario"] = "build_scenario"

    def __post_init__(self) -> None:
        if not self.arm.strip():
            raise ValueError("a build_scenario step names the arm it realises")
        if not self.purpose.strip():
            raise ValueError("a build_scenario step requires a purpose")
        _check_depends_on(self.inputs, self.depends_on)

    def refs(self) -> tuple[StepRef, ...]:
        return _refs(("network", self.network_id), ("demand", self.demand_id))

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("network", self.network_id), ("demand", self.demand_id))

    @property
    def produces(self) -> Produces:
        return "scenario"

    def apply(self, phase: Phase, record: StepRecord, reused: tuple[str, ...]) -> Phase:
        """The scenario `record` produced becomes the `Experiment` of this step's arm, with the
        stored results it reused (a scenario found by the hash of its request)."""
        if len(record.produced_ids) != 1:
            raise ValueError("a build_scenario step produces one scenario")
        experiment = Experiment(
            record.produced_ids[0],
            self.arm,
            self.role,
            self.purpose,
            phase.next_plan_index,
            result_ids=reused,
            reused=bool(reused),
        )
        return replace(phase, experiments=(*phase.experiments, experiment))


@dataclass(frozen=True, slots=True)
class RunSimulationStep:
    """`seeds=None` means the Executor's `DEFAULT_SEEDS`; one result per seed."""

    scenario_id: str | FromStep
    seeds: tuple[int, ...] | None = None
    depends_on: tuple[int, ...] = ()
    kind: Literal["run_simulation"] = "run_simulation"

    def __post_init__(self) -> None:
        if self.seeds is not None:
            if not self.seeds:
                raise ValueError("seeds, when given, must not be empty")
            if len(set(self.seeds)) != len(self.seeds):
                raise ValueError("seeds must not repeat")
            if any(s < 0 for s in self.seeds):
                raise ValueError("seeds must be >= 0")
        _check_depends_on(self.inputs, self.depends_on)

    def refs(self) -> tuple[StepRef, ...]:
        return _refs(("scenario", self.scenario_id))

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("scenario", self.scenario_id))

    @property
    def produces(self) -> Produces:
        return "result"

    def apply(self, phase: Phase, record: StepRecord, reused: tuple[str, ...]) -> Phase:
        """The run's results join, without repeats, the experiment of the build step its scenario
        comes from. A run on a stored scenario (an id in the plan) joins none. `reused` are the
        results of the seeds the run did not run again."""
        if not set(reused) <= set(record.produced_ids):
            raise ValueError("a run can reuse only results it holds")
        if not isinstance(self.scenario_id, FromStep):
            return phase
        built = self.scenario_id.step
        if not any(e.step_index == built for e in phase.experiments):
            raise ValueError(f"step {built} built no experiment of this phase")
        experiments = tuple(
            replace(e, result_ids=tuple(dict.fromkeys((*e.result_ids, *record.produced_ids))))
            if e.step_index == built
            else e
            for e in phase.experiments
        )
        return replace(phase, experiments=experiments)


PlanStep = (
    ObtainNetworkStep
    | DeriveNetworkStep
    | ObtainDemandStep
    | RerouteDemandStep
    | BuildScenarioStep
    | RunSimulationStep
)
"""One variant per use case a plan may call. Asking the Expert and composing the report are not
plan steps: the Executor always runs them (ADR-0023 §2). Each variant declares the ids it names
directly (`refs`) and its effect on its phase once recorded (`apply`), so neither the plan
validator nor `Study.record_step` matches on step types (ADR-0042 §6)."""


@dataclass(frozen=True, slots=True)
class StudyPlan:
    """Emitted by the planner, one per phase; measured against gold plans. `network_id` is the
    network the study is about (`FromStep` when the plan creates it). A plan always contains an
    `obtain_network` step (ADR-0037 §2), so it is never empty."""

    network_id: str | FromStep
    rationale: str
    steps: tuple[PlanStep, ...]

    def __post_init__(self) -> None:
        for i, step in enumerate(self.steps):
            if any(d >= i for d in step.depends_on):
                raise ValueError(f"step {i} depends on a step that is not earlier")
            for ref, expected in step.inputs:
                self._check_ref(ref, expected, f"step {i}")
            if isinstance(step, ObtainDemandStep) and not isinstance(step.network_id, FromStep):
                raise ValueError(f"step {i}: obtain_demand takes its network by FromStep")
        if not any(isinstance(s, ObtainNetworkStep) for s in self.steps):
            raise ValueError("a plan always contains an obtain_network step")
        if isinstance(self.network_id, FromStep):
            self._check_ref(self.network_id, "network", "network_id")
        arms = self.arms
        if len(set(arms)) != len(arms):
            raise ValueError("each arm is built once per plan")

    @property
    def arms(self) -> tuple[str, ...]:
        """The arms this plan builds, in order."""
        return tuple(s.arm for s in self.steps if isinstance(s, BuildScenarioStep))

    def _check_ref(self, ref: FromStep, expected: Produces, where: str) -> None:
        if ref.step >= len(self.steps):
            raise ValueError(f"{where}: FromStep({ref.step}) is not a step of this plan")
        produced = self.steps[ref.step].produces
        if produced != expected:
            raise ValueError(
                f"{where}: FromStep({ref.step}) produces a {produced}, a {expected} is expected"
            )
