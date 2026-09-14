"""NetworkMCP: read-only queries on a `.net.xml` (DoD §4.9, work-plan E1.1).

Each function is a thin, pure delegation to a `NetworkQuery` port instance — no logic lives
here beyond that delegation (ADR-0009: the function is the one true implementation, offered
in-process to a `ToolAgent` or wrapped by `interface/mcp/network_server.py`). Every `get_*`/
`shortest_path`/`edges_in_bbox`/`capacity_estimate` call raises `KeyError` if it references an
edge/lane/TLS id that does not exist on the loaded network — callers check first with
`has_edge`/`has_lane`/`has_tls` if a missing id is an expected, non-exceptional case.

`build_network_tools(query)` binds one loaded network to all seven functions and returns them as
`Tool`s ready to hand to a `ToolAgent` or to an MCP server.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import partial
from typing import Any

from resto.application.ports.llm import Tool
from resto.application.ports.network_query import NetworkQuery


def get_edge(query: NetworkQuery, edge_id: str) -> Mapping[str, Any]:
    """Attributes of one edge: endpoints, length, speed, lane count, priority, shape.

    Example: get_edge(query, "A0A1") ->
        {"id": "A0A1", "from_node": "A0", "to_node": "A1", "length": 189.6, "speed": 13.89,
         "lane_count": 1, "priority": -1, "type": "", "allows": [...], "shape": [...]}

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return query.get_edge(edge_id)


def get_lanes(query: NetworkQuery, edge_id: str) -> Sequence[Mapping[str, Any]]:
    """Per-lane attributes of one edge: index, length, speed, width, allowed vehicle classes.

    Example: get_lanes(query, "A0A1") ->
        [{"id": "A0A1_0", "index": 0, "length": 189.6, "speed": 13.89, "width": 3.2,
          "allows": [...]}]

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return query.get_lanes(edge_id)


def get_neighbours(query: NetworkQuery, edge_id: str) -> Sequence[str]:
    """Ids of the edges reachable in one hop downstream of `edge_id` (outgoing connections).

    Example: get_neighbours(query, "A0A1") -> ["A1A2", "A1B1"]

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return query.get_neighbours(edge_id)


def shortest_path(query: NetworkQuery, from_edge: str, to_edge: str) -> Sequence[str]:
    """Ids of the edges on the shortest route from `from_edge` to `to_edge`, empty if unreachable.

    Example: shortest_path(query, "A0A1", "B0B1") ->
        ["A0A1", "A1B1", "B1C1", "C1C0", "C0B0", "B0B1"]

    Raises:
        KeyError: `from_edge` or `to_edge` does not exist on this network.
    """
    return query.shortest_path(from_edge, to_edge)


def edges_in_bbox(
    query: NetworkQuery, xmin: float, ymin: float, xmax: float, ymax: float
) -> Sequence[str]:
    """Ids of the edges whose bounding box overlaps `(xmin, ymin, xmax, ymax)` (net coordinates).

    Example: edges_in_bbox(query, 0, 0, 50, 50) -> ["A0A1", "A0B0", "A1A0", "B0A0"]
    """
    return query.edges_in_bbox((xmin, ymin, xmax, ymax))


def capacity_estimate(query: NetworkQuery, edge_id: str) -> float:
    """Rough capacity of `edge_id` in veh/h (Greenshields estimate — see ADR-0015; order-of-
    magnitude only, not a substitute for a simulated result).

    Example: capacity_estimate(query, "A0A1") -> 1666.8

    Raises:
        KeyError: `edge_id` does not exist on this network.
    """
    return query.capacity_estimate(edge_id)


def get_tls(query: NetworkQuery, tls_id: str) -> Mapping[str, Any]:
    """Controlled edges and signal programs (phase state/duration pairs) of one traffic light.

    Example: get_tls(query, "A2") ->
        {"id": "A2", "controlled_edges": ["A1A2", "A3A2", "B2A2"],
         "programs": {"0": [("GgrrGG", 42), ("yyrrGy", 3), ("rrGGGr", 42), ("rryyGr", 3)]}}

    Raises:
        KeyError: `tls_id` does not exist on this network.
    """
    return query.get_tls(tls_id)


_SCHEMAS: dict[str, Mapping[str, Any]] = {
    "get_edge": {
        "type": "object",
        "properties": {"edge_id": {"type": "string", "description": "Edge id, e.g. 'A0A1'."}},
        "required": ["edge_id"],
    },
    "get_lanes": {
        "type": "object",
        "properties": {"edge_id": {"type": "string", "description": "Edge id, e.g. 'A0A1'."}},
        "required": ["edge_id"],
    },
    "get_neighbours": {
        "type": "object",
        "properties": {"edge_id": {"type": "string", "description": "Edge id, e.g. 'A0A1'."}},
        "required": ["edge_id"],
    },
    "shortest_path": {
        "type": "object",
        "properties": {
            "from_edge": {"type": "string", "description": "Origin edge id."},
            "to_edge": {"type": "string", "description": "Destination edge id."},
        },
        "required": ["from_edge", "to_edge"],
    },
    "edges_in_bbox": {
        "type": "object",
        "properties": {
            "xmin": {"type": "number"},
            "ymin": {"type": "number"},
            "xmax": {"type": "number"},
            "ymax": {"type": "number"},
        },
        "required": ["xmin", "ymin", "xmax", "ymax"],
    },
    "capacity_estimate": {
        "type": "object",
        "properties": {"edge_id": {"type": "string", "description": "Edge id, e.g. 'A0A1'."}},
        "required": ["edge_id"],
    },
    "get_tls": {
        "type": "object",
        "properties": {"tls_id": {"type": "string", "description": "Traffic light id."}},
        "required": ["tls_id"],
    },
}

_FUNCTIONS = (
    get_edge,
    get_lanes,
    get_neighbours,
    shortest_path,
    edges_in_bbox,
    capacity_estimate,
    get_tls,
)


def build_network_tools(query: NetworkQuery) -> tuple[Tool, ...]:
    """The seven NetworkMCP tools, bound to one loaded network.

    Each `Tool.fn` is `functools.partial(fn, query)` with `__name__`/`__doc__` copied from `fn` —
    `mcp.server.mcpserver`'s schema introspection needs both, and `inspect.signature` already
    drops the bound `query` argument from a `partial`, leaving exactly the LLM-facing parameters.
    """
    tools = []
    for fn in _FUNCTIONS:
        bound = partial(fn, query)
        bound.__name__ = fn.__name__  # type: ignore[attr-defined, union-attr]
        bound.__doc__ = fn.__doc__
        tools.append(
            Tool(
                name=fn.__name__,
                description=(fn.__doc__ or "").strip().splitlines()[0],
                fn=bound,
                input_schema=_SCHEMAS[fn.__name__],
            )
        )
    return tuple(tools)
