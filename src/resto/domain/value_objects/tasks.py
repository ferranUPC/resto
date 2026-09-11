"""Typed tasks the Coordinator sends to each specialist agent (the *what*)."""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.demand_source import DemandSource
from resto.domain.value_objects.demand_spec import DemandProfile
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.topology_modification import TopologyModification

DEFAULT_NETWORK_ROUNDS = 5
DEFAULT_CALIBRATION_ROUNDS = 5


@dataclass(frozen=True, slots=True)
class NetworkTask:
    source: NetworkSource | None = None
    base_network_id: str | None = None
    goals: tuple[str, ...] = ()
    modifications: tuple[TopologyModification, ...] = ()
    min_scc_ratio: float = 0.95
    probe_teleport_threshold: int = 0
    max_rounds: int = DEFAULT_NETWORK_ROUNDS

    def __post_init__(self) -> None:
        if (self.source is None) == (self.base_network_id is None):
            raise ValueError("exactly one of source or base_network_id must be set")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")


@dataclass(frozen=True, slots=True)
class DemandTask:
    network_id: str
    profile: DemandProfile
    seed: int
    sources: tuple[DemandSource, ...] = ()
    control_edges: tuple[str, ...] = ()
    tolerance: float = 0.15
    max_calibration_rounds: int = DEFAULT_CALIBRATION_ROUNDS

    def __post_init__(self) -> None:
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
    allow_script: bool = True


@dataclass(frozen=True, slots=True)
class ExpertTask:
    question: str
    mode: Mode
    network_id: str
    result_ids: tuple[str, ...] = ()
    notes_allowed: bool = True

    def __post_init__(self) -> None:
        if not self.question.strip():
            raise ValueError("an ExpertTask requires a question")


Task = NetworkTask | DemandTask | ScenarioTask | ExpertTask
