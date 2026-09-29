"""Tools of the Network Expert agent as typed Python functions (DoD §2.2; ADR-0011, ADR-0018).

Facts reach the Expert only through these: topology via `get_lanes`/`shortest_path` (the
NetworkMCP functions of `application/tools/network.py`, unchanged) plus `get_edges`,
`get_neighbours`, `capacity_estimate` and `get_tls`, Expert-only wrappers over the same
`NetworkQuery` port that take a list of ids instead of one (v2: describing a neighbourhood of
several edges was costing one tool call per edge per NetworkMCP's singular contract, which starved
`-diag` questions of turns before they could describe a whole neighbourhood — see
docs/expert-tuning-log.md). Simulated data reaches it via the `ResultRepository`/
`ScenarioRepository` ports (never by parsing an artifact file), and earlier interpretations via
`search_notes`.

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
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from resto.application.ports.llm import Tool
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import (
    NetworkRepository,
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.schemas import adapter_for
from resto.application.tools.declaration import tool
from resto.application.tools.network import get_lanes, shortest_path
from resto.domain.entities.expert_note import ExpertNote
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.value_objects.tasks import ExpertTask

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


@dataclass(frozen=True, slots=True)
class ExpertContext:
    """What the Expert's tools are bound to for one task: the network, the repositories, the ids
    this task may read and the network it asks about. The first parameter (`ctx`) of every tool
    below; the model never sees it."""

    query: NetworkQuery
    results: ResultRepository
    scenarios: ScenarioRepository
    notes: NoteRepository | None
    network_id: str
    available: frozenset[str]
    available_scenarios: frozenset[str]
    notes_allowed: bool


def expert_context(
    task: ExpertTask,
    *,
    query: NetworkQuery,
    results: ResultRepository,
    scenarios: ScenarioRepository,
    notes: NoteRepository | None,
) -> ExpertContext:
    """The context of one task: `task.result_ids` is the allow-list, and the scenarios available
    are the ones those results belong to.

    Raises:
        ValueError: `task.notes_allowed` but no `notes` repository was given.
    """
    if task.notes_allowed and notes is None:
        raise ValueError("notes_allowed requires a NoteRepository")
    available = frozenset(task.result_ids)
    return ExpertContext(
        query=query,
        results=results,
        scenarios=scenarios,
        notes=notes,
        network_id=task.network_id,
        available=available,
        available_scenarios=frozenset(
            r.scenario_id for r in (results.get(rid) for rid in available) if r is not None
        ),
        notes_allowed=task.notes_allowed,
    )


@dataclass(frozen=True, slots=True)
class ExpertCollaborators:
    """Everything the Expert needs that does not depend on the task: the repositories and the
    query factory. Built once in the composition root; a new collaborator is one more field."""

    networks: NetworkRepository
    results: ResultRepository
    scenarios: ScenarioRepository
    notes: NoteRepository | None
    network_query_factory: Callable[[Path], NetworkQuery]


_EdgeIds = Annotated[
    Sequence[str], Field(min_length=1, description="Edge ids, e.g. ['A0A1', 'A1A2'].")
]
_TlsIds = Annotated[Sequence[str], Field(min_length=1, description="Traffic light ids.")]
_ResultId = Annotated[str, Field(description="Id of an available simulation result.")]
_ResultIds = Annotated[Sequence[str], Field(min_length=1)]
_Measure = Annotated[str, Field(json_schema_extra={"enum": list(EDGE_MEASURES)})]
_TopK = Annotated[int, Field(ge=1)]
_Window = (
    Annotated[
        Sequence[float],
        Field(
            min_length=2,
            max_length=2,
            description=(
                "[start, end) as time of day in seconds since midnight (08:00-08:05 is "
                "[28800, 29100]); omit for the whole run."
            ),
        ),
    ]
    | None
)


@tool(
    name="get_edges",
    description=(
        "Attributes of several edges in one call: endpoints, length, speed, lane count, priority,"
    ),
)
def get_edges(ctx: ExpertContext, edge_ids: _EdgeIds) -> Mapping[str, Any]:
    """Attributes of several edges in one call: endpoints, length, speed, lane count, priority,
    shape.

    Raises:
        KeyError: an edge_id does not exist on this network.
    """
    if not edge_ids:
        raise ValueError("give at least one edge_id")
    return {edge_id: ctx.query.get_edge(edge_id) for edge_id in edge_ids}


@tool(
    name="get_neighbours",
    description=(
        "Ids of the edges reachable in one hop downstream of each edge (outgoing connections), one"
    ),
)
def get_neighbours(ctx: ExpertContext, edge_ids: _EdgeIds) -> Mapping[str, Any]:
    """Ids of the edges reachable in one hop downstream of each edge (outgoing connections), one
    call for several edges.

    Raises:
        KeyError: an edge_id does not exist on this network.
    """
    if not edge_ids:
        raise ValueError("give at least one edge_id")
    return {edge_id: ctx.query.get_neighbours(edge_id) for edge_id in edge_ids}


@tool(
    name="capacity_estimate",
    description=(
        "Rough capacity of several edges in veh/h (Greenshields estimate — ADR-0015; "
        "order-of-"
    ),
)
def capacity_estimate(ctx: ExpertContext, edge_ids: _EdgeIds) -> Mapping[str, Any]:
    """Rough capacity of several edges in veh/h (Greenshields estimate — ADR-0015; order-of-
    magnitude only, not a substitute for a simulated result), one call for several edges.

    Raises:
        KeyError: an edge_id does not exist on this network.
    """
    if not edge_ids:
        raise ValueError("give at least one edge_id")
    return {edge_id: ctx.query.capacity_estimate(edge_id) for edge_id in edge_ids}


@tool(
    name="get_tls",
    description="Controlled edges and signal programs of several traffic lights in one call.",
)
def get_tls(ctx: ExpertContext, tls_ids: _TlsIds) -> Mapping[str, Any]:
    """Controlled edges and signal programs of several traffic lights in one call.

    Raises:
        KeyError: a tls_id does not exist on this network.
    """
    if not tls_ids:
        raise ValueError("give at least one tls_id")
    return {tls_id: ctx.query.get_tls(tls_id) for tls_id in tls_ids}


@tool(
    name="get_result",
    description=(
        "One simulation result: scenario_id, seed, status, KPIs and artifact references."
    ),
)
def get_result(ctx: ExpertContext, result_id: _ResultId) -> Mapping[str, Any]:
    """One simulation result: scenario_id, seed, status, KPIs and artifact references.

    Raises:
        NotAvailableError: `result_id` is not available to this question.
        KeyError: no stored result has that id.
    """
    _require_available(ctx.available, result_id)
    result = ctx.results.get(result_id)
    if result is None:
        raise KeyError(f"result {result_id!r} not found")
    return adapter_for(SimulationResult).dump_python(result, mode="json")


@tool(
    name="list_results",
    description=(
        "The available results of one scenario (one per seed), empty if none is available."
    ),
)
def list_results(ctx: ExpertContext, scenario_id: str) -> list[Mapping[str, Any]]:
    """The available results of one scenario (one per seed), empty if none is available."""
    adapter = adapter_for(SimulationResult)
    return [
        adapter.dump_python(r, mode="json")
        for r in ctx.results.list(scenario_id)
        if r.result_id in ctx.available
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


def _bounds(window: Sequence[float] | None) -> tuple[float, float] | None:
    if window is None:
        return None
    if len(window) != 2:
        raise ValueError("window must be [start, end] in seconds since midnight")
    return float(window[0]), float(window[1])


def _per_run(
    ctx: ExpertContext,
    result_ids: Sequence[str],
    edge_ids: Sequence[str],
    window: Sequence[float] | None,
) -> list[Mapping[str, Mapping[str, float]]]:
    if not result_ids:
        raise ValueError("give at least one result_id")
    for result_id in result_ids:
        _require_available(ctx.available, result_id)
    bounds = _bounds(window)
    return [ctx.results.query_edgedata(rid, list(edge_ids), bounds) for rid in result_ids]


def _edge_summary(
    runs: Sequence[Mapping[str, Mapping[str, float]]], edge_id: str, measure: str
) -> dict[str, float | int] | None:
    return _summary([_run_value(run[edge_id], measure) for run in runs if edge_id in run])


@tool(
    name="edge_stats",
    description=(
        "Mean, std and run count of every measure on the given edges, across the given runs."
    ),
)
def edge_stats(
    ctx: ExpertContext,
    result_ids: _ResultIds,
    edge_ids: Annotated[Sequence[str], Field(min_length=1)],
    window: _Window = None,
) -> Mapping[str, Any]:
    """Mean, std and run count of every measure on the given edges, across the given runs.

    Per-vehicle means (travel_time, speed, time_loss_per_vehicle) only count runs where the edge
    had traffic, and are null when none had: a null travel time means no vehicle crossed the edge.

    Raises:
        NotAvailableError: a result is not available to this question.
    """
    if not edge_ids:
        raise ValueError("name the edges; use rank_edges to search the whole network")
    runs = _per_run(ctx, result_ids, edge_ids, window)
    return {
        edge_id: {measure: _edge_summary(runs, edge_id, measure) for measure in EDGE_MEASURES}
        for edge_id in edge_ids
        if any(edge_id in run for run in runs)
    }


@tool(
    name="rank_edges",
    description=(
        "Edges of the whole network ranked by the mean of one measure across the given runs."
    ),
)
def rank_edges(
    ctx: ExpertContext,
    result_ids: _ResultIds,
    measure: _Measure,
    window: _Window = None,
    top_k: _TopK = 10,
    min_value: float | None = None,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    """Edges of the whole network ranked by the mean of one measure across the given runs.

    With `min_value`, only edges whose mean exceeds it. Edges where a per-vehicle mean is undefined
    in every run are left out.
    """
    _check_measure(measure)
    runs = _per_run(ctx, result_ids, (), window)
    rows: list[dict[str, Any]] = []
    for edge_id in runs[0]:
        summary = _edge_summary(runs, edge_id, measure)
        if summary is None or (min_value is not None and summary["mean"] <= min_value):
            continue
        rows.append({"edge_id": edge_id, **summary})
    rows.sort(key=lambda row: row["mean"], reverse=not ascending)
    return rows[:top_k]


@tool(
    name="compare_edges",
    description=(
        "Per edge, the mean of one measure in baseline and treatment runs, the difference and the"
    ),
)
def compare_edges(
    ctx: ExpertContext,
    baseline_result_ids: _ResultIds,
    treatment_result_ids: _ResultIds,
    measure: _Measure,
    window: _Window = None,
    edge_ids: Sequence[str] = (),
    top_k: _TopK = 10,
) -> list[dict[str, Any]]:
    """Per edge, the mean of one measure in baseline and treatment runs, the difference and the
    relative change in percent. With `edge_ids`, exactly those edges; otherwise the `top_k` edges
    with the largest absolute difference."""
    _check_measure(measure)
    baseline = _per_run(ctx, baseline_result_ids, edge_ids, window)
    treatment = _per_run(ctx, treatment_result_ids, edge_ids, window)
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


@tool(
    name="compare_kpis",
    description=(
        "Network-wide KPIs (mean_delay, mean_travel_time, teleports, departed, arrived): "
        "mean across"
    ),
)
def compare_kpis(
    ctx: ExpertContext, baseline_result_ids: _ResultIds, treatment_result_ids: _ResultIds
) -> Mapping[str, Any]:
    """Network-wide KPIs (mean_delay, mean_travel_time, teleports, departed, arrived): mean across
    baseline and treatment runs, the difference and the relative change in percent."""

    def kpis(result_ids: Sequence[str]) -> dict[str, dict[str, float | int] | None]:
        if not result_ids:
            raise ValueError("give at least one result_id per side")
        values: dict[str, list[float | None]] = {name: [] for name in KPI_NAMES}
        for result_id in result_ids:
            _require_available(ctx.available, result_id)
            result = ctx.results.get(result_id)
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


@tool(
    name="query_edgedata",
    description=(
        "EXPENSIVE raw per-run data of every edge (~17,000 characters per result): "
        "prefer edge_stats,"
    ),
)
def query_edgedata(
    ctx: ExpertContext,
    result_id: _ResultId,
    edge_ids: Annotated[
        Sequence[str], Field(description="Edge ids to return; empty or omitted for every edge.")
    ] = (),
    window: _Window = None,
) -> Mapping[str, Any]:
    """EXPENSIVE raw per-run data of every edge (~17,000 characters per result): prefer edge_stats,
    rank_edges or compare_edges, and use this only when they cannot express what you need.

    Per-edge measures of one result over `[start, end)`, time of day in seconds since midnight
    (None: whole run).
    Empty `edge_ids` means every edge. Measures: sampled_seconds, density, occupancy, speed,
    waiting_time, time_loss, travel_time, entered, left (DATABASE_MCP_CONTRACT.md §5.4);
    waiting_time and time_loss are totals over all vehicles (vehicle-seconds).

    Raises:
        NotAvailableError: `result_id` is not available to this question.
        ValueError: `window` is not a `[start, end]` pair.
    """
    _require_available(ctx.available, result_id)
    bounds = _bounds(window)
    return ctx.results.query_edgedata(result_id, list(edge_ids), bounds)


@tool(
    name="get_scenario",
    description=(
        "The scenario an available result was run on: its interventions and context tags - how"
    ),
)
def get_scenario(ctx: ExpertContext, scenario_id: str) -> Mapping[str, Any]:
    """The scenario an available result was run on: its interventions and context tags - how
    to tell a baseline result from an intervention one.

    Raises:
        NotAvailableError: no available result belongs to `scenario_id`.
        KeyError: no stored scenario has that id.
    """
    if scenario_id not in ctx.available_scenarios:
        raise NotAvailableError(
            f"scenario {scenario_id!r} has no result available to this question"
        )
    scenario = ctx.scenarios.get(scenario_id)
    if scenario is None:
        raise KeyError(f"scenario {scenario_id!r} not found")
    return adapter_for(Scenario).dump_python(scenario, mode="json")


@tool(
    name="search_notes",
    description=(
        "Earlier notes on this network ranked by relevance to `query`, each with its score."
    ),
)
def search_notes(
    ctx: ExpertContext,
    query: Annotated[str, Field(description="What you are looking for, in prose.")],
    filters: Annotated[
        Mapping[str, Any],
        Field(description="Optional: status, basis, provenance, scenario_id, context_tags."),
    ]
    | None = None,
    limit: _TopK = 10,
) -> list[Mapping[str, Any]]:
    """Earlier notes on this network ranked by relevance to `query`, each with its score.
    Filters: status, basis, provenance, scenario_id, context_tags."""
    assert ctx.notes is not None, "search_notes is only offered with a NoteRepository"
    adapter = adapter_for(ExpertNote)
    return [
        {"note": adapter.dump_python(note, mode="json"), "score": score}
        for note, score in ctx.notes.search(query, ctx.network_id, filters or {}, limit)
    ]


# What the Expert is offered, in the order it is offered. The network tools are the NetworkMCP
# declarations bound to `ctx.query`; the rest are bound to the whole context.
_NETWORK_TOOLS = (get_lanes, shortest_path)
_EXPERT_TOOLS = (
    get_edges,
    get_neighbours,
    capacity_estimate,
    get_tls,
    edge_stats,
    rank_edges,
    compare_edges,
    compare_kpis,
    get_result,
    list_results,
    query_edgedata,
    get_scenario,
)
EXPERT_TOOL_NAMES = tuple(d.name for d in (*_NETWORK_TOOLS, *_EXPERT_TOOLS))


def _recorded(ledger: EvidenceLedger, bound: Tool) -> Tool:
    def call(**kwargs: Any) -> Mapping[str, Any]:
        result = bound.fn(**kwargs)
        return {"ref": ledger.record(bound.name, kwargs, result), "result": result}

    return Tool(
        name=bound.name,
        description=bound.description,
        fn=call,
        input_schema=bound.input_schema,
    )


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
    ctx = expert_context(task, query=query, results=results, scenarios=scenarios, notes=notes)
    tools = [d.bind(ctx.query) for d in _NETWORK_TOOLS]
    tools.extend(d.bind(ctx) for d in _EXPERT_TOOLS)
    if ctx.notes_allowed:
        tools.append(search_notes.bind(ctx))
    return tuple(_recorded(ledger, t) for t in tools)
