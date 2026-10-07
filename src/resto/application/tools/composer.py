"""Tools of the Output Composer as typed Python functions (DoD §2.4; offered in-process or via MCP).

Three read-only tools, all scoped to the study being composed: `get_study`, `get_result` and
`query_edgedata`. They depend on the `StudyRepository` and `ResultRepository` ports only. The
study's results are the allow-list: a result outside the study's experiments cannot be read, and
`get_study` refuses any study id but the one being composed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import Field

from resto.application.ports.llm import Tool
from resto.application.ports.repositories import ResultRepository, StudyRepository
from resto.application.schemas import adapter_for
from resto.application.tools.declaration import tool
from resto.application.tools.expert import NotAvailableError
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.entities.study import Study


@dataclass(frozen=True, slots=True)
class ComposerContext:
    """What the Composer's tools are bound to: the study being composed, the results repository
    and the result ids of that study's experiments. The first parameter (`ctx`) of every tool."""

    study: Study
    results: ResultRepository
    available: frozenset[str]

    def require_result(self, result_id: str) -> None:
        """Raises:
        NotAvailableError: `result_id` is not a result of an experiment of this study.
        """
        if result_id not in self.available:
            raise NotAvailableError(f"result {result_id!r} is not a result of this study")


def composer_context(
    study_id: str, *, studies: StudyRepository, results: ResultRepository
) -> ComposerContext:
    """The context for composing `study_id`.

    Raises:
        KeyError: no stored study has that id.
    """
    study = studies.get(study_id)
    if study is None:
        raise KeyError(f"study {study_id!r} not found")
    available = frozenset(
        rid for phase in study.phases for e in phase.experiments for rid in e.result_ids
    )
    return ComposerContext(study=study, results=results, available=available)


_ResultId = Annotated[str, Field(description="Id of a result of this study's experiments.")]


@tool(
    name="get_study",
    description=(
        "The study being composed: its question, phases, experiments, Expert rounds and answers."
    ),
)
def get_study(
    ctx: ComposerContext,
    study_id: Annotated[
        str | None, Field(description="Omit; only the study being composed can be read.")
    ] = None,
) -> Mapping[str, Any]:
    """The study being composed.

    Raises:
        NotAvailableError: `study_id` is given and is not the study being composed.
    """
    if study_id is not None and study_id != ctx.study.study_id:
        raise NotAvailableError(f"study {study_id!r} is not the study being composed")
    return adapter_for(Study).dump_python(ctx.study, mode="json")


@tool(
    name="get_result",
    description=(
        "One simulation result of this study: scenario_id, seed, status, KPIs and artifact "
        "references."
    ),
)
def get_result(ctx: ComposerContext, result_id: _ResultId) -> Mapping[str, Any]:
    """One simulation result of the study.

    Raises:
        NotAvailableError: `result_id` is not a result of this study.
        KeyError: no stored result has that id.
    """
    ctx.require_result(result_id)
    result = ctx.results.get(result_id)
    if result is None:
        raise KeyError(f"result {result_id!r} not found")
    return adapter_for(SimulationResult).dump_python(result, mode="json")


@tool(
    name="query_edgedata",
    description=(
        "EXPENSIVE raw per-run data of every edge (~17,000 characters per result), very large. "
        "A last resort: use it only when the study and result summaries cannot answer."
    ),
)
def query_edgedata(
    ctx: ComposerContext,
    result_id: _ResultId,
    edge_ids: Annotated[
        Sequence[str], Field(description="Edge ids to return; empty or omitted for every edge.")
    ] = (),
) -> Mapping[str, Any]:
    """EXPENSIVE raw per-run data of every edge of a result of the study, whole run.

    Raises:
        NotAvailableError: `result_id` is not a result of this study.
    """
    ctx.require_result(result_id)
    return ctx.results.query_edgedata(result_id, list(edge_ids), None)


_COMPOSER_TOOLS = (get_study, get_result, query_edgedata)


def build_composer_tools(context: ComposerContext) -> tuple[Tool, ...]:
    """The Composer's tool set for the study of `context`."""
    return tuple(d.bind(context) for d in _COMPOSER_TOOLS)
