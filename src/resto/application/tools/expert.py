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

import statistics
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
RESULT_TOOLS = (
    "edge_stats",
    "rank_edges",
    "compare_edges",
    "compare_kpis",
    "get_result",
    "list_results",
    "query_edgedata",
    "get_scenario",
)
# per-vehicle means: undefined in a run where no vehicle was on the edge (ADR-0021)
_PER_VEHICLE = frozenset({"travel_time", "speed", "time_loss_per_vehicle"})
EDGE_MEASURES = (
    "travel_time",
    "speed",
    "occupancy",
    "density",
    "time_loss",
    "waiting_time",
    "entered",
    "left",
    "time_loss_per_vehicle",
)
KPI_NAMES = ("mean_delay", "mean_travel_time", "teleports", "departed", "arrived")


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


def _check_measure(measure: str) -> None:
    if measure not in EDGE_MEASURES:
        raise ValueError(f"unknown measure {measure!r}; use one of {', '.join(EDGE_MEASURES)}")


def _run_value(edge: Mapping[str, float], measure: str) -> float | None:
    """One run's value of `measure` on one edge, None where a per-vehicle mean is undefined."""
    if measure in _PER_VEHICLE and edge["sampled_seconds"] <= 0:
        return None
    if measure == "time_loss_per_vehicle":
        return edge["time_loss"] / edge["entered"] if edge["entered"] > 0 else None
    return float(edge[measure])


def _summary(values: Sequence[float | None]) -> dict[str, float | int] | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return {
        "mean": round(statistics.mean(present), 3),
        "std": round(statistics.stdev(present), 3) if len(present) > 1 else 0.0,
        "runs": len(present),
    }


def _per_run(
    results: ResultRepository,
    available: AbstractSet[str],
    result_ids: Sequence[str],
    edge_ids: Sequence[str],
    window: Sequence[float] | None,
) -> list[Mapping[str, Mapping[str, float]]]:
    if not result_ids:
        raise ValueError("give at least one result_id")
    for result_id in result_ids:
        _require_available(available, result_id)
    if window is not None and len(window) != 2:
        raise ValueError("window must be [start, end] in simulation seconds")
    bounds = None if window is None else (float(window[0]), float(window[1]))
    return [results.query_edgedata(rid, list(edge_ids), bounds) for rid in result_ids]


def _edge_summary(
    runs: Sequence[Mapping[str, Mapping[str, float]]], edge_id: str, measure: str
) -> dict[str, float | int] | None:
    return _summary([_run_value(run[edge_id], measure) for run in runs if edge_id in run])


def edge_stats(
    results: ResultRepository,
    available: AbstractSet[str],
    result_ids: Sequence[str],
    edge_ids: Sequence[str],
    window: Sequence[float] | None = None,
) -> Mapping[str, Any]:
    """Mean, std and run count of every measure on the given edges, across the given runs.

    Per-vehicle means (travel_time, speed, time_loss_per_vehicle) only count runs where the edge
    had traffic, and are null when none had: a null travel time means no vehicle crossed the edge.

    Raises:
        NotAvailableError: a result is not available to this question.
    """
    if not edge_ids:
        raise ValueError("name the edges; use rank_edges to search the whole network")
    runs = _per_run(results, available, result_ids, edge_ids, window)
    return {
        edge_id: {measure: _edge_summary(runs, edge_id, measure) for measure in EDGE_MEASURES}
        for edge_id in edge_ids
        if any(edge_id in run for run in runs)
    }


