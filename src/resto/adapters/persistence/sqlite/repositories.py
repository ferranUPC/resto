"""SQLite + in-process cosine repositories - the DatabaseMCP reference implementation
(ADR-0012, DATABASE_MCP_CONTRACT.md).

Each aggregate is stored as one row: its id, its full JSON serialisation (via
`application.schemas.ADAPTERS`, the same round-trip-tested TypeAdapters E0.3 already built - no
separate column-mapping code to keep in sync with the domain types), and a handful of denormalised
columns purely for filtering/ordering. `store_*` idempotency (§3: identical content on a repeat
`store_*` is a no-op, different content under an existing id is `CONFLICT`) is the same rule for
`demands`/`scenarios`/`results`/`notes` (`_idempotent_store` below); `networks` is the one
exception, because `Network.label` is explicitly allowed to change in place (§3, §5.1).

`find_similar_scenario`'s identity short-circuit (§5.3 step 1) computes the real
`scenario_id_for(network_id, demand_id, interventions, context_tags)` (domain/services/ids.py) and
looks it up directly - `demand_id` is therefore a required argument of `find_similar`, not
optional, fixed after an earlier draft of this module found the contract's original tool
signature omitted it (see docs/DATABASE_MCP_CONTRACT.md §5.3, now corrected). `demand_id` plays no
part in step 2's Jaccard scoring: that ranking is deliberately about intervention/context *shape*
on a network, independent of which demand was used.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from resto.adapters.embedding.hashing import HashingEmbedder
from resto.adapters.persistence.sqlite.edgedata import query_edgedata as _aggregate_edgedata
from resto.application.ports.embedding import Embedder
from resto.application.ports.errors import ConflictError, InvalidArgumentError, NotFoundError
from resto.application.schemas import ADAPTERS
from resto.domain.entities.demand import Demand
from resto.domain.entities.expert_note import ExpertNote, NoteStatus
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.services.ids import scenario_id_for
from resto.domain.services.note_ranking import rank_notes
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.intervention_target import InterventionTarget

_SCHEMA = """
CREATE TABLE IF NOT EXISTS networks (
    network_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    source TEXT,
    derived_from TEXT,
    label TEXT
);
CREATE TABLE IF NOT EXISTS demands (
    demand_id TEXT PRIMARY KEY,
    network_id TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id TEXT PRIMARY KEY,
    network_id TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    result_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    note_id TEXT PRIMARY KEY,
    network_id TEXT NOT NULL,
    data TEXT NOT NULL,
    embedding TEXT NOT NULL,
    status TEXT NOT NULL,
    basis TEXT NOT NULL,
    provenance TEXT NOT NULL,
    scenario_id TEXT,
    context_tags TEXT NOT NULL
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    # check_same_thread=False: the MCP server dispatches each sync tool call to a worker thread
    # (mcp.server.mcpserver runs tools via anyio.to_thread.run_sync), so the connection built
    # in-process at server start-up is used from a different thread per call. There is no real
    # concurrent-write risk to guard against here - one process, one connection, calls handled
    # one at a time - so disabling sqlite3's own same-thread check is the correct fix, not a
    # workaround around an actual concurrency hazard.
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.executescript(_SCHEMA)
    return conn


def _idempotent_store(
    conn: sqlite3.Connection,
    table: str,
    id_col: str,
    id_value: str,
    data_json: bytes,
    extra_columns: Mapping[str, Any],
) -> bool:
    """Inserts a new row, or no-ops on a byte-identical repeat. Returns True if inserted.

    Raises ConflictError if `id_value` exists with a different `data` payload (§3).
    """
    row = conn.execute(f"SELECT data FROM {table} WHERE {id_col} = ?", (id_value,)).fetchone()  # noqa: S608
    text = data_json.decode("utf-8")
    if row is not None:
        if row[0] == text:
            return False
        raise ConflictError(f"{table}: {id_value} already exists with different content")
    columns = [id_col, "data", *extra_columns.keys()]
    values = [id_value, text, *extra_columns.values()]
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",  # noqa: S608
        values,
    )
    conn.commit()
    return True


class SqliteNetworkRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._adapter = ADAPTERS["Network"]

    def store(self, network: Network) -> None:
        data_json = self._adapter.dump_json(network)
        row = self._conn.execute(
            "SELECT data FROM networks WHERE network_id = ?", (network.network_id,)
        ).fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO networks (network_id, data, source, derived_from, label) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    network.network_id,
                    data_json.decode("utf-8"),
                    network.recipe.source.value if network.recipe.source else None,
                    network.derived_from,
                    network.label,
                ),
            )
            self._conn.commit()
            return
        if row[0] == data_json.decode("utf-8"):
            return  # exact no-op
        existing = self._adapter.validate_json(row[0])
        if existing == replace(network, label=existing.label):
            # only `label` differs - contract-exempt from CONFLICT (§3, §5.1)
            self._conn.execute(
                "UPDATE networks SET data = ?, label = ? WHERE network_id = ?",
                (data_json.decode("utf-8"), network.label, network.network_id),
            )
            self._conn.commit()
            return
        raise ConflictError(f"network {network.network_id} already exists with different content")

    def get(self, network_id: str) -> Network | None:
        row = self._conn.execute(
            "SELECT data FROM networks WHERE network_id = ?", (network_id,)
        ).fetchone()
        return self._adapter.validate_json(row[0]) if row else None

    def list(self) -> Sequence[Network]:
        rows = self._conn.execute("SELECT data FROM networks ORDER BY network_id ASC").fetchall()
        return [self._adapter.validate_json(r[0]) for r in rows]

    def find(
        self,
        source: str | None = None,
        derived_from: str | None = None,
        label: str | None = None,
    ) -> Sequence[Network]:
        clauses: list[str] = []
        params: list[Any] = []
        for column, value in (("source", source), ("derived_from", derived_from), ("label", label)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT data FROM networks {where} ORDER BY network_id ASC",  # noqa: S608
            params,
        ).fetchall()
        return [self._adapter.validate_json(r[0]) for r in rows]


class SqliteDemandRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._adapter = ADAPTERS["Demand"]

    def store(self, demand: Demand) -> None:
        _idempotent_store(
            self._conn,
            "demands",
            "demand_id",
            demand.demand_id,
            self._adapter.dump_json(demand),
            {"network_id": demand.network_id},
        )

    def get(self, demand_id: str) -> Demand | None:
        row = self._conn.execute(
            "SELECT data FROM demands WHERE demand_id = ?", (demand_id,)
        ).fetchone()
        return self._adapter.validate_json(row[0]) if row else None

    def list(self, network_id: str) -> Sequence[Demand]:
        rows = self._conn.execute(
            "SELECT data FROM demands WHERE network_id = ? ORDER BY demand_id ASC", (network_id,)
        ).fetchall()
        return [self._adapter.validate_json(r[0]) for r in rows]


_TARGET_ID_ATTR = {"edge": "edge_id", "lane": "lane_id", "tls": "tls_id", "taz": "taz_id"}


def _target_signature(target: InterventionTarget | None) -> tuple[str, str]:
    if target is None:
        return ("none", "")
    return (target.kind, getattr(target, _TARGET_ID_ATTR[target.kind]))


def _intervention_signature(iv: Intervention) -> tuple[str, str, str, str]:
    target_kind, target_id = _target_signature(iv.target)
    return (iv.type.value, target_kind, target_id, iv.strategy.value)


def _signature_set(interventions: Iterable[Intervention]) -> frozenset[tuple[str, str, str, str]]:
    return frozenset(_intervention_signature(iv) for iv in interventions)


