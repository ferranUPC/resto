"""Repository ports. Networks/demands/scenarios/results/notes map 1:1 to DatabaseMCP
capabilities; StudyRepository is a framework port outside that contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Protocol

from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote, NoteStatus
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.entities.study import Study
from resto.domain.value_objects.intervention import Intervention


class NetworkRepository(Protocol):
    def store(self, network: Network) -> None: ...
    def get(self, network_id: str) -> Network | None: ...
    def list(self) -> Sequence[Network]: ...
    def find(
        self, source: str | None = None, derived_from: str | None = None
    ) -> Sequence[Network]: ...


class DemandRepository(Protocol):
    def store(self, demand: Demand) -> None: ...
    def get(self, demand_id: str) -> Demand | None: ...
    def list(self, network_id: str) -> Sequence[Demand]: ...


class ScenarioRepository(Protocol):
    def store(self, scenario: Scenario) -> None: ...
    def get(self, scenario_id: str) -> Scenario | None: ...
    def find_similar(
        self, network_id: str, interventions: Iterable[Intervention], context_tags: Iterable[str]
    ) -> Sequence[Scenario]: ...


class ResultRepository(Protocol):
    def store(self, result: SimulationResult) -> None: ...
    def get(self, result_id: str) -> SimulationResult | None: ...
    def list(self, scenario_id: str) -> Sequence[SimulationResult]: ...
    def query_edgedata(
        self, result_id: str, edge_ids: Iterable[str], window: tuple[float, float] | None
    ) -> Mapping[str, Any]: ...


class NoteRepository(Protocol):
    def store(self, note: ExpertNote) -> None: ...
    def search(
        self, query: str, network_id: str, filters: Mapping[str, Any]
    ) -> Sequence[ExpertNote]: ...
    def update_status(self, note_id: str, status: NoteStatus) -> None: ...


class HistoricalDemandSource(Protocol):
    """Optional DatabaseMCP capability."""

    def get_historical_demand(
        self, network_id: str, day_type: str, hour: int
    ) -> Mapping[str, Any]: ...


class StudyRepository(Protocol):
    def store(self, study: Study) -> None: ...
    def get(self, study_id: str) -> Study | None: ...
