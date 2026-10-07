"""Composer tools (E5.4): read-only and scoped to the study being composed."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

import pytest

from resto.adapters.persistence.memory import InMemoryResultRepository, InMemoryStudyRepository
from resto.application.ports.llm import Tool
from resto.application.schemas import adapter_for
from resto.application.tools.composer import build_composer_tools, composer_context
from resto.application.tools.results import NotAvailableError
from resto.domain.entities.study import Study
from tests.unit.adapters.llm._fakes import call_tool
from tests.unit.domain._samples import simulation_result as sample_result
from tests.unit.domain._samples import study as sample_study


class RecordingResultRepository(InMemoryResultRepository):
    def __init__(self) -> None:
        super().__init__()
        self.edgedata_calls: list[tuple[str, list[str], tuple[float, float] | None]] = []

    def query_edgedata(
        self, result_id: str, edge_ids: Iterable[str], window: tuple[float, float] | None
    ) -> Mapping[str, Any]:
        self.edgedata_calls.append((result_id, list(edge_ids), window))
        return {"A0A1": {"occupancy": 2.5}}


def _tools() -> tuple[tuple[Tool, ...], Study, RecordingResultRepository]:
    study = sample_study()  # st-1, experiments of results res0 and res1
    studies = InMemoryStudyRepository()
    studies.store(study)
    studies.store(replace(study, study_id="st-2"))
    results = RecordingResultRepository()
    results.store(sample_result())  # res1
    results.store(replace(sample_result(), result_id="res0"))
    results.store(replace(sample_result(), result_id="res9"))  # not in the study
    context = composer_context("st-1", studies=studies, results=results)
    return build_composer_tools(context), study, results


def test_tool_set_is_the_dod_list() -> None:
    tools, _, _ = _tools()
    assert [t.name for t in tools] == ["get_study", "get_result", "query_edgedata"]
    assert all(t.description and t.input_schema for t in tools)


def test_get_study_returns_the_study_being_composed() -> None:
    tools, study, _ = _tools()
    assert call_tool(tools, "get_study") == adapter_for(Study).dump_python(study, mode="json")


def test_get_study_refuses_another_study() -> None:
    tools, _, _ = _tools()
    with pytest.raises(NotAvailableError):
        call_tool(tools, "get_study", study_id="st-2")


def test_get_result_returns_a_result_of_the_study() -> None:
    tools, _, _ = _tools()
    got = call_tool(tools, "get_result", result_id="res1")
    assert (got["result_id"], got["scenario_id"], got["seed"]) == ("res1", "s1", 1)


def test_get_result_refuses_a_result_outside_the_study() -> None:
    tools, _, _ = _tools()
    with pytest.raises(NotAvailableError):
        call_tool(tools, "get_result", result_id="res9")


def test_query_edgedata_returns_the_edge_data_of_a_result_of_the_study() -> None:
    tools, _, results = _tools()
    got = call_tool(tools, "query_edgedata", result_id="res1", edge_ids=["A0A1"])
    assert got == {"A0A1": {"occupancy": 2.5}}
    assert results.edgedata_calls == [("res1", ["A0A1"], None)]


def test_query_edgedata_passes_the_window_to_the_repository() -> None:
    tools, _, results = _tools()
    call_tool(tools, "query_edgedata", result_id="res1", window=[28800, 29100])
    assert results.edgedata_calls == [("res1", [], (28800.0, 29100.0))]


def test_query_edgedata_refuses_a_window_that_is_not_a_pair() -> None:
    tools, _, results = _tools()
    with pytest.raises(ValueError, match="window"):
        call_tool(tools, "query_edgedata", result_id="res1", window=[1.0])
    assert results.edgedata_calls == []


def test_query_edgedata_refuses_a_result_outside_the_study() -> None:
    tools, _, results = _tools()
    with pytest.raises(NotAvailableError):
        call_tool(tools, "query_edgedata", result_id="res9")
    assert results.edgedata_calls == []


def test_query_edgedata_warns_about_its_size() -> None:
    tools, _, _ = _tools()
    description = next(t.description for t in tools if t.name == "query_edgedata")
    assert "last resort" in description


def test_a_study_that_is_not_stored_is_an_error() -> None:
    with pytest.raises(KeyError):
        composer_context(
            "nope", studies=InMemoryStudyRepository(), results=RecordingResultRepository()
        )
