"""NetworkMCP server (E1.1): protocol plumbing only, over the seven network tools.

Uses `MCPServer.call_tool` directly (no stdio subprocess) - enough to prove the server wires
`application/tools/network.py` correctly, per ADR-0009's "no logic beyond protocol plumbing".
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import UnexpectedToolError
from mcp.types import CallToolResult

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.network_query import NetworkQuery
from resto.interface.mcp.network_server import build_server


def _structured(result: object) -> Any:
    """`MCPServer.call_tool` is typed as `CallToolResult | InputRequiredResult`; these tests
    never elicit input, so narrow to the result's structured payload."""
    assert isinstance(result, CallToolResult)
    return result.structured_content

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"


@pytest.fixture(scope="module")
def query() -> SumolibNetworkQuery:
    return SumolibNetworkQuery(DEV_NET)


def test_build_server_registers_the_seven_network_tools(query: NetworkQuery) -> None:
    server = build_server(query)

    tools = asyncio.run(server.list_tools())

    assert {t.name for t in tools} == {
        "get_edge",
        "get_lanes",
        "get_neighbours",
        "shortest_path",
        "edges_in_bbox",
        "capacity_estimate",
        "get_tls",
    }


def test_build_server_derives_input_schemas_from_the_tool_signatures(
    query: NetworkQuery,
) -> None:
    server = build_server(query)

    tools = {t.name: t for t in asyncio.run(server.list_tools())}

    assert set(tools["shortest_path"].input_schema["properties"]) == {"from_edge", "to_edge"}
    assert set(tools["edges_in_bbox"].input_schema["properties"]) == {
        "xmin",
        "ymin",
        "xmax",
        "ymax",
    }


def test_build_server_call_tool_returns_the_network_query_result(query: NetworkQuery) -> None:
    server = build_server(query)

    result = asyncio.run(server.call_tool("get_edge", {"edge_id": "A0A1"}))

    # MCP results round-trip through JSON (tuples -> lists), so compare post-round-trip.
    assert _structured(result)["result"] == json.loads(json.dumps(query.get_edge("A0A1")))


def test_build_server_call_tool_unknown_id_is_reported_as_a_tool_error(
    query: NetworkQuery,
) -> None:
    server = build_server(query)

    with pytest.raises(UnexpectedToolError):
        asyncio.run(server.call_tool("get_edge", {"edge_id": "NOPE"}))
