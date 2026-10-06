"""Typed tasks sent to each specialist agent (the *what*)."""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import TopologyModification


@dataclass(frozen=True, slots=True)
class NetworkTask:
    """The Network Author's task for a `derive_network` step: edit `base_network_id`."""

    base_network_id: str
    max_rounds: int
    goals: tuple[str, ...] = ()
    modifications: tuple[TopologyModification, ...] = ()
    min_scc_ratio: float = 0.95
    probe_teleport_threshold: int = 0

    def __post_init__(self) -> None:
        if not self.base_network_id:
            raise ValueError("a NetworkTask requires a base_network_id")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")


@dataclass(frozen=True, slots=True)
class ObtainNetworkTask:
    """The Network Author's task for an `obtain_network` step: resolve `network_ref`."""

    network_ref: str
    max_rounds: int
    goals: tuple[str, ...] = ()
    min_scc_ratio: float = 0.95
    probe_teleport_threshold: int = 0

    def __post_init__(self) -> None:
        if not self.network_ref.strip():
            raise ValueError("an ObtainNetworkTask requires the network reference")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")


@dataclass(frozen=True, slots=True)
class ObtainDemandTask:
    """The Demand Generator's task for an `obtain_demand` step, on a network already resolved."""

    network_id: str
    seed: int
    max_calibration_rounds: int
    demand_ref: str | None = None
    window: TimeWindow | None = None
    """The study window, derived from the question by code (`study_window`); none when no
    intervention has a window."""
    tolerance: float = 0.15

    def __post_init__(self) -> None:
        if not self.network_id:
            raise ValueError("an ObtainDemandTask requires a network_id")
        if not 0 < self.tolerance < 1:
            raise ValueError("tolerance must be a fraction in (0, 1)")
        if self.max_calibration_rounds < 1:
            raise ValueError("max_calibration_rounds must be >= 1")


@dataclass(frozen=True, slots=True)
class ScenarioTask:
    network_id: str
    demand_id: str
    interventions: tuple[Intervention, ...] = ()
    context_tags: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ExpertTask:
    """One Expert round. `network_ids` is the study's network scope (`GLOSSARY.md`) as it stood
    when the round started (ADR-0032)."""

    question: str
    mode: Mode
    network_ids: tuple[str, ...]
    result_ids: tuple[str, ...] = ()
    notes_allowed: bool = True

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("an ExpertTask requires a question")
        if not self.network_ids:
            raise ValueError("an ExpertTask requires at least one network in its scope")
        if len(set(self.network_ids)) != len(self.network_ids):
            raise ValueError("an ExpertTask scope names each network once")


@dataclass(frozen=True, slots=True)
class NoteScenario:
    """One entry of the note writer's allow-list. `simulated` is true when the scenario has ok
    results in the study; false for the predicted id of an intervention that was not simulated
    (ADR-0026). `network_id` is the network of the scenario, which a note about it is stored under
    (ADR-0032); the note writer never sees it or chooses it."""

    scenario_id: str
    arm: str
    role: ExperimentRole
    purpose: str
    simulated: bool
    network_id: str

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("a NoteScenario requires a scenario_id")
        if not self.network_id:
            raise ValueError("a NoteScenario requires a network_id")


@dataclass(frozen=True, slots=True)
class NoteTask:
    """The note writer's input: the study's final round and the scenarios a note may be about.
    `base_network_id` is where a note with no scenario is stored (ADR-0032)."""

    round: ExpertRound
    base_network_id: str
    scenarios: tuple[NoteScenario, ...] = ()

    def __post_init__(self) -> None:
        if self.round.answer.needs_simulation:
            raise ValueError("notes are written after the final round, which answers")
        if not self.base_network_id:
            raise ValueError("a NoteTask requires a base_network_id")
        ids = [s.scenario_id for s in self.scenarios]
        if len(set(ids)) != len(ids):
            raise ValueError("a scenario appears twice in the allow-list")

    def scenario(self, scenario_id: str) -> NoteScenario | None:
        return next((s for s in self.scenarios if s.scenario_id == scenario_id), None)


Task = NetworkTask | ObtainNetworkTask | ObtainDemandTask | ScenarioTask | ExpertTask | NoteTask
