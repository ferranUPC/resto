"""The critical path: heaviest chain of unfinished work, weighted by points."""

from __future__ import annotations

from typing import Any

from task_tree.critical import critical_path


def _node(points: int | None = None, stage: str = "ready", kind: str = "task") -> dict[str, Any]:
    return {"points": points, "stage": stage, "kind": kind}


def test_the_path_follows_the_heaviest_chain_not_the_longest_one():
    nodes = {"A": _node(1), "B": _node(1), "C": _node(1), "D": _node(10), "E": _node(1)}
    edges = [("A", "B"), ("B", "C"), ("C", "E"), ("D", "E")]
    assert critical_path(nodes, edges) == ["D", "E"]


def test_finished_tasks_and_their_edges_are_left_out():
    nodes = {"A": _node(50, "done"), "B": _node(2), "C": _node(3)}
    assert critical_path(nodes, [("A", "B"), ("B", "C")]) == ["B", "C"]


def test_a_task_without_points_weighs_one_and_a_diagram_node_weighs_nothing():
    nodes = {"A": _node(), "B": _node(), "S": _node(kind="suite"), "C": _node(1)}
    assert critical_path(nodes, [("A", "B"), ("B", "S"), ("C", "S")]) == ["A", "B", "S"]


def test_a_cycle_does_not_loop_and_nothing_open_gives_an_empty_path():
    nodes = {"A": _node(1), "B": _node(1)}
    assert len(critical_path(nodes, [("A", "B"), ("B", "A")])) == 2
    assert critical_path({"A": _node(1, "done")}, []) == []