def _jaccard(a: frozenset[Any], b: frozenset[Any]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


class SqliteScenarioRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._adapter = ADAPTERS["Scenario"]

    def store(self, scenario: Scenario) -> None:
        _idempotent_store(
            self._conn,
            "scenarios",
            "scenario_id",
            scenario.scenario_id,
            self._adapter.dump_json(scenario),
            {"network_id": scenario.network_id},
        )

    def get(self, scenario_id: str) -> Scenario | None:
        row = self._conn.execute(
            "SELECT data FROM scenarios WHERE scenario_id = ?", (scenario_id,)
        ).fetchone()
        return self._adapter.validate_json(row[0]) if row else None

    def find_similar(
        self,
        network_id: str,
        demand_id: str,
        interventions: Iterable[Intervention],
        context_tags: Iterable[str],
        limit: int = 10,
    ) -> Sequence[tuple[Scenario, float]]:
        interventions = tuple(interventions)
        context_tags = tuple(context_tags)

        # Step 1 (§5.3): exact identity, via the real hash - never approximated.
        exact_id = scenario_id_for(network_id, demand_id, interventions, context_tags)
        exact = self.get(exact_id)
        if exact is not None:
            return [(exact, 1.0)]

        # Step 2: rank by intervention-shape / context_tags similarity, demand_id irrelevant here.
        query_signature = _signature_set(interventions)
        query_tags = frozenset(context_tags)

        rows = self._conn.execute(
            "SELECT data FROM scenarios WHERE network_id = ? ORDER BY scenario_id ASC",
            (network_id,),
        ).fetchall()
        scored: list[tuple[Scenario, float]] = []
        for (data_json,) in rows:
            candidate = self._adapter.validate_json(data_json)
            score = 0.7 * _jaccard(
                query_signature, _signature_set(candidate.interventions)
            ) + 0.3 * _jaccard(query_tags, candidate.context_tags)
            if score > 0:
                scored.append((candidate, score))

        scored.sort(key=lambda pair: (-pair[1], pair[0].scenario_id))
        return scored[:limit]


class SqliteResultRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._adapter = ADAPTERS["SimulationResult"]

    def store(self, result: SimulationResult) -> None:
        _idempotent_store(
            self._conn,
            "results",
            "result_id",
            result.result_id,
            self._adapter.dump_json(result),
            {"scenario_id": result.scenario_id},
        )

    def get(self, result_id: str) -> SimulationResult | None:
        row = self._conn.execute(
            "SELECT data FROM results WHERE result_id = ?", (result_id,)
        ).fetchone()
        return self._adapter.validate_json(row[0]) if row else None

    def list(self, scenario_id: str) -> Sequence[SimulationResult]:
        rows = self._conn.execute(
            "SELECT data FROM results WHERE scenario_id = ? ORDER BY result_id ASC",
            (scenario_id,),
        ).fetchall()
        return [self._adapter.validate_json(r[0]) for r in rows]

    def query_edgedata(
        self, result_id: str, edge_ids: Iterable[str], window: tuple[float, float] | None
    ) -> Mapping[str, Any]:
        result = self.get(result_id)
        if result is None:
            raise NotFoundError(f"result {result_id} not found")
        edgedata_artifact = next((a for a in result.artifacts if a.kind == "edgedata"), None)
        if edgedata_artifact is None:
            return {}
        return _aggregate_edgedata(edgedata_artifact.path, list(edge_ids), window)


_VALID_NOTE_FILTERS = {"status", "basis", "provenance", "scenario_id", "context_tags"}


class SqliteNoteRepository:
    def __init__(self, conn: sqlite3.Connection, embedder: Embedder) -> None:
        self._conn = conn
        self._embedder = embedder
        self._adapter = ADAPTERS["ExpertNote"]

    def store(self, note: ExpertNote) -> None:
        vector = self._embedder.embed(note.text)
        _idempotent_store(
            self._conn,
            "notes",
            "note_id",
            note.note_id,
            self._adapter.dump_json(note),
            {
                "network_id": note.network_id,
                "status": note.status.value,
                "basis": note.basis.value,
                "provenance": note.provenance.value,
                "scenario_id": note.scenario_id,
                "context_tags": json.dumps(sorted(note.context_tags)),
                "embedding": json.dumps(list(vector)),
            },
        )

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

        clauses = ["network_id = ?"]
        params: list[Any] = [network_id]
        for key in ("status", "basis", "provenance"):
            if key in filters:
                values = list(filters[key])
                clauses.append(f"{key} IN ({','.join('?' for _ in values)})")
                params.extend(values)
        if "scenario_id" in filters:
            clauses.append("scenario_id = ?")
            params.append(filters["scenario_id"])

        rows = self._conn.execute(
            f"SELECT data, embedding, context_tags FROM notes WHERE {' AND '.join(clauses)}",  # noqa: S608
            params,
        ).fetchall()

        required_tags = set(filters.get("context_tags", ()))
        candidates: list[tuple[ExpertNote, tuple[float, ...]]] = []
        for data_json, embedding_json, context_tags_json in rows:
            if required_tags and not required_tags.issubset(set(json.loads(context_tags_json))):
                continue
            note = self._adapter.validate_json(data_json)
            candidates.append((note, tuple(json.loads(embedding_json))))

        query_vector = self._embedder.embed(query)
        ranked = rank_notes(query_vector, candidates, limit=limit)
        return [(scored.note, scored.score) for scored in ranked]

    def update_status(self, note_id: str, status: NoteStatus) -> None:
        row = self._conn.execute(
            "SELECT data FROM notes WHERE note_id = ?", (note_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"note {note_id} not found")
        updated = self._adapter.validate_json(row[0]).with_status(status)
        self._conn.execute(
            "UPDATE notes SET data = ?, status = ? WHERE note_id = ?",
            (self._adapter.dump_json(updated).decode("utf-8"), status.value, note_id),
        )
        self._conn.commit()


class SqliteDatabase:
    """Owns the shared connection/schema and every repository (DatabaseMCP's five required
    capability groups - `historical_demand` is optional and unimplemented here, contract §10
    point 3: its shape isn't pinned until E6.5 chooses a data source)."""

    def __init__(self, path: Path | str, embedder: Embedder | None = None) -> None:
        self.connection = connect(path)
        self.networks = SqliteNetworkRepository(self.connection)
        self.demands = SqliteDemandRepository(self.connection)
        self.scenarios = SqliteScenarioRepository(self.connection)
        self.results = SqliteResultRepository(self.connection)
        self.notes = SqliteNoteRepository(self.connection, embedder or HashingEmbedder())

    def close(self) -> None:
        self.connection.close()
