"""The Coordinator's output: a typed, immutable plan the Executor walks (ADR-0023 §2, ADR-0025).

Ids that do not exist at planning time are written as `FromStep(i)`: the Executor substitutes the id
produced by step `i`. Each step variant mirrors the typed task of the use case it calls, with every
such id widened to `str | FromStep`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from resto.domain.value_objects.demand_source import DemandSource
from resto.domain.value_objects.demand_spec import DemandProfile
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.tasks import DEFAULT_CALIBRATION_ROUNDS, DEFAULT_NETWORK_ROUNDS
from resto.domain.value_objects.topology_modification import TopologyModification

Produces = Literal["network", "demand", "scenario", "result"]


@dataclass(frozen=True, slots=True)
class FromStep:
    """The id produced by step `step` of the same plan."""

    step: int

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("FromStep must point to a step index >= 0")


StepInput = tuple[FromStep, Produces]


def _step_inputs(*ids: tuple[Produces, str | FromStep]) -> tuple[StepInput, ...]:
    return tuple((ref, kind) for kind, ref in ids if isinstance(ref, FromStep))


def _check_depends_on(inputs: tuple[StepInput, ...], depends_on: tuple[int, ...]) -> None:
    if any(d < 0 for d in depends_on):
        raise ValueError("depends_on holds step indexes >= 0")
    missing = sorted({ref.step for ref, _ in inputs} - set(depends_on))
    if missing:
        raise ValueError(f"FromStep {missing} must also be listed in depends_on")


@dataclass(frozen=True, slots=True)
class GenerateNetworkStep:
    source: NetworkSource
    goals: tuple[str, ...] = ()
    modifications: tuple[TopologyModification, ...] = ()
    min_scc_ratio: float = 0.95
    probe_teleport_threshold: int = 0
    max_rounds: int = DEFAULT_NETWORK_ROUNDS
    depends_on: tuple[int, ...] = ()
    kind: Literal["generate_network"] = "generate_network"

    def __post_init__(self) -> None:
        _check_depends_on(self.inputs, self.depends_on)

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return ()

    @property
    def produces(self) -> Produces:
        return "network"


@dataclass(frozen=True, slots=True)
class DeriveNetworkStep:
    base_network_id: str | FromStep
    modifications: tuple[TopologyModification, ...]
    goals: tuple[str, ...] = ()
    min_scc_ratio: float = 0.95
    probe_teleport_threshold: int = 0
    max_rounds: int = DEFAULT_NETWORK_ROUNDS
    depends_on: tuple[int, ...] = ()
    kind: Literal["derive_network"] = "derive_network"

    def __post_init__(self) -> None:
        if not self.modifications:
            raise ValueError("deriving a network requires at least one modification")
        _check_depends_on(self.inputs, self.depends_on)

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("network", self.base_network_id))

    @property
    def produces(self) -> Produces:
        return "network"


@dataclass(frozen=True, slots=True)
class GenerateDemandStep:
    network_id: str | FromStep
    profile: DemandProfile
    seed: int
    sources: tuple[DemandSource, ...] = ()
    control_edges: tuple[str, ...] = ()
    tolerance: float = 0.15
    max_calibration_rounds: int = DEFAULT_CALIBRATION_ROUNDS
    depends_on: tuple[int, ...] = ()
    kind: Literal["generate_demand"] = "generate_demand"

    def __post_init__(self) -> None:
        _check_depends_on(self.inputs, self.depends_on)

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("network", self.network_id))

    @property
    def produces(self) -> Produces:
        return "demand"


@dataclass(frozen=True, slots=True)
class RerouteDemandStep:
    """The same trips re-routed on another network (deterministic, no agent)."""

    demand_id: str | FromStep
    network_id: str | FromStep
    depends_on: tuple[int, ...] = ()
    kind: Literal["reroute_demand"] = "reroute_demand"

    def __post_init__(self) -> None:
        _check_depends_on(self.inputs, self.depends_on)

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("demand", self.demand_id), ("network", self.network_id))

    @property
    def produces(self) -> Produces:
        return "demand"


@dataclass(frozen=True, slots=True)
class BuildScenarioStep:
    """`arm`, `role` and `purpose` are the Coordinator's: the Executor copies them into the
    `Experiment` this scenario and its runs become (ADR-0025 §5, ADR-0027 §3)."""

    network_id: str | FromStep
    demand_id: str | FromStep
    arm: str
    role: ExperimentRole
    purpose: str
    interventions: tuple[Intervention, ...] = ()
    context_tags: frozenset[str] = frozenset()
    allow_script: bool = True
    depends_on: tuple[int, ...] = ()
    kind: Literal["build_scenario"] = "build_scenario"

    def __post_init__(self) -> None:
        if not self.arm.strip():
            raise ValueError("a build_scenario step names the arm it realises")
        if not self.purpose.strip():
            raise ValueError("a build_scenario step requires a purpose")
        _check_depends_on(self.inputs, self.depends_on)

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("network", self.network_id), ("demand", self.demand_id))

    @property
    def produces(self) -> Produces:
        return "scenario"


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

    @property
    def inputs(self) -> tuple[StepInput, ...]:
        return _step_inputs(("scenario", self.scenario_id))

    @property
    def produces(self) -> Produces:
        return "result"


PlanStep = (
    GenerateNetworkStep
    | DeriveNetworkStep
    | GenerateDemandStep
    | RerouteDemandStep
    | BuildScenarioStep
    | RunSimulationStep
)
"""One variant per use case a plan may call. `ask_expert` and `compose_report` are not plan
steps: the Executor always runs them (ADR-0023 §2)."""


@dataclass(frozen=True, slots=True)
class ReusedExperiment:
    """A stored scenario whose ok results the Expert is given, without running anything."""

    scenario_id: str
    arm: str
    role: ExperimentRole
    purpose: str

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("a ReusedExperiment requires a scenario_id")
        if not self.arm.strip():
            raise ValueError("a ReusedExperiment names the arm it realises")
        if not self.purpose.strip():
            raise ValueError("a ReusedExperiment requires a purpose")


@dataclass(frozen=True, slots=True)
class StudyPlan:
    """Emitted by the Coordinator, one per phase; measured against gold plans. `network_id` is the
    network the study is about (`FromStep` when the plan creates it). Zero steps is valid: the
    Expert then answers from `reused` results only."""

    network_id: str | FromStep
    rationale: str
    steps: tuple[PlanStep, ...] = ()
    reused: tuple[ReusedExperiment, ...] = ()

    def __post_init__(self) -> None:
        for i, step in enumerate(self.steps):
            if any(d >= i for d in step.depends_on):
                raise ValueError(f"step {i} depends on a step that is not earlier")
            for ref, expected in step.inputs:
                self._check_ref(ref, expected, f"step {i}")
        if isinstance(self.network_id, FromStep):
            self._check_ref(self.network_id, "network", "network_id")
        scenario_ids = [r.scenario_id for r in self.reused]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("a scenario is reused more than once")
        arms = self.arms
        if len(set(arms)) != len(arms):
            raise ValueError("each arm is built or reused once per plan")

    @property
    def arms(self) -> tuple[str, ...]:
        """The arms this plan realises: reused first, then built, in order."""
        built = (s.arm for s in self.steps if isinstance(s, BuildScenarioStep))
        return (*(r.arm for r in self.reused), *built)

    def _check_ref(self, ref: FromStep, expected: Produces, where: str) -> None:
        if ref.step >= len(self.steps):
            raise ValueError(f"{where}: FromStep({ref.step}) is not a step of this plan")
        produced = self.steps[ref.step].produces
        if produced != expected:
            raise ValueError(
                f"{where}: FromStep({ref.step}) produces a {produced}, a {expected} is expected"
            )


@dataclass(frozen=True, slots=True)
class ClarificationRequest:
    """The Coordinator's other possible output: an ambiguity only the database reveals, e.g. two
    networks labelled "Gran Via". `candidates` are what the user picks from."""

    reason: str
    candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a ClarificationRequest requires a reason")


CoordinatorOutput = StudyPlan | ClarificationRequest
