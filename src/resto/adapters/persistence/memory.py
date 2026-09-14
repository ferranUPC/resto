"""In-memory repositories for tests: the same port contracts as the SQLite reference
implementation, held in dicts. Only `ResultRepository` so far (E2.1)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from resto.adapters.persistence.sqlite.edgedata import query_edgedata as _aggregate_edgedata
from resto.domain.entities.simulation_result import SimulationResult


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
