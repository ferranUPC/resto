"""Network Expert tools (E4.1): exact tool set, the result allow-list, and the evidence ledger.

NetworkMCP correctness is covered by test_network.py/test_netxml.py; here the network tools only
need to prove they still reach the real DEV-NET through the ledger wrapper.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from resto.adapters.persistence.memory import InMemoryResultRepository, InMemoryScenarioRepository
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.llm import Tool
from resto.application.tools.expert import (
    EXPERT_NETWORK_TOOLS,
    RESULT_TOOLS,
    EvidenceLedger,
    NotAvailableError,
    build_expert_tools,
)
from resto.domain.entities.expert_note import ExpertNote
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask
from tests.unit.adapters.llm._fakes import call_tool
from tests.unit.domain._samples import expert_note as sample_note
from tests.unit.domain._samples import scenario as sample_scenario
from tests.unit.domain._samples import simulation_result as sample_result

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"


@pytest.fixture(scope="module")
def query() -> SumolibNetworkQuery:
    return SumolibNetworkQuery(DEV_NET)


class RecordingResultRepository(InMemoryResultRepository):
    """In-memory results whose `query_edgedata` records its arguments instead of parsing XML."""

    def __init__(self) -> None:
        super().__init__()
        self.edgedata_calls: list[tuple[str, list[str], tuple[float, float] | None]] = []

    def query_edgedata(
        self, result_id: str, edge_ids: Iterable[str], window: tuple[float, float] | None
    ) -> Mapping[str, Any]:
        self.edgedata_calls.append((result_id, list(edge_ids), window))
        return {"A0A1": {"occupancy": 2.5}}


class RecordingNoteRepository:
    def __init__(self) -> None:
        self.searches: list[tuple[str, str, Mapping[str, Any], int]] = []

    def store(self, note: ExpertNote) -> None:
        raise AssertionError("the Expert never stores notes through its tools")

    def search(
        self, query: str, network_id: str, filters: Mapping[str, Any], limit: int = 10
    ) -> Sequence[tuple[ExpertNote, float]]:
        self.searches.append((query, network_id, filters, limit))
        return [(sample_note(), 0.75)]

    def update_status(self, note_id: str, status: Any) -> None:
        raise AssertionError("not an Expert tool")


def _repositories() -> tuple[RecordingResultRepository, InMemoryScenarioRepository]:
    results = RecordingResultRepository()
    available = sample_result()  # res1, scenario s1
    results.store(available)
    results.store(replace(available, result_id="res2", seed=2))  # same scenario, held out
    results.store(replace(available, result_id="res3", scenario_id="s2"))  # held out
    scenarios = InMemoryScenarioRepository()
    scenarios.store(sample_scenario())  # s1
    scenarios.store(replace(sample_scenario(), scenario_id="s2"))
    return results, scenarios


def _tools(
    query: SumolibNetworkQuery,
    *,
    result_ids: tuple[str, ...] = ("res1",),
    notes_allowed: bool = False,
    notes: RecordingNoteRepository | None = None,
) -> tuple[tuple[Tool, ...], EvidenceLedger, RecordingResultRepository]:
    results, scenarios = _repositories()
    ledger = EvidenceLedger()
    task = ExpertTask(
        question="which edges are congested?",
        mode=Mode.FORCED,
        network_id="abc123",
        result_ids=result_ids,
        notes_allowed=notes_allowed,
    )
    tools = build_expert_tools(
        task=task, query=query, results=results, scenarios=scenarios, notes=notes, ledger=ledger
    )
    return tools, ledger, results


def test_tool_set_is_the_dod_list_plus_get_scenario(query: SumolibNetworkQuery) -> None:
    tools, _, _ = _tools(query)
    assert [t.name for t in tools] == [*EXPERT_NETWORK_TOOLS, *RESULT_TOOLS]
    assert all(t.description and t.input_schema for t in tools)


def test_search_notes_is_offered_only_when_notes_are_allowed(query: SumolibNetworkQuery) -> None:
    tools, _, _ = _tools(query, notes_allowed=True, notes=RecordingNoteRepository())
    assert [t.name for t in tools][-1] == "search_notes"


def test_notes_allowed_without_a_note_repository_is_an_error(query: SumolibNetworkQuery) -> None:
    with pytest.raises(ValueError, match="NoteRepository"):
        _tools(query, notes_allowed=True, notes=None)


def test_network_tool_reaches_the_real_network_and_is_recorded(
    query: SumolibNetworkQuery,
) -> None:
    tools, ledger, _ = _tools(query)
    response = call_tool(tools, "get_edge", edge_id="A0A1")
    assert response == {"ref": "q1", "result": query.get_edge("A0A1")}
    entry = ledger.get("q1")
    assert entry is not None
    assert (entry.tool, entry.arguments) == ("get_edge", {"edge_id": "A0A1"})


def test_refs_increment_per_successful_call(query: SumolibNetworkQuery) -> None:
    tools, ledger, _ = _tools(query)
    call_tool(tools, "get_neighbours", edge_id="A0A1")
    response = call_tool(tools, "get_result", result_id="res1")
    assert response["ref"] == "q2"
    assert [e.ref for e in ledger.entries] == ["q1", "q2"]


def test_failed_calls_are_not_recorded(query: SumolibNetworkQuery) -> None:
    tools, ledger, _ = _tools(query)
    with pytest.raises(KeyError):
        call_tool(tools, "get_edge", edge_id="nope")
    assert ledger.entries == ()


def test_get_result_returns_the_result_as_json(query: SumolibNetworkQuery) -> None:
    tools, _, _ = _tools(query)
    result = call_tool(tools, "get_result", result_id="res1")["result"]
    assert result["result_id"] == "res1"
    assert result["kpis"]["mean_delay"] == 42.0
    assert result["status"] == "ok"


@pytest.mark.parametrize("result_id", ["res2", "res3", "missing"])
def test_results_outside_the_allow_list_cannot_be_read(
    query: SumolibNetworkQuery, result_id: str
) -> None:
    tools, ledger, results = _tools(query)
    with pytest.raises(NotAvailableError):
        call_tool(tools, "get_result", result_id=result_id)
    with pytest.raises(NotAvailableError):
        call_tool(tools, "query_edgedata", result_id=result_id)
    assert results.edgedata_calls == []
    assert ledger.entries == ()


def test_empty_result_ids_means_no_simulated_evidence(query: SumolibNetworkQuery) -> None:
    tools, _, _ = _tools(query, result_ids=())
    with pytest.raises(NotAvailableError):
        call_tool(tools, "get_result", result_id="res1")
    assert call_tool(tools, "list_results", scenario_id="s1")["result"] == []


def test_list_results_only_lists_available_results(query: SumolibNetworkQuery) -> None:
    tools, _, _ = _tools(query)
    listed = call_tool(tools, "list_results", scenario_id="s1")["result"]
    assert [r["result_id"] for r in listed] == ["res1"]


def test_query_edgedata_delegates_with_a_window_tuple(query: SumolibNetworkQuery) -> None:
    tools, _, results = _tools(query)
    response = call_tool(
        tools, "query_edgedata", result_id="res1", edge_ids=["A0A1"], window=[0, 300]
    )
    assert response["result"] == {"A0A1": {"occupancy": 2.5}}
    assert results.edgedata_calls == [("res1", ["A0A1"], (0.0, 300.0))]


def test_query_edgedata_defaults_to_every_edge_over_the_whole_run(
    query: SumolibNetworkQuery,
) -> None:
    tools, _, results = _tools(query)
    call_tool(tools, "query_edgedata", result_id="res1")
    assert results.edgedata_calls == [("res1", [], None)]


def test_query_edgedata_rejects_a_malformed_window(query: SumolibNetworkQuery) -> None:
    tools, _, _ = _tools(query)
    with pytest.raises(ValueError, match="window"):
        call_tool(tools, "query_edgedata", result_id="res1", window=[0])


def test_get_scenario_only_reaches_scenarios_of_available_results(
    query: SumolibNetworkQuery,
) -> None:
    tools, _, _ = _tools(query)
    scenario = call_tool(tools, "get_scenario", scenario_id="s1")["result"]
    assert scenario["scenario_id"] == "s1"
    assert scenario["interventions"][0]["type"] == "lane_closure"
    with pytest.raises(NotAvailableError):
        call_tool(tools, "get_scenario", scenario_id="s2")


def test_ledger_exposes_artifacts_returned_by_result_tools(query: SumolibNetworkQuery) -> None:
    tools, ledger, _ = _tools(query)
    assert ledger.artifact_ids() == frozenset()
    call_tool(tools, "get_result", result_id="res1")
    assert {"edgedata.xml", "ed1"} <= ledger.artifact_ids()


def test_search_notes_is_scoped_to_the_task_network(query: SumolibNetworkQuery) -> None:
    notes = RecordingNoteRepository()
    tools, _, _ = _tools(query, notes_allowed=True, notes=notes)
    response = call_tool(tools, "search_notes", query="E12 at peak")
    assert notes.searches == [("E12 at peak", "abc123", {}, 10)]
    assert response["result"][0]["score"] == 0.75
    assert response["result"][0]["note"]["note_id"] == "n-1"
