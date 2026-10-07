"""Tools of the Output Composer as typed Python functions (DoD §2.4; offered in-process or via MCP).

Three read-only tools, all scoped to the study being composed: `get_study`, `get_result` and
`query_edgedata`. They depend on the `ResultRepository` port only. The
study's results are the allow-list: a result outside the study's experiments cannot be read, and
`get_study` takes no arguments.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from resto.application.ports.llm import Tool
from resto.application.ports.repositories import ResultRepository
from resto.application.schemas import adapter_for
from resto.application.tools.declaration import tool
from resto.application.tools.results import (
    EDGEDATA_COST,
    RESULT_DESCRIPTION,
    EdgeIdsOrAll,
    ResultId,
    Window,
    read_edgedata,
    read_result,
)
from resto.domain.entities.study import Study


@dataclass(frozen=True, slots=True)
class ComposerContext:
    """What the Composer's tools are bound to: the study being composed, the results repository
    and the result ids of that study's experiments. The first parameter (`ctx`) of every tool."""

    study: Study
    results: ResultRepository
    available: frozenset[str]


def composer_context(study: Study, *, results: ResultRepository) -> ComposerContext:
    """The context for composing `study`: its experiments' results are the allow-list."""
    available = frozenset(
        rid for phase in study.phases for e in phase.experiments for rid in e.result_ids
    )
    return ComposerContext(study=study, results=results, available=available)


@tool(
    name="get_study",
    description=(
        "The study being composed: its question, phases, experiments, Expert rounds and answers."
    ),
)
def get_study(ctx: ComposerContext) -> Mapping[str, Any]:
    """The study being composed."""
    return adapter_for(Study).dump_python(ctx.study, mode="json")


@tool(name="get_result", description=RESULT_DESCRIPTION)
def get_result(ctx: ComposerContext, result_id: ResultId) -> Mapping[str, Any]:
    """One simulation result of the study.

    Raises:
        NotAvailableError: `result_id` is not a result of this study.
        KeyError: no stored result has that id.
    """
    return read_result(ctx, result_id)


@tool(
    name="query_edgedata",
    description=f"{EDGEDATA_COST}use it only when the study and result summaries cannot answer.",
)
def query_edgedata(
    ctx: ComposerContext,
    result_id: ResultId,
    edge_ids: EdgeIdsOrAll = (),
    window: Window = None,
) -> Mapping[str, Any]:
    """EXPENSIVE raw per-run data of every edge of a result of the study.

    Raises:
        NotAvailableError: `result_id` is not a result of this study.
        ValueError: `window` is not a `[start, end]` pair.
    """
    return read_edgedata(ctx, result_id, edge_ids, window)


_COMPOSER_TOOLS = (get_study, get_result, query_edgedata)


def build_composer_tools(context: ComposerContext) -> tuple[Tool, ...]:
    """The Composer's tool set for the study of `context`."""
    return tuple(d.bind(context) for d in _COMPOSER_TOOLS)
