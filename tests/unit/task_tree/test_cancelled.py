"""The `cancelled` status: a cancelled node is absorbed, so its dependents inherit its blockers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from task_tree.tree import build_tree

PLAN = """### 4.2 Measurement DAG

```mermaid
flowchart LR
  S1(["EXP suite"]):::suite
  T1["E5.2 cancelled step"]:::task --> S1
```
"""


def _task(
    root: Path, name: str, title: str, status: str, blocked: str = "None", extra: str = ""
) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "spec.md").write_text(
        f"# {title}\n\n**Status:** {status}\n\n**Blocked by:** {blocked}\n\n{extra}"
        "## Spec\n\nA real spec.\n",
        encoding="utf-8",
    )
    return directory


def _tree(tmp_path: Path, plan: str | None = None) -> dict[str, Any]:
    tracker = tmp_path / "progress-tracker.md"
    tracker.write_text("| ID | Task | Status | Notes |\n|---|---|---|---|\n", encoding="utf-8")
    plan_path = None
    if plan is not None:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(plan, encoding="utf-8")
    return build_tree(tmp_path / ".scratch", tracker, plan_path)


def _nodes(tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["id"]: n for n in tree["nodes"]}


def _edges(tree: dict[str, Any]) -> set[tuple[str, str]]:
    return {(e["from"], e["to"]) for e in tree["edges"]}


def _real_case(root: Path) -> None:
    _task(root, "e3-7", "E3.7: Base", "ready")
    _task(root, "e5-2", "E5.2: Dropped", "cancelled", "E3.7")
    _task(root, "e5-15", "E5.15: First dependent", "ready", "E5.2")
    _task(root, "e5-3", "E5.3: Second dependent", "ready", "E5.2")


def test_dependents_of_a_cancelled_task_inherit_its_blockers(tmp_path):
    _real_case(tmp_path / ".scratch")
    tree = _tree(tmp_path)
    nodes = _nodes(tree)
    assert nodes["E5.2"]["stage"] == "cancelled"
    assert nodes["E5.15"]["blocked_by"] == ["E3.7"]
    assert nodes["E5.3"]["blocked_by"] == ["E3.7"]
    assert nodes["E5.15"]["blocked"] is True
    assert {("E3.7", "E5.15"), ("E3.7", "E5.3")} <= _edges(tree)
    assert not [edge for edge in _edges(tree) if edge[0] == "E5.2"]


def test_a_cancelled_task_is_not_frontier_blocked_or_urgent(tmp_path):
    root = tmp_path / ".scratch"
    _real_case(root)
    spec = root / "e5-2" / "spec.md"
    spec.write_text(spec.read_text() + "**Priority:** urgent\n", encoding="utf-8")
    cancelled = _nodes(_tree(tmp_path))["E5.2"]
    assert cancelled["frontier"] is False
    assert cancelled["blocked"] is False
    assert cancelled["urgent"] is False


def test_a_cancelled_task_with_no_blockers_is_not_frontier_and_blocks_nothing(tmp_path):
    root = tmp_path / ".scratch"
    _task(root, "e1-1", "E1.1: Gone", "cancelled")
    _task(root, "e1-2", "E1.2: After it", "ready", "E1.1")
    nodes = _nodes(_tree(tmp_path))
    assert nodes["E1.1"]["frontier"] is False
    assert nodes["E1.2"]["blocked_by"] == []
    assert nodes["E1.2"]["blocked"] is False
    assert nodes["E1.2"]["frontier"] is True


def test_absorption_is_transitive_and_has_no_duplicates(tmp_path):
    root = tmp_path / ".scratch"
    _task(root, "e1-1", "E1.1: Base", "ready")
    _task(root, "e1-2", "E1.2: Other base", "ready")
    _task(root, "e1-3", "E1.3: Gone first", "cancelled", "E1.1")
    _task(root, "e1-4", "E1.4: Gone second", "cancelled", "E1.3, E1.2")
    _task(root, "e1-5", "E1.5: Waits", "ready", "E1.4, E1.1")
    nodes = _nodes(_tree(tmp_path))
    assert sorted(nodes["E1.5"]["blocked_by"]) == ["E1.1", "E1.2"]


def test_absorption_ignores_a_cycle_among_cancelled_tasks(tmp_path):
    root = tmp_path / ".scratch"
    _task(root, "e1-1", "E1.1: Gone a", "cancelled", "E1.2")
    _task(root, "e1-2", "E1.2: Gone b", "cancelled", "E1.1")
    _task(root, "e1-3", "E1.3: Waits", "ready", "E1.1")
    assert _nodes(_tree(tmp_path))["E1.3"]["blocked_by"] == []


def test_replaced_by_sends_the_dependents_to_the_replacement_instead(tmp_path):
    root = tmp_path / ".scratch"
    _task(root, "e3-7", "E3.7: Base", "ready")
    _task(
        root, "e5-2", "E5.2: Dropped", "cancelled", "E3.7", "**Cancelled:** replaced by E5.15\n\n"
    )
    _task(root, "e5-15", "E5.15: Replacement", "ready", "None")
    _task(root, "e5-3", "E5.3: Dependent", "ready", "E5.2")
    nodes = _nodes(_tree(tmp_path))
    assert nodes["E5.3"]["blocked_by"] == ["E5.15"]
    assert nodes["E5.3"]["blocked"] is True


def test_a_replacement_that_waits_on_the_dependent_is_ignored_for_that_edge(tmp_path):
    root = tmp_path / ".scratch"
    _task(root, "e3-7", "E3.7: Base", "ready")
    _task(root, "e5-2", "E5.2: Dropped", "cancelled", "E3.7", "**Cancelled:** replaced by E5.4\n\n")
    _task(root, "e5-3", "E5.3: Dependent", "ready", "E5.2")
    _task(root, "e5-4", "E5.4: Replacement that waits on E5.3", "ready", "E5.3")
    nodes = _nodes(_tree(tmp_path))
    assert nodes["E5.3"]["blocked_by"] == ["E3.7"]
    assert nodes["E5.4"]["blocked_by"] == ["E5.3"]


def test_a_task_replaced_by_its_own_dependent_falls_back_to_absorption(tmp_path):
    root = tmp_path / ".scratch"
    _task(root, "e3-7", "E3.7: Base", "ready")
    _task(
        root, "e5-2", "E5.2: Dropped", "cancelled", "E3.7", "**Cancelled:** replaced by E5.15\n\n"
    )
    _task(root, "e5-15", "E5.15: Dependent and replacement", "ready", "E5.2")
    assert _nodes(_tree(tmp_path))["E5.15"]["blocked_by"] == ["E3.7"]


def test_a_cancelled_ticket_is_absorbed_and_never_blocked(tmp_path):
    root = tmp_path / ".scratch"
    directory = _task(root, "e2-1", "E2.1: Ticketed", "ready")
    issues = directory / "issues"
    issues.mkdir()
    (issues / "01-base.md").write_text("# 01: Base\n\n**Status:** ready\n", encoding="utf-8")
    (issues / "02-gone.md").write_text(
        "# 02: Gone\n\n**Status:** cancelled\n\n**Blocked by:** 01\n\n**Priority:** urgent\n",
        encoding="utf-8",
    )
    (issues / "03-after.md").write_text(
        "# 03: After\n\n**Status:** ready\n\n**Blocked by:** 02\n", encoding="utf-8"
    )
    (issues / "04-replaced.md").write_text(
        "# 04: Replaced\n\n**Status:** cancelled\n\n**Blocked by:** 01\n\n"
        "**Cancelled:** replaced by 05\n",
        encoding="utf-8",
    )
    (issues / "05-new.md").write_text("# 05: New\n\n**Status:** ready\n", encoding="utf-8")
    (issues / "06-after-replaced.md").write_text(
        "# 06: After replaced\n\n**Status:** ready\n\n**Blocked by:** 04\n", encoding="utf-8"
    )
    tickets = {t["id"]: t for t in _nodes(_tree(tmp_path))["E2.1"]["tickets"]}
    assert tickets["02"]["blocked"] is False
    assert tickets["02"]["urgent"] is False
    assert tickets["03"]["blocked_by"] == ["01"]
    assert tickets["03"]["blocked"] is True
    assert tickets["06"]["blocked_by"] == ["05"]


def test_a_suite_after_a_cancelled_task_waits_on_what_the_task_waited_on(tmp_path):
    root = tmp_path / ".scratch"
    _task(root, "e3-7", "E3.7: Base", "ready")
    _task(root, "e5-2", "E5.2: Dropped", "cancelled", "E3.7")
    tree = _tree(tmp_path, PLAN)
    suite = next(n["id"] for n in tree["nodes"] if n["kind"] == "suite")
    edges = _edges(tree)
    assert ("E3.7", suite) in edges
    assert ("E5.2", suite) not in edges


def test_the_critical_path_skips_cancelled_tasks(tmp_path):
    _real_case(tmp_path / ".scratch")
    assert "E5.2" not in _tree(tmp_path)["critical_path"]
