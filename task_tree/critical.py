"""Critical path of the open work: the longest chain of unfinished tasks, weighted by points."""

from __future__ import annotations

from typing import Any


def critical_path(nodes: dict[str, dict[str, Any]], edges: list[tuple[str, str]]) -> list[str]:
    """Node ids of the heaviest chain through the unfinished nodes, first to last.

    A task weighs its points, or 1 when the plan gives none. Diagram nodes (milestone, suite,
    validates) weigh 0, so they end a chain without lengthening it. Edges that touch a finished
    node are ignored, and so is any edge that would close a cycle.
    """
    open_ids = {i for i, n in nodes.items() if n["stage"] not in ("done", "wontfix", "cancelled")}
    preds: dict[str, list[str]] = {i: [] for i in open_ids}
    for a, b in edges:
        if a in open_ids and b in open_ids and a != b and a not in preds[b]:
            preds[b].append(a)
    weight = {i: (nodes[i]["points"] or 1) if nodes[i]["kind"] == "task" else 0 for i in open_ids}
    best: dict[str, tuple[int, str | None]] = {}

    def solve(node_id: str, seen: frozenset[str]) -> int:
        if node_id in best:
            return best[node_id][0]
        chosen: tuple[int, str | None] = (0, None)
        for p in preds[node_id]:
            if p in seen:
                continue
            total = solve(p, seen | {node_id})
            if total > chosen[0] or (total == chosen[0] and chosen[1] is None):
                chosen = (total, p)
        best[node_id] = (chosen[0] + weight[node_id], chosen[1])
        return best[node_id][0]

    for node_id in sorted(open_ids):
        solve(node_id, frozenset())
    if not best:
        return []
    has_successor = {p for ps in preds.values() for p in ps}
    sinks = sorted(i for i in best if i not in has_successor) or sorted(best)
    last: str | None = max(sinks, key=lambda i: best[i][0])
    path: list[str] = []
    while last is not None:
        path.append(last)
        last = best[last][1]
    return path[::-1]
