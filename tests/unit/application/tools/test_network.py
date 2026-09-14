"""NetworkMCP tool functions (E1.1): delegation to NetworkQuery and Tool wrapping.

sumolib-backed correctness (geometry, shortest path, capacity formula, ...) is already covered by
tests/unit/adapters/sumo/test_netxml.py; these tests cover what's new at this layer instead: that
each function delegates its arguments unchanged, that `edges_in_bbox` packs its four scalar
LLM-facing args into the bbox tuple the port expects, and that `build_network_tools` produces
seven correctly named/shaped `Tool`s whose `fn` still raises on an unknown id.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.network_query import NetworkQuery
from resto.application.tools.network import (
    build_network_tools,
    capacity_estimate,
    edges_in_bbox,
    get_edge,
    get_lanes,
    get_neighbours,
    get_tls,
    shortest_path,
)

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"


@pytest.fixture(scope="module")
def query() -> SumolibNetworkQuery:
    return SumolibNetworkQuery(DEV_NET)


def test_get_edge_delegates_to_the_query(query: NetworkQuery) -> None:
    assert get_edge(query, "A0A1") == query.get_edge("A0A1")


def test_get_lanes_delegates_to_the_query(query: NetworkQuery) -> None:
    assert get_lanes(query, "A0A1") == query.get_lanes("A0A1")


def test_get_neighbours_delegates_to_the_query(query: NetworkQuery) -> None:
    assert get_neighbours(query, "A0A1") == query.get_neighbours("A0A1")


def test_shortest_path_delegates_to_the_query(query: NetworkQuery) -> None:
    assert shortest_path(query, "A0A1", "B0B1") == query.shortest_path("A0A1", "B0B1")


def test_edges_in_bbox_packs_the_four_scalars_into_the_bbox_tuple(query: NetworkQuery) -> None:
    assert edges_in_bbox(query, 0, 0, 50, 50) == query.edges_in_bbox((0, 0, 50, 50))


def test_capacity_estimate_delegates_to_the_query(query: NetworkQuery) -> None:
    assert capacity_estimate(query, "A0A1") == query.capacity_estimate("A0A1")


def test_get_tls_delegates_to_the_query(query: NetworkQuery) -> None:
    assert get_tls(query, "A2") == query.get_tls("A2")


def test_build_network_tools_returns_the_seven_network_mcp_tools(query: NetworkQuery) -> None:
    tools = build_network_tools(query)

    assert {t.name for t in tools} == {
        "get_edge",
        "get_lanes",
        "get_neighbours",
        "shortest_path",
        "edges_in_bbox",
        "capacity_estimate",
        "get_tls",
    }
    assert all(t.description for t in tools)
    assert all(t.input_schema.get("type") == "object" for t in tools)


def test_build_network_tools_fn_is_callable_with_only_the_llm_facing_arguments(
    query: NetworkQuery,
) -> None:
    tools = {t.name: t for t in build_network_tools(query)}

    assert tools["get_edge"].fn(edge_id="A0A1") == query.get_edge("A0A1")
    assert tools["shortest_path"].fn(from_edge="A0A1", to_edge="B0B1") == query.shortest_path(
        "A0A1", "B0B1"
    )


def test_build_network_tools_fn_propagates_key_error_for_an_unknown_id(
    query: NetworkQuery,
) -> None:
    tools = {t.name: t for t in build_network_tools(query)}

    with pytest.raises(KeyError):
        tools["get_edge"].fn(edge_id="NOPE")
