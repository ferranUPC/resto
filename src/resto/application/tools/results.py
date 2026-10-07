"""What the Expert and the Composer share when they read simulated results (DoD §2.2, §2.4).

Both read `get_result` and `query_edgedata` the same way; only the context that decides which
results may be read differs (the Expert's task allow-list, the Composer's study). The tools each
agent offers are declared in `expert.py` and `composer.py` with their own descriptions and delegate
here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Annotated, Any, Protocol

from pydantic import Field

from resto.application.ports.repositories import ResultRepository
from resto.application.schemas import adapter_for
from resto.domain.entities.simulation_result import SimulationResult


class NotAvailableError(LookupError):
    """The id exists (or may exist) but is not among what this question may use."""


class ResultsContext(Protocol):
    """A tool context that can read results: the repository and the ids it may read."""

    @property
    def results(self) -> ResultRepository: ...

    @property
    def available(self) -> AbstractSet[str]: ...


RESULT_DESCRIPTION = (
    "One simulation result: scenario_id, seed, status, KPIs and artifact references."
)
EDGEDATA_COST = (
    "EXPENSIVE raw per-run data of every edge (~17,000 characters per result), very large. "
    "A last resort: "
)
"""Start of the `query_edgedata` description of every agent; each adds when not to reach for it."""

ResultId = Annotated[str, Field(description="Id of an available simulation result.")]
EdgeIdsOrAll = Annotated[
    Sequence[str], Field(description="Edge ids to return; empty or omitted for every edge.")
]
Window = (
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


def require_available(available: AbstractSet[str], result_id: str) -> None:
    """Raises:
    NotAvailableError: `result_id` is not among the results the question may read.
    """
    if result_id not in available:
        raise NotAvailableError(
            f"result {result_id!r} is not among the results available to this question"
        )


def bounds(window: Sequence[float] | None) -> tuple[float, float] | None:
    """Raises:
    ValueError: `window` is not a `[start, end]` pair.
    """
    if window is None:
        return None
    if len(window) != 2:
        raise ValueError("window must be [start, end] in seconds since midnight")
    return float(window[0]), float(window[1])


def read_result(ctx: ResultsContext, result_id: str) -> Mapping[str, Any]:
    """One simulation result of those available.

    Raises:
        NotAvailableError: `result_id` is not available to this question.
        KeyError: no stored result has that id.
    """
    require_available(ctx.available, result_id)
    result = ctx.results.get(result_id)
    if result is None:
        raise KeyError(f"result {result_id!r} not found")
    return adapter_for(SimulationResult).dump_python(result, mode="json")


def read_edgedata(
    ctx: ResultsContext,
    result_id: str,
    edge_ids: Sequence[str],
    window: Sequence[float] | None,
) -> Mapping[str, Any]:
    """Per-edge measures of one available result over `[start, end)`, time of day in seconds
    since midnight (None: whole run). Empty `edge_ids` means every edge. Measures:
    sampled_seconds, density, occupancy, speed, waiting_time, time_loss, travel_time, entered,
    left (DATABASE_MCP_CONTRACT.md §5.4); waiting_time and time_loss are totals over all
    vehicles (vehicle-seconds).

    Raises:
        NotAvailableError: `result_id` is not available to this question.
        ValueError: `window` is not a `[start, end]` pair.
    """
    require_available(ctx.available, result_id)
    return ctx.results.query_edgedata(result_id, list(edge_ids), bounds(window))
