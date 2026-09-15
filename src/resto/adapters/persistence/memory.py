"""In-memory repositories for tests: the same port contracts as the SQLite reference
implementation, held in dicts. `NetworkRepository`/`DemandRepository`/`ScenarioRepository` keep
`find`/`find_similar` intentionally simple (exact match plus an unranked/unfiltered fallback) —
good enough for a test double, not a second implementation of the SQLite adapter's ranking."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from resto.adapters.persistence.sqlite.edgedata import query_edgedata as _aggregate_edgedata
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.intervention import Intervention


class InMemoryNetworkRepository:
    def __init__(self) -> None:
        self._networks: dict[str, Network] = {}

    def store(self, network: Network) -> None:
        self._networks[network.network_id] = network

    def get(self, network_id: str) -> Network | None:
        return self._networks.get(network_id)

    def list(self) -> Sequence[Network]:
        return list(self._networks.values())

    def find(
        self,
        source: str | None = None,
        derived_from: str | None = None,
        label: str | None = None,
    ) -> Sequence[Network]:
        return [
            n
            for n in self._networks.values()
            if (derived_from is None or n.derived_from == derived_from)
            and (label is None or n.label == label)
        ]


class InMemoryDemandRepository:
    def __init__(self) -> None:
        self._demands: dict[str, Demand] = {}

    def store(self, demand: Demand) -> None:
        self._demands[demand.demand_id] = demand

    def get(self, demand_id: str) -> Demand | None:
        return self._demands.get(demand_id)

    def list(self, network_id: str) -> Sequence[Demand]:
        return [d for d in self._demands.values() if d.network_id == network_id]


class InMemoryScenarioRepository:
    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}

    def store(self, scenario: Scenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    def get(self, scenario_id: str) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def find_similar(
        self,
        network_id: str,
        demand_id: str,
        interventions: Iterable[Intervention],
        context_tags: Iterable[str],
        limit: int = 10,
    ) -> Sequence[tuple[Scenario, float]]:
        exact_id = scenario_id_for(network_id, demand_id, interventions, context_tags)
        exact = self._scenarios.get(exact_id)
        if exact is not None:
            return [(exact, 1.0)]
        candidates = [s for s in self._scenarios.values() if s.network_id == network_id]
        return [(s, 0.0) for s in candidates[:limit]]


class InMemoryResultRepository:
    def __init__(self) -> None:
        self._results: dict[str, SimulationResult] = {}

    def store(self, result: SimulationResult) -> None:
        self._results[result.result_id] = result

    def get(self, result_id: str) -> SimulationResult | None:
        return self._results.get(result_id)

    def list(self, scenario_id: str) -> Sequence[SimulationResult]:
        return [r for r in self._results.values() if r.scenario_id == scenario_id]

    def query_edgedata(
        self, result_id: str, edge_ids: Iterable[str], window: tuple[float, float] | None
    ) -> Mapping[str, Any]:
        result = self._results[result_id]
        edgedata = next((a for a in result.artifacts if a.kind == "edgedata"), None)
        if edgedata is None:
            return {}
        return _aggregate_edgedata(edgedata.path, list(edge_ids), window)
