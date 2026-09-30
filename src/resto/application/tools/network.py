"""NetworkMCP: read-only queries on a `.net.xml` (DoD §4.9, work-plan E1.1).

Each function is a thin, pure delegation to a `NetworkQuery` port instance — no logic lives
here beyond that delegation (ADR-0009: the function is the one true implementation, offered
in-process to a `ToolAgent` or wrapped by `interface/mcp/network_server.py`). Every `get_*`/
`shortest_path`/`edges_in_bbox`/`capacity_estimate` call raises `KeyError` if it references an
edge/lane/TLS id that does not exist on the loaded network — callers check first with
`has_edge`/`has_lane`/`has_tls` if a missing id is an expected, non-exceptional case.

Each function is declared once with `@tool` (ADR-0033): name, explicit description and typed
parameters. The first parameter, `ctx`, is the loaded network and never reaches the model's schema.
`build_network_tools(query)` binds one loaded network to all seven and returns them as `Tool`s
ready to hand to a `ToolAgent` or to an MCP server.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any

from pydantic import Field

from resto.application.ports.llm import Tool
from resto.application.ports.network_query import NetworkQuery
from resto.application.tools.declaration import tool

_EdgeId = Annotated[str, Field(description="Edge id, e.g. 'A0A1'.")]


@tool(
    name="get_edge",
    description="Attributes of one edge: endpoints, length, speed, lane count, priority, shape.",
)
def get_edge(ctx: NetworkQuery, edge_id: _EdgeId) -> Mapping[str, Any]:
    """Attributes of one edge: endpoints, length, speed, lane count, priority, shape.

    Example: get_edge(ctx, "A0A1") ->
        {"id": "A0A1", "from_node": "A0", "to_node": "A1", "length": 189.6, "speed": 13.89,
         "lane_count": 1, "priority": -1, "type": "", "allows": [...], "shape": [...]}

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return ctx.get_edge(edge_id)


@tool(
    name="get_lanes",
    description=(
        "Per-lane attributes of one edge: index, length, speed, width, allowed vehicle classes."
    ),
)
def get_lanes(ctx: NetworkQuery, edge_id: _EdgeId) -> Sequence[Mapping[str, Any]]:
    """Per-lane attributes of one edge: index, length, speed, width, allowed vehicle classes.

    Example: get_lanes(ctx, "A0A1") ->
        [{"id": "A0A1_0", "index": 0, "length": 189.6, "speed": 13.89, "width": 3.2,
          "allows": [...]}]

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return ctx.get_lanes(edge_id)


@tool(
    name="get_neighbours",
    description=(
        "Ids of the edges reachable in one hop downstream of `edge_id` (outgoing connections)."
    ),
)
def get_neighbours(ctx: NetworkQuery, edge_id: _EdgeId) -> Sequence[str]:
    """Ids of the edges reachable in one hop downstream of `edge_id` (outgoing connections).

    Example: get_neighbours(ctx, "A0A1") -> ["A1A2", "A1B1"]

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return ctx.get_neighbours(edge_id)


@tool(
    name="shortest_path",
    description=(
        "Ids of the edges on the shortest route from `from_edge` to `to_edge`, "
        "empty if unreachable."
    ),
)
def shortest_path(
    ctx: NetworkQuery,
    from_edge: Annotated[str, Field(description="Origin edge id.")],
    to_edge: Annotated[str, Field(description="Destination edge id.")],
) -> Sequence[str]:
    """Ids of the edges on the shortest route from `from_edge` to `to_edge`, empty if unreachable.

    Example: shortest_path(ctx, "A0A1", "B0B1") ->
        ["A0A1", "A1B1", "B1C1", "C1C0", "C0B0", "B0B1"]

    Raises:
        KeyError: `from_edge` or `to_edge` does not exist on this network.
    """
    return ctx.shortest_path(from_edge, to_edge)


@tool(
    name="edges_in_bbox",
    description=(
        "Ids of the edges whose bounding box overlaps `(xmin, ymin, xmax, ymax)` (net coordinates)."
    ),
)
def edges_in_bbox(
    ctx: NetworkQuery, xmin: float, ymin: float, xmax: float, ymax: float
) -> Sequence[str]:
    """Ids of the edges whose bounding box overlaps `(xmin, ymin, xmax, ymax)` (net coordinates).

    Example: edges_in_bbox(ctx, 0, 0, 50, 50) -> ["A0A1", "A0B0", "A1A0", "B0A0"]
    """
    return ctx.edges_in_bbox((xmin, ymin, xmax, ymax))


@tool(
    name="capacity_estimate",
    description=(
        "Rough capacity of `edge_id` in veh/h (Greenshields estimate — see ADR-0015; order-of-"
    ),
)
def capacity_estimate(ctx: NetworkQuery, edge_id: _EdgeId) -> float:
    """Rough capacity of `edge_id` in veh/h (Greenshields estimate — see ADR-0015; order-of-
    magnitude only, not a substitute for a simulated result).

    Example: capacity_estimate(ctx, "A0A1") -> 1666.8

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return ctx.capacity_estimate(edge_id)


@tool(
    name="get_tls",
    description=(
        "Controlled edges and signal programs (phase state/duration pairs) of one traffic light."
    ),
)
def get_tls(
    ctx: NetworkQuery, tls_id: Annotated[str, Field(description="Traffic light id.")]
) -> Mapping[str, Any]:
    """Controlled edges and signal programs (phase state/duration pairs) of one traffic light.

    Example: get_tls(ctx, "A2") ->
        {"id": "A2", "controlled_edges": ["A1A2", "A3A2", "B2A2"],
         "programs": {"0": [("GgrrGG", 42), ("yyrrGy", 3), ("rrGGGr", 42), ("rryyGr", 3)]}}

    Raises:
        KeyError: `tls_id` does not exist on this network.
    """
    return ctx.get_tls(tls_id)


def build_network_tools(query: NetworkQuery) -> tuple[Tool, ...]:
    """The seven NetworkMCP tools, bound to one loaded network."""
    return tuple(
        declared.bind(query)
        for declared in (
            get_edge,
            get_lanes,
            get_neighbours,
            shortest_path,
            edges_in_bbox,
            capacity_estimate,
            get_tls,
        )
    )
