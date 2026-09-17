"""Tools of the Network Expert agent as typed Python functions (DoD §2.2; ADR-0011, ADR-0018).

Facts reach the Expert only through these: topology via the NetworkMCP functions of
`application/tools/network.py`, simulated data via the `ResultRepository`/`ScenarioRepository`
ports (never by parsing an artifact file), and earlier interpretations via `search_notes`.

Two things are added on top of plain delegation, both bound in `build_expert_tools`:

- **Availability.** `ExpertTask.result_ids` is an allow-list: a result outside it cannot be read,
  listed, or used to reach its scenario. An empty list means no simulated evidence is available.
- **Evidence ledger.** Every successful call is recorded in an `EvidenceLedger` under a ref
  (`"q1"`, `"q2"`, ...) and returned to the agent as `{"ref": ..., "result": ...}`. The agent cites
  those refs in `ExpertAnswer.evidence`, and `use_cases/ask_expert.py` rejects any ref the ledger
  does not hold - which is what makes "every fact comes from a tool call visible in the trace"
  checkable instead of a prompt instruction.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Any

from resto.application.ports.llm import Tool
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import (
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.schemas import adapter_for
from resto.application.tools.network import build_network_tools
from resto.domain.entities.expert_note import ExpertNote
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.value_objects.tasks import ExpertTask

EXPERT_NETWORK_TOOLS = (
    "get_edge",
    "get_lanes",
    "get_neighbours",
    "shortest_path",
    "capacity_estimate",
    "get_tls",
)
RESULT_TOOLS = ("get_result", "list_results", "query_edgedata", "get_scenario")


class NotAvailableError(LookupError):
    """The id exists (or may exist) but is not among what this question may use."""


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    ref: str
    tool: str
    arguments: Mapping[str, Any]
    result: Any


class EvidenceLedger:
    """Every successful Expert tool call of one run, addressable by ref. Failed calls are not
    recorded: they returned no fact, so there is nothing to cite."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def record(self, tool: str, arguments: Mapping[str, Any], result: Any) -> str:
        ref = f"q{len(self._entries) + 1}"
        self._entries.append(LedgerEntry(ref, tool, dict(arguments), result))
        return ref

    def get(self, ref: str) -> LedgerEntry | None:
        return next((e for e in self._entries if e.ref == ref), None)

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._entries)

    def artifact_ids(self) -> frozenset[str]:
        """Paths and content hashes of every artifact a result tool call returned - the only
        artifacts an `EvidenceKind.ARTIFACT` citation may point at."""
        ids: set[str] = set()
        for entry in self._entries:
            if entry.tool == "get_result":
                ids |= _artifact_ids(entry.result)
            elif entry.tool == "list_results":
                for result in entry.result:
                    ids |= _artifact_ids(result)
        return frozenset(ids)


