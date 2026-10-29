"""What the Network Author can say about a network without simulating it: a bounded
summary, one edge, and the `SanityReport`.

Every function reads through `EnumerableNetworkQuery` and returns plain values. The graph is the
one vehicles drive on: edges are the vertices, and a connection from one edge to the next is an arc.

Two figures need a definition the report does not carry:

- an edge has zero length when it is no longer than `ZERO_LENGTH_M`, SUMO's own floor for an edge
  (`netconvert` raises anything shorter to it), so a shorter edge never reaches a built network;
- the border is every edge nothing leads into, plus the largest strongly connected component. An
  edge counts as reachable from the border when a vehicle entering there can get to it. Closed
  networks such as a grid have no entry edge, which is why their core stands in for the border;
- the exits are every edge that leads nowhere, plus the core. An edge carries through traffic when
  it is reachable from the border and can reach an exit (ADR-0048). A road cut at the edge of the
  selection has entries and exits that are not defects, so the share of such edges, not of the
  core, is what the report is judged on.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from resto.application.ports.network_query import EnumerableNetworkQuery
from resto.domain.value_objects.sanity_report import SanityReport

ZERO_LENGTH_M = 0.1
MAX_SUSPECTS = 10


def sanity_report(query: EnumerableNetworkQuery) -> SanityReport:
    edges = list(query.edge_ids())
    successors = {e: list(query.get_neighbours(e)) for e in edges}
    zero_length = sum(1 for e in edges if query.get_edge(e)["length"] <= ZERO_LENGTH_M)
    if not edges:
        return SanityReport(0.0, zero_length, False, 0.0)
    core = max(_strong_components(successors), key=len)
    predecessors: dict[str, set[str]] = defaultdict(set)
    for edge, targets in successors.items():
        for target in targets:
            predecessors[target].add(edge)
    border = {e for e in edges if not predecessors[e]} | set(core)
    exits = {e for e in edges if not successors[e]} | set(core)
    reached = _reachable(successors, border)
    through = reached & _reachable(predecessors, exits)
    return SanityReport(
        largest_scc_ratio=len(core) / len(edges),
        zero_length_edges=zero_length,
        all_reachable_from_fringe=reached == set(edges),
        through_traffic_ratio=len(through) / len(edges),
    )


def network_summary(query: EnumerableNetworkQuery) -> Mapping[str, Any]:
    edges = list(query.edge_ids())
    rows = {e: query.get_edge(e) for e in edges}
    successors = {e: list(query.get_neighbours(e)) for e in edges}
    has_predecessor = {t for targets in successors.values() for t in targets}
    speeds = [row["speed"] for row in rows.values()]
    suspects = _suspects(rows, successors, has_predecessor)
    return {
        "edges": len(edges),
        "junctions": len({n for row in rows.values() for n in (row["from_node"], row["to_node"])}),
        "traffic_lights": len(query.tls_ids()),
        "total_length_m": sum(row["length"] for row in rows.values()),
        "speeds_mps": {"min": min(speeds), "max": max(speeds)} if speeds else {},
        "road_types": dict(
            sorted(Counter(row["type"] or "(untyped)" for row in rows.values()).items())
        ),
        "vehicle_classes": sorted({vc for row in rows.values() for vc in row["allows"]}),
        "connected_components": _weak_component_count(successors),
        "suspect_count": len(suspects),
        "suspects": suspects[:MAX_SUSPECTS],
    }


def edge_description(query: EnumerableNetworkQuery, edge_id: str) -> Mapping[str, Any]:
    """One edge: its attributes without the shape, its lanes and the edges it leads to.

    Raises:
        KeyError: `edge_id` is not an edge of the network.
    """
    if not query.has_edge(edge_id):
        raise KeyError(f"no edge {edge_id!r} in this network")
    attributes = {k: v for k, v in query.get_edge(edge_id).items() if k != "shape"}
    return {
        **attributes,
        "lanes": list(query.get_lanes(edge_id)),
        "successors": list(query.get_neighbours(edge_id)),
    }


def _suspects(
    rows: Mapping[str, Mapping[str, Any]],
    successors: Mapping[str, Sequence[str]],
    has_predecessor: set[str],
) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for edge in sorted(rows):
        if rows[edge]["length"] <= ZERO_LENGTH_M:
            found.append({"edge": edge, "reason": "zero length"})
        elif not successors[edge] and edge not in has_predecessor:
            found.append({"edge": edge, "reason": "isolated"})
        elif not successors[edge]:
            found.append({"edge": edge, "reason": "no outgoing connection"})
    return found


def _strong_components(successors: Mapping[str, Sequence[str]]) -> list[list[str]]:
    """Tarjan's algorithm without recursion, so a long road cannot exhaust the stack."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[list[str]] = []
    for root in successors:
        if root in index:
            continue
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(successors[root]))]
        while work:
            node, pending = work[-1]
            for nxt in pending:
                if nxt not in index:
                    index[nxt] = low[nxt] = len(index)
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(successors[nxt])))
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        component.append(member)
                        if member == node:
                            break
                    components.append(component)
    return components


def _reachable(successors: Mapping[str, Iterable[str]], start: set[str]) -> set[str]:
    seen = set(start)
    todo = list(start)
    while todo:
        for nxt in successors[todo.pop()]:
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def _weak_component_count(successors: Mapping[str, Sequence[str]]) -> int:
    neighbours: dict[str, set[str]] = defaultdict(set)
    for edge, targets in successors.items():
        neighbours[edge]
        for target in targets:
            neighbours[edge].add(target)
            neighbours[target].add(edge)
    unseen = set(neighbours)
    count = 0
    while unseen:
        count += 1
        unseen -= _reachable(neighbours, {unseen.pop()})
    return count
