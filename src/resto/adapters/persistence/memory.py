"""In-memory repositories for tests: the same port contracts as the SQLite reference
implementation, held in dicts. `NetworkRepository`/`DemandRepository`/`ScenarioRepository` keep
`find`/`find_similar` intentionally simple (exact match plus an unranked/unfiltered fallback) —
good enough for a test double, not a second implementation of the SQLite adapter's ranking."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from resto.adapters.embedding.hashing import HashingEmbedder
from resto.adapters.persistence.sqlite.edgedata import query_edgedata as _aggregate_edgedata
from resto.application.ports.embedding import Embedder
from resto.application.ports.errors import InvalidArgumentError, NotFoundError
from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote, NoteStatus
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.services.ids import scenario_id_for
from resto.domain.services.note_ranking import rank_notes
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


_VALID_NOTE_FILTERS = {"status", "basis", "provenance", "scenario_id", "context_tags"}


class InMemoryNoteRepository:
    """Same port contract and filter/ranking rules as `SqliteNoteRepository`, held in a dict."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._notes: dict[str, ExpertNote] = {}
        self._vectors: dict[str, tuple[float, ...]] = {}
        self._embedder = embedder or HashingEmbedder()

    def store(self, note: ExpertNote) -> None:
        self._notes[note.note_id] = note
        self._vectors[note.note_id] = self._embedder.embed(note.text)

    def search(
        self,
        query: str,
        network_id: str,
        filters: Mapping[str, Any],
        limit: int = 10,
    ) -> Sequence[tuple[ExpertNote, float]]:
        unknown = set(filters) - _VALID_NOTE_FILTERS
        if unknown:
            raise InvalidArgumentError(f"unknown search_notes filter key(s): {sorted(unknown)}")

        required_tags = set(filters.get("context_tags", ()))
        candidates = [
            (note, self._vectors[note.note_id])
            for note in self._notes.values()
            if note.network_id == network_id
            and (note.status.value in filters["status"] if "status" in filters else True)
            and (note.basis.value in filters["basis"] if "basis" in filters else True)
            and (
                note.provenance.value in filters["provenance"] if "provenance" in filters else True
            )
            and (note.scenario_id == filters.get("scenario_id", note.scenario_id))
            and required_tags.issubset(note.context_tags)
        ]
        query_vector = self._embedder.embed(query)
        ranked = rank_notes(query_vector, candidates, limit=limit)
        return [(scored.note, scored.score) for scored in ranked]

    def update_status(self, note_id: str, status: NoteStatus) -> None:
        note = self._notes.get(note_id)
        if note is None:
            raise NotFoundError(f"note {note_id} not found")
        self._notes[note_id] = note.with_status(status)