def rank_edges(
    results: ResultRepository,
    available: AbstractSet[str],
    result_ids: Sequence[str],
    measure: str,
    window: Sequence[float] | None = None,
    top_k: int = 10,
    min_value: float | None = None,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    """Edges of the whole network ranked by the mean of one measure across the given runs.

    With `min_value`, only edges whose mean exceeds it. Edges where a per-vehicle mean is undefined
    in every run are left out.
    """
    _check_measure(measure)
    runs = _per_run(results, available, result_ids, (), window)
    rows: list[dict[str, Any]] = []
    for edge_id in runs[0]:
        summary = _edge_summary(runs, edge_id, measure)
        if summary is None or (min_value is not None and summary["mean"] <= min_value):
            continue
        rows.append({"edge_id": edge_id, **summary})
    rows.sort(key=lambda row: row["mean"], reverse=not ascending)
    return rows[:top_k]


def compare_edges(
    results: ResultRepository,
    available: AbstractSet[str],
    baseline_result_ids: Sequence[str],
    treatment_result_ids: Sequence[str],
    measure: str,
    window: Sequence[float] | None = None,
    edge_ids: Sequence[str] = (),
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Per edge, the mean of one measure in baseline and treatment runs, the difference and the
    relative change in percent. With `edge_ids`, exactly those edges; otherwise the `top_k` edges
    with the largest absolute difference."""
    _check_measure(measure)
    baseline = _per_run(results, available, baseline_result_ids, edge_ids, window)
    treatment = _per_run(results, available, treatment_result_ids, edge_ids, window)
    rows: list[dict[str, Any]] = []
    for edge_id in edge_ids or list(treatment[0]):
        before = _edge_summary(baseline, edge_id, measure)
        after = _edge_summary(treatment, edge_id, measure)
        delta = pct = None
        if before is not None and after is not None:
            delta = round(after["mean"] - before["mean"], 3)
            pct = round(delta / before["mean"] * 100, 1) if before["mean"] != 0 else None
        rows.append(
            {
                "edge_id": edge_id,
                "baseline": before,
                "treatment": after,
                "delta": delta,
                "relative_change_pct": pct,
            }
        )
    if edge_ids:
        return rows
    ranked = sorted((r for r in rows if r["delta"] is not None), key=lambda r: -abs(r["delta"]))
    return ranked[:top_k]


def compare_kpis(
    results: ResultRepository,
    available: AbstractSet[str],
    baseline_result_ids: Sequence[str],
    treatment_result_ids: Sequence[str],
) -> Mapping[str, Any]:
    """Network-wide KPIs (mean_delay, mean_travel_time, teleports, departed, arrived): mean across
    baseline and treatment runs, the difference and the relative change in percent."""

    def kpis(result_ids: Sequence[str]) -> dict[str, dict[str, float | int] | None]:
        if not result_ids:
            raise ValueError("give at least one result_id per side")
        values: dict[str, list[float | None]] = {name: [] for name in KPI_NAMES}
        for result_id in result_ids:
            _require_available(available, result_id)
            result = results.get(result_id)
            if result is None or result.kpis is None:
                raise KeyError(f"result {result_id!r} has no KPIs")
            for name in KPI_NAMES:
                values[name].append(float(getattr(result.kpis, name)))
        return {name: _summary(v) for name, v in values.items()}

    before, after = kpis(baseline_result_ids), kpis(treatment_result_ids)
    out: dict[str, Any] = {}
    for name in KPI_NAMES:
        b, a = before[name], after[name]
        assert b is not None and a is not None
        delta = round(a["mean"] - b["mean"], 3)
        pct = round(delta / b["mean"] * 100, 1) if b["mean"] != 0 else None
        out[name] = {"baseline": b, "treatment": a, "delta": delta, "relative_change_pct": pct}
    return out


def query_edgedata(
    results: ResultRepository,
    available: AbstractSet[str],
    result_id: str,
    edge_ids: Sequence[str] = (),
    window: Sequence[float] | None = None,
) -> Mapping[str, Any]:
    """EXPENSIVE raw per-run data of every edge (~17,000 characters per result): prefer edge_stats,
    rank_edges or compare_edges, and use this only when they cannot express what you need.

    Per-edge measures of one result over `[start, end)` simulation seconds (None: whole run).
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
_RESULT_IDS = {"type": "array", "items": {"type": "string"}, "minItems": 1}
_WINDOW = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 2,
    "maxItems": 2,
    "description": "[start, end) in simulation seconds; omit for the whole run.",
}
_MEASURE = {"type": "string", "enum": list(EDGE_MEASURES)}
_SCHEMAS: dict[str, Mapping[str, Any]] = {
    "edge_stats": {
        "type": "object",
        "properties": {
            "result_ids": _RESULT_IDS,
            "edge_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "window": _WINDOW,
        },
        "required": ["result_ids", "edge_ids"],
    },
    "rank_edges": {
        "type": "object",
        "properties": {
            "result_ids": _RESULT_IDS,
            "measure": _MEASURE,
            "window": _WINDOW,
            "top_k": {"type": "integer", "minimum": 1},
            "min_value": {"type": "number"},
            "ascending": {"type": "boolean"},
        },
        "required": ["result_ids", "measure"],
    },
    "compare_edges": {
        "type": "object",
        "properties": {
            "baseline_result_ids": _RESULT_IDS,
            "treatment_result_ids": _RESULT_IDS,
            "measure": _MEASURE,
            "window": _WINDOW,
            "edge_ids": {"type": "array", "items": {"type": "string"}},
            "top_k": {"type": "integer", "minimum": 1},
        },
        "required": ["baseline_result_ids", "treatment_result_ids", "measure"],
    },
    "compare_kpis": {
        "type": "object",
        "properties": {"baseline_result_ids": _RESULT_IDS, "treatment_result_ids": _RESULT_IDS},
        "required": ["baseline_result_ids", "treatment_result_ids"],
    },
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
            "edge_stats",
            edge_stats,
            lambda result_ids, edge_ids, window=None: edge_stats(
                results, available, result_ids, edge_ids, window
            ),
        ),
        (
            "rank_edges",
            rank_edges,
            lambda result_ids, measure, window=None, top_k=10, min_value=None, ascending=False: (
                rank_edges(
                    results, available, result_ids, measure, window, top_k, min_value, ascending
                )
            ),
        ),
        (
            "compare_edges",
            compare_edges,
            lambda baseline_result_ids, treatment_result_ids, measure, window=None, edge_ids=(),
            top_k=10: compare_edges(
                results, available, baseline_result_ids, treatment_result_ids, measure, window,
                edge_ids, top_k,
            ),
        ),
        (
            "compare_kpis",
            compare_kpis,
            lambda baseline_result_ids, treatment_result_ids: compare_kpis(
                results, available, baseline_result_ids, treatment_result_ids
            ),
        ),
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
