"""`mcp_client.py` (E1.5): the adapter's own plumbing - unwrapping structured tool output,
translating the server's `"CODE: detail"` error text back into the right `RepositoryError`
subclass, and round-tripping every aggregate through a real MCP session (`InMemoryTransport`, no
subprocess). The underlying contract behaviour (idempotency, scoring, ranking, aggregation) is
already covered against the SQLite backend directly and re-verified backend-agnostically by
`conformance/` - this file only has to prove the wire plumbing itself is correct.
"""

from __future__ import annotations

import dataclasses
import time
from collections.abc import Iterator
from typing import Any

import pytest
from mcp.client._memory import InMemoryTransport
from mcp.server.mcpserver import MCPServer
from mcp.types import TextContent

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.application.ports.errors import ConflictError, InvalidArgumentError, NotFoundError
from resto.application.schemas import ADAPTERS
from resto.domain.entities.expert_note import NoteStatus
from resto.interface.mcp.database_server import build_server
from tests.unit.domain._samples import expert_note, network, scenario


@pytest.fixture
def backend() -> Iterator[SqliteDatabase]:
    db = SqliteDatabase(":memory:")
    yield db
    db.close()


@pytest.fixture
def client(backend: SqliteDatabase) -> Iterator[McpClientDatabase]:
    server = build_server(backend)
    db = McpClientDatabase(lambda: InMemoryTransport(server))
    yield db
    db.close()


def test_tool_names_lists_every_registered_tool(client: McpClientDatabase) -> None:
    assert "find_similar_scenario" in client.tool_names()
    assert "search_notes" in client.tool_names()
    assert "query_edgedata" in client.tool_names()
    assert len(client.tool_names()) == 17


def test_store_then_get_network_round_trips_over_real_mcp(client: McpClientDatabase) -> None:
    net = network()

    client.networks.store(net)
    found = client.networks.get(net.network_id)

    assert found == net


def test_get_network_unknown_id_returns_none_not_an_exception(client: McpClientDatabase) -> None:
    assert client.networks.get("nope") is None


def test_list_networks_unwraps_the_wrapped_list_result(client: McpClientDatabase) -> None:
    net = network()
    client.networks.store(net)

    assert client.networks.list() == [net]


def test_store_network_conflict_raises_conflict_error(client: McpClientDatabase) -> None:
    net = network()
    client.networks.store(net)
    changed = dataclasses.replace(net, probe_report=None)

    with pytest.raises(ConflictError):
        client.networks.store(changed)


def test_update_note_status_unknown_id_raises_not_found(client: McpClientDatabase) -> None:
    with pytest.raises(NotFoundError):
        client.notes.update_status("nope", NoteStatus.CONFIRMED)


def test_search_notes_unknown_filter_raises_invalid_argument(client: McpClientDatabase) -> None:
    note = expert_note()
    client.notes.store(note)

    with pytest.raises(InvalidArgumentError):
        client.notes.search("q", note.network_id, {"nonexistent": ["x"]})


def test_find_similar_scenario_round_trips_scored_pairs(client: McpClientDatabase) -> None:
    s = scenario()
    client.scenarios.store(s)

    [(found, score)] = client.scenarios.find_similar(
        s.network_id, s.demand_id, s.interventions, s.context_tags
    )

    assert found == s
    assert score == 1.0


def test_query_edgedata_of_a_result_without_edgedata_returns_empty(
    client: McpClientDatabase, backend: SqliteDatabase
) -> None:
    from tests.unit.domain._samples import simulation_result

    result = dataclasses.replace(simulation_result(), artifacts=())
    client.results.store(result)

    assert client.results.query_edgedata(result.result_id, [], None) == {}


def test_query_edgedata_of_an_unknown_result_raises_not_found(client: McpClientDatabase) -> None:
    with pytest.raises(NotFoundError):
        client.results.query_edgedata("nope", [], None)


def test_store_note_then_search_notes_round_trips_over_real_mcp(
    client: McpClientDatabase,
) -> None:
    note = dataclasses.replace(expert_note(), text="E12 saturates at peak")
    client.notes.store(note)

    [(found, score)] = client.notes.search(note.text, note.network_id, {})

    assert found == note
    assert score == pytest.approx(1.0)


def test_client_reads_the_same_data_the_server_side_backend_holds(
    client: McpClientDatabase, backend: SqliteDatabase
) -> None:
    net = network()
    client.networks.store(net)

    stored_directly = backend.networks.get(net.network_id)

    assert stored_directly == net
    assert ADAPTERS["Network"].dump_python(stored_directly) == ADAPTERS["Network"].dump_python(
        net
    )


# --- plumbing failure modes: errors, never hangs -------------------------------------------


def _server_with(fn: Any, name: str) -> MCPServer:
    server = MCPServer("stub")
    server.add_tool(fn, name=name, description=name)
    return server


@pytest.fixture
def client_factory() -> Any:
    def make(fn: Any, name: str, **kwargs: Any) -> McpClientDatabase:
        return McpClientDatabase(lambda: InMemoryTransport(_server_with(fn, name)), **kwargs)

    return make


def test_call_that_exceeds_timeout_raises_timeout_error_instead_of_hanging(
    client_factory: Any,
) -> None:
    def slow() -> dict[str, str]:
        time.sleep(0.5)
        return {"ok": "late"}

    with (
        client_factory(slow, "slow", timeout=0.05) as client,
        pytest.raises(TimeoutError, match="slow"),
    ):
        client.call_tool("slow", {})


def test_call_after_close_raises_connection_error_instead_of_hanging(
    client: McpClientDatabase,
) -> None:
    client.close()

    with pytest.raises(ConnectionError):
        client.networks.get("anything")


def test_close_is_idempotent(client: McpClientDatabase) -> None:
    client.close()
    client.close()


def test_failed_connection_raises_from_the_constructor() -> None:
    def broken() -> Any:
        raise OSError("no server here")

    with pytest.raises(OSError, match="no server here"):
        McpClientDatabase(broken)


def test_unstructured_json_text_result_is_parsed(client_factory: Any) -> None:
    # A tool returning content blocks publishes no output schema and no structuredContent - the
    # shape a non-Python backend may well produce (contract §2: the JSON goes in the text block).
    def blocks() -> list[TextContent]:
        return [TextContent(type="text", text='["a", "b"]')]

    with client_factory(blocks, "blocks") as client:
        assert client.call_tool("blocks", {}) == ["a", "b"]


def test_unstructured_non_json_text_result_is_an_error_not_a_silent_value(
    client_factory: Any,
) -> None:
    def raw():  # type: ignore[no-untyped-def]  # untyped on purpose: the SDK emits bare text
        return ["a", "b"]

    with client_factory(raw, "raw") as client, pytest.raises(RuntimeError, match="raw"):
        client.call_tool("raw", {})