def _artifact_ids(result: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for artifact in result.get("artifacts", ()):
        ids.add(str(artifact["path"]))
        ids.add(str(artifact["content_hash"]))
    return ids


def _require_available(available: AbstractSet[str], result_id: str) -> None:
    if result_id not in available:
        raise NotAvailableError(
            f"result {result_id!r} is not among the results available to this question"
        )


def get_result(
    results: ResultRepository, available: AbstractSet[str], result_id: str
) -> Mapping[str, Any]:
    """One simulation result: scenario_id, seed, status, KPIs and artifact references.

    Raises:
        NotAvailableError: `result_id` is not available to this question.
        KeyError: no stored result has that id.
    """
    _require_available(available, result_id)
    result = results.get(result_id)
    if result is None:
        raise KeyError(f"result {result_id!r} not found")
    return adapter_for(SimulationResult).dump_python(result, mode="json")


def list_results(
    results: ResultRepository, available: AbstractSet[str], scenario_id: str
) -> list[Mapping[str, Any]]:
    """The available results of one scenario (one per seed), empty if none is available."""
    adapter = adapter_for(SimulationResult)
    return [
        adapter.dump_python(r, mode="json")
        for r in results.list(scenario_id)
        if r.result_id in available
    ]


def query_edgedata(
    results: ResultRepository,
    available: AbstractSet[str],
    result_id: str,
    edge_ids: Sequence[str] = (),
    window: Sequence[float] | None = None,
) -> Mapping[str, Any]:
    """Per-edge measures of one result over `[start, end)` simulation seconds (None: whole run).
    Empty `edge_ids` means every edge. Measures: sampled_seconds, density, occupancy, speed,
    waiting_time, time_loss, travel_time, entered, left (DATABASE_MCP_CONTRACT.md §5.4);
    waiting_time and time_loss are totals over all vehicles (vehicle-seconds).

    Raises:
        NotAvailableError: `result_id` is not available to this question.
        ValueError: `window` is not a `[start, end]` pair.
    """
    _require_available(available, result_id)
    if window is not None and len(window) != 2:
        raise ValueError("window must be [start, end] in simulation seconds")
    bounds = None if window is None else (float(window[0]), float(window[1]))
    return results.query_edgedata(result_id, list(edge_ids), bounds)


def get_scenario(
    scenarios: ScenarioRepository, available_scenarios: AbstractSet[str], scenario_id: str
) -> Mapping[str, Any]:
    """The scenario an available result was run on: its interventions and context tags - how
    to tell a baseline result from an intervention one.

    Raises:
        NotAvailableError: no available result belongs to `scenario_id`.
        KeyError: no stored scenario has that id.
    """
    if scenario_id not in available_scenarios:
        raise NotAvailableError(
            f"scenario {scenario_id!r} has no result available to this question"
        )
    scenario = scenarios.get(scenario_id)
    if scenario is None:
        raise KeyError(f"scenario {scenario_id!r} not found")
    return adapter_for(Scenario).dump_python(scenario, mode="json")


def search_notes(
    notes: NoteRepository,
    network_id: str,
    query: str,
    filters: Mapping[str, Any] | None = None,
    limit: int = 10,
) -> list[Mapping[str, Any]]:
    """Earlier notes on this network ranked by relevance to `query`, each with its score.
    Filters: status, basis, provenance, scenario_id, context_tags."""
    adapter = adapter_for(ExpertNote)
    return [
        {"note": adapter.dump_python(note, mode="json"), "score": score}
        for note, score in notes.search(query, network_id, filters or {}, limit)
    ]


_RESULT_ID = {"type": "string", "description": "Id of an available simulation result."}
_SCHEMAS: dict[str, Mapping[str, Any]] = {
    "get_result": {
        "type": "object",
        "properties": {"result_id": _RESULT_ID},
        "required": ["result_id"],
    },
    "list_results": {
        "type": "object",
        "properties": {"scenario_id": {"type": "string"}},
        "required": ["scenario_id"],
    },
    "query_edgedata": {
        "type": "object",
        "properties": {
            "result_id": _RESULT_ID,
            "edge_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Edge ids to return; empty or omitted for every edge.",
            },
            "window": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
                "description": "[start, end) in simulation seconds; omit for the whole run.",
            },
        },
        "required": ["result_id"],
    },
    "get_scenario": {
        "type": "object",
        "properties": {"scenario_id": {"type": "string"}},
        "required": ["scenario_id"],
    },
    "search_notes": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What you are looking for, in prose."},
            "filters": {
                "type": "object",
                "description": "Optional: status, basis, provenance, scenario_id, context_tags.",
            },
            "limit": {"type": "integer", "minimum": 1},
        },
        "required": ["query"],
    },
}


def _recorded(ledger: EvidenceLedger, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    def call(**kwargs: Any) -> Mapping[str, Any]:
        result = fn(**kwargs)
        return {"ref": ledger.record(name, kwargs, result), "result": result}

    return call


def _first_line(fn: Callable[..., Any]) -> str:
    return (fn.__doc__ or "").strip().splitlines()[0]


def build_expert_tools(
    *,
    task: ExpertTask,
    query: NetworkQuery,
    results: ResultRepository,
    scenarios: ScenarioRepository,
    notes: NoteRepository | None,
    ledger: EvidenceLedger,
) -> tuple[Tool, ...]:
    """The Expert's tool set for one task, every call recorded in `ledger`.

    `search_notes` is offered only when `task.notes_allowed`.

    Raises:
        ValueError: `task.notes_allowed` but no `notes` repository was given.
    """
    if task.notes_allowed and notes is None:
        raise ValueError("notes_allowed requires a NoteRepository")

    available = frozenset(task.result_ids)
    available_scenarios = frozenset(
        r.scenario_id for r in (results.get(rid) for rid in available) if r is not None
    )

    tools = [
        Tool(
            name=t.name,
            description=t.description,
            fn=_recorded(ledger, t.name, t.fn),
            input_schema=t.input_schema,
        )
        for t in build_network_tools(query)
        if t.name in EXPERT_NETWORK_TOOLS
    ]

    bound: list[tuple[str, Callable[..., Any], Callable[..., Any]]] = [
        (
            "get_result",
            get_result,
            lambda result_id: get_result(results, available, result_id),
        ),
        (
            "list_results",
            list_results,
            lambda scenario_id: list_results(results, available, scenario_id),
        ),
        (
            "query_edgedata",
            query_edgedata,
            lambda result_id, edge_ids=(), window=None: query_edgedata(
                results, available, result_id, edge_ids, window
            ),
        ),
        (
            "get_scenario",
            get_scenario,
            lambda scenario_id: get_scenario(scenarios, available_scenarios, scenario_id),
        ),
    ]
    if task.notes_allowed:
        assert notes is not None
        note_repo = notes
        bound.append(
            (
                "search_notes",
                search_notes,
                lambda query, filters=None, limit=10: search_notes(
                    note_repo, task.network_id, query, filters, limit
                ),
            )
        )

    tools.extend(
        Tool(
            name=name,
            description=_first_line(documented),
            fn=_recorded(ledger, name, fn),
            input_schema=_SCHEMAS[name],
        )
        for name, documented, fn in bound
    )
    return tuple(tools)
