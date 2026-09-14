"""DatabaseMCP server (E1.3): protocol plumbing and error-code translation only - the underlying
logic (idempotency, scoring, aggregation, ranking) is already covered against
`tests/unit/adapters/persistence/sqlite/test_repositories.py`.
"""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Iterator

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.application.schemas import ADAPTERS
from resto.interface.mcp.database_server import build_server
from tests.unit.domain._samples import expert_note, network, scenario


@pytest.fixture
def db() -> Iterator[SqliteDatabase]:
    database = SqliteDatabase(":memory:")
    yield database
    database.close()


def test_build_server_registers_the_seventeen_required_tools(db: SqliteDatabase) -> None:
    server = build_server(db)

    tools = {t.name for t in asyncio.run(server.list_tools())}

    assert tools == {
        "store_network",
        "get_network",
        "list_networks",
        "find_network",
        "store_demand",
        "get_demand",
        "list_demands",
        "store_scenario",
        "get_scenario",
        "find_similar_scenario",
        "store_result",
        "get_result",
        "list_results",
        "query_edgedata",
        "store_note",
        "search_notes",
        "update_note_status",
    }


def test_store_then_get_network_round_trips_over_the_wire(db: SqliteDatabase) -> None:
    server = build_server(db)
    net = network()
    payload = ADAPTERS["Network"].dump_python(net, mode="json")

    store_result = asyncio.run(server.call_tool("store_network", {"network_data": payload}))
    get_result = asyncio.run(server.call_tool("get_network", {"network_id": net.network_id}))

    # a dict[str, str] return is used directly as structured_content; dict[str, Any] | None
    # (get_network's return type) is not representable as top-level object properties, so
    # mcp.server.mcpserver wraps it in {"result": ...} instead - both verified empirically.
    assert store_result.structured_content == {"network_id": net.network_id}
    assert get_result.structured_content["result"]["label"] == net.label


def test_get_network_unknown_id_returns_null_not_a_tool_error(db: SqliteDatabase) -> None:
    server = build_server(db)

    result = asyncio.run(server.call_tool("get_network", {"network_id": "nope"}))

    assert result.structured_content["result"] is None


def test_store_network_conflict_is_reported_with_the_conflict_code(db: SqliteDatabase) -> None:
    server = build_server(db)
    net = network()
    payload = ADAPTERS["Network"].dump_python(net, mode="json")
    asyncio.run(server.call_tool("store_network", {"network_data": payload}))

    changed = dict(payload)
    changed["probe_report"] = None

    with pytest.raises(ToolError, match="CONFLICT"):
        asyncio.run(server.call_tool("store_network", {"network_data": changed}))


def test_update_note_status_unknown_id_is_reported_with_the_not_found_code(
    db: SqliteDatabase,
) -> None:
    server = build_server(db)

    with pytest.raises(ToolError, match="NOT_FOUND"):
        asyncio.run(
            server.call_tool("update_note_status", {"note_id": "nope", "status": "confirmed"})
        )


def test_search_notes_unknown_filter_is_reported_with_the_invalid_argument_code(
    db: SqliteDatabase,
) -> None:
    server = build_server(db)

    with pytest.raises(ToolError, match="INVALID_ARGUMENT"):
        asyncio.run(
            server.call_tool(
                "search_notes",
                {
                    "query": "q",
                    "network_id": "abc123",
                    "filters": {"nonexistent": ["x"]},
                },
            )
        )


def test_find_similar_scenario_returns_scored_results_over_the_wire(db: SqliteDatabase) -> None:
    server = build_server(db)
    s = scenario()
    payload = ADAPTERS["Scenario"].dump_python(s, mode="json")
    asyncio.run(server.call_tool("store_scenario", {"scenario_data": payload}))

    result = asyncio.run(
        server.call_tool(
            "find_similar_scenario",
            {
                "network_id": s.network_id,
                "demand_id": s.demand_id,
                "interventions": payload["interventions"],
                "context_tags": list(s.context_tags),
            },
        )
    )

    [match] = result.structured_content["result"]
    assert match["scenario"]["scenario_id"] == s.scenario_id
    assert match["score"] == 1.0


def test_search_notes_returns_scored_results_over_the_wire(db: SqliteDatabase) -> None:
    server = build_server(db)
    note = dataclasses.replace(expert_note(), text="B0C0 saturates at peak")
    payload = ADAPTERS["ExpertNote"].dump_python(note, mode="json")
    asyncio.run(server.call_tool("store_note", {"note_data": payload}))

    result = asyncio.run(
        server.call_tool(
            "search_notes", {"query": "B0C0 saturates", "network_id": note.network_id}
        )
    )

    [match] = result.structured_content["result"]
    assert match["note"]["note_id"] == note.note_id
    assert match["score"] > 0
