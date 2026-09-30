"""Read `.scratch/` and the progress tracker into a task tree. Reads only; nothing is cached."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from task_tree.dag import link_tasks, parse_dag

STAGES = ("needs-triage", "ready", "specified", "ticketed", "done", "wontfix", "needs-info")
FINISHED = ("done", "wontfix")
_TITLE = re.compile(
    r"^#\s+(?:(?:Refactor|Unplanned)\s+)?(?:([A-Za-z]+\d+(?:\.\d+)?):\s*)?(.+?)\s*$"
)
_STATUS = re.compile(r"^\*\*Status:\*\*\s*(\S+)", re.MULTILINE)
_BLOCKED = re.compile(r"^\*\*Blocked by:\*\*(.*(?:\n(?![\n*#]).*)*)", re.MULTILINE)
_TASK_ID = re.compile(r"\b(E\d+\.\d+|r\d+)\b")
_TICKET_ID = re.compile(r"\b(\d{2})\b")
_LINK = re.compile(r"\[[^\]]*\]\([^)]*\)|`[^`]*`")
_PLACEHOLDER = "_Not written yet"


@dataclass
class Task:
    id: str
    name: str
    stage: str
    blocked_by: list[str] = field(default_factory=list)
    tickets: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    directory: Path | None = None


def _read(path: Path, warnings: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        warnings.append(f"cannot read {path.name}: {exc}")
        return ""


def _status(text: str) -> str | None:
    match = _STATUS.search(text)
    return match.group(1).lower() if match else None


def _blocked_by(text: str, pattern: re.Pattern[str]) -> list[str]:
    match = _BLOCKED.search(text)
    if not match:
        return []
    return list(dict.fromkeys(pattern.findall(_LINK.sub("", match.group(1)))))


def _spec_is_filled(text: str) -> bool:
    match = re.search(r"^## Spec\s*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        return "## Problem Statement" in text
    body = match.group(1).strip()
    return bool(body) and not body.startswith(_PLACEHOLDER)


def _tickets(directory: Path, warnings: list[str]) -> list[dict[str, Any]]:
    tickets = []
    for path in sorted((directory / "issues").glob("[0-9][0-9]-*.md")):
        text = _read(path, warnings)
        title = re.search(r"^#\s+(?:\d+\s*[:.-]\s*)?(.+?)\s*$", text, re.MULTILINE)
        tickets.append(
            {
                "id": path.name[:2],
                "name": title.group(1) if title else path.stem,
                "stage": _status(text) or "needs-triage",
                "blocked_by": _blocked_by(text, _TICKET_ID),
            }
        )
    finished = {t["id"] for t in tickets if t["stage"] in FINISHED}
    for ticket in tickets:
        ticket["blocked"] = any(d not in finished for d in ticket["blocked_by"])
    return tickets


def _read_task(directory: Path, finished: bool) -> Task | None:
    spec = directory / "spec.md"
    if not spec.is_file():
        return None
    problems: list[str] = []
    text = _read(spec, problems)
    first = text.splitlines()[0] if text else ""
    title = _TITLE.match(first)
    if title is None:
        problems.append("spec has no '# title' first line")
    task_id = (title.group(1) if title and title.group(1) else None) or directory.name
    name = title.group(2) if title else directory.name
    status = _status(text)
    if status is None:
        problems.append("spec has no Status line")
    tickets = _tickets(directory, problems)
    if finished or status in ("done", "wontfix", "needs-info"):
        stage = "done" if finished else str(status)
    elif tickets:
        stage = "ticketed"
    elif _spec_is_filled(text):
        stage = "specified"
    else:
        stage = status if status in ("needs-triage", "ready") else "needs-triage"
    return Task(task_id, name, stage, _blocked_by(text, _TASK_ID), tickets, problems, directory)


def _tracker_done(path: Path) -> dict[str, str]:
    """Task id -> name for every row the tracker marks done."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    rows = re.finditer(r"^\|\s*(E\d+\.\d+)\s*\|\s*(.+?)\s*\|\s*✅\s*\|", text, re.MULTILINE)
    return {m.group(1): re.sub(r"^\*\(new [\d-]+\)\*\s*", "", m.group(2)) for m in rows}


def _infer_chains(ids: list[str]) -> dict[str, list[str]]:
    """Guessed order for done tasks that have no spec and so no `Blocked by:` line.

    Each task follows the previous one of its epic, and the first task of an epic follows the first
    task of the nearest earlier epic. These edges are drawn dashed: they only spread the tree out.
    """
    epics: dict[int, list[tuple[int, str]]] = {}
    for task_id in ids:
        epic_part, number_part = task_id[1:].split(".")
        epics.setdefault(int(epic_part), []).append((int(number_part), task_id))
    inferred: dict[str, list[str]] = {}
    earlier_first: str | None = None
    for epic in sorted(epics):
        ordered = [task_id for _, task_id in sorted(epics[epic])]
        if earlier_first:
            inferred[ordered[0]] = [earlier_first]
        for before, after in zip(ordered, ordered[1:], strict=False):
            inferred[after] = [before]
        earlier_first = ordered[0]
    return inferred


def _layout(nodes: dict[str, dict[str, Any]], extra_deps: dict[str, list[str]]) -> None:
    """Column = longest chain from a root; row = barycenter of the blockers' rows.

    `extra_deps` are the diagram's edges. They place nodes but never block a task.
    """
    deps_of = {i: n["blocked_by"] + extra_deps.get(i, []) for i, n in nodes.items()}
    column: dict[str, int] = {}

    def depth(node_id: str, seen: frozenset[str]) -> int:
        if node_id in column:
            return column[node_id]
        if node_id in seen:
            return 0
        deps = [d for d in deps_of[node_id] if d in nodes]
        column[node_id] = 1 + max((depth(d, seen | {node_id}) for d in deps), default=-1)
        return column[node_id]

    for node_id in nodes:
        depth(node_id, frozenset())
    rows: dict[str, float] = {}
    by_column: dict[int, list[str]] = {}
    for node_id, col in column.items():
        by_column.setdefault(col, []).append(node_id)
    for col in sorted(by_column):
        def key(node_id: str) -> tuple[float, str]:
            deps = [rows[d] for d in deps_of[node_id] if d in rows]
            return (sum(deps) / len(deps) if deps else 1e9, node_id)

        for row, node_id in enumerate(sorted(by_column[col], key=key)):
            rows[node_id] = row
    for node_id, node in nodes.items():
        node["column"], node["row"] = column[node_id], int(rows[node_id])


def _load_tasks(scratch: Path, tracker: Path) -> tuple[dict[str, Task], set[str]]:
    tasks: dict[str, Task] = {}
    directories = sorted(p for p in scratch.iterdir() if p.is_dir()) if scratch.is_dir() else []
    finished_dir = scratch / "done"
    for directory in directories:
        if directory == finished_dir:
            continue
        task = _read_task(directory, finished=False)
        if task is not None:
            tasks.setdefault(task.id, task)
    if finished_dir.is_dir():
        for directory in sorted(p for p in finished_dir.iterdir() if p.is_dir()):
            task = _read_task(directory, finished=True)
            if task is not None:
                tasks.setdefault(task.id, task)
    guessed: set[str] = set()
    for task_id, name in _tracker_done(tracker).items():
        if task_id not in tasks:
            tasks[task_id] = Task(task_id, name, "done")
            guessed.add(task_id)
    for task_id, deps in _infer_chains(sorted(guessed)).items():
        tasks[task_id].blocked_by = deps
    return tasks, guessed


def build_tree(scratch: Path, tracker: Path, plan: Path | None = None) -> dict[str, Any]:
    tasks, guessed = _load_tasks(scratch, tracker)
    done = {t.id for t in tasks.values() if t.stage in FINISHED}
    nodes: dict[str, dict[str, Any]] = {}
    for task in tasks.values():
        nodes[task.id] = {
            "id": task.id,
            "kind": "task",
            "name": task.name,
            "stage": task.stage,
            "blocked_by": [d for d in task.blocked_by if d in tasks],
            "blocked": any(d in tasks and d not in done for d in task.blocked_by),
            "tickets": task.tickets,
            "warnings": task.warnings,
        }
    tree_warnings: list[str] = []
    dag_edges: list[tuple[str, str]] = []
    if plan is not None:
        dag = parse_dag(plan)
        tree_warnings = dag.warnings
        dag_nodes, dag_edges = link_tasks(dag, set(tasks))
        for dag_id, (kind, label) in dag_nodes.items():
            nodes[dag_id] = {
                "id": dag_id,
                "kind": kind,
                "name": label,
                "stage": kind,
                "blocked_by": [],
                "blocked": False,
                "tickets": [],
                "warnings": [],
            }
    extra_deps: dict[str, list[str]] = {}
    for a, b in dag_edges:
        extra_deps.setdefault(b, []).append(a)
    _layout(nodes, extra_deps)
    edges = [
        {
            "from": dep,
            "to": node["id"],
            "done": dep in done,
            "inferred": node["id"] in guessed,
        }
        for node in nodes.values()
        for dep in node["blocked_by"]
    ]
    edges += [{"from": a, "to": b, "done": a in done, "inferred": False} for a, b in dag_edges]
    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stages": list(STAGES),
        "warnings": tree_warnings,
    }


def _table_row(path: Path, task_id: str) -> list[str] | None:
    """The cells of the first markdown table row in `path` whose first cell is `task_id`."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            if cells and cells[0] == task_id:
                return cells
    return None


def _header_line(text: str, label: str) -> str | None:
    match = re.search(rf"^\*\*{label}:\*\*\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def task_detail(scratch: Path, tracker: Path, plan: Path, task_id: str) -> dict[str, Any] | None:
    """Everything the side panel shows for one task, or None when the id is unknown."""
    tasks, _ = _load_tasks(scratch, tracker)
    task = tasks.get(task_id)
    if task is None:
        return None
    done = {t.id for t in tasks.values() if t.stage in FINISHED}
    spec_text = ""
    if task.directory is not None:
        spec_text = _read(task.directory / "spec.md", [])
    plan_line = _header_line(spec_text, "Work plan") or ""
    points = re.search(r"(\d+)\s*pts", plan_line)
    due = re.search(r"latest due\s+\**([^·*]+?)\**\s*(?:·|$)", plan_line)
    plan_row = _table_row(plan, task_id)
    tracker_row = _table_row(tracker, task_id)
    return {
        "id": task.id,
        "name": task.name,
        "stage": task.stage,
        "blocked": any(d in tasks and d not in done for d in task.blocked_by),
        # A task without a spec only has guessed edges, which the panel must not show as fact.
        "blocked_by": task.blocked_by if task.directory is not None else [],
        "points": points.group(1) if points else None,
        "latest_due": due.group(1).strip() if due else None,
        "measured_in": _header_line(spec_text, "Measured in"),
        "plan_excerpt": " | ".join(plan_row[1:]) if plan_row else None,
        "tracker_status": tracker_row[2] if tracker_row and len(tracker_row) > 2 else None,
        "tracker_notes": (
            " | ".join(tracker_row[3:]) if tracker_row and len(tracker_row) > 3 else None
        ),
        "tickets": task.tickets,
        "warnings": task.warnings,
    }


def ticket_detail(
    scratch: Path, tracker: Path, task_id: str, ticket_id: str
) -> dict[str, Any] | None:
    """One ticket's question, status and blockers, or None when the task or ticket is unknown."""
    tasks, _ = _load_tasks(scratch, tracker)
    task = tasks.get(task_id)
    if task is None or task.directory is None:
        return None
    ticket = next((t for t in task.tickets if t["id"] == ticket_id), None)
    if ticket is None:
        return None
    path = next((task.directory / "issues").glob(f"{ticket_id}-*.md"), None)
    if path is None:
        return None
    text = _read(path, [])
    question = re.search(r"^\*\*What to build:\*\*\s*(.*(?:\n(?!\n).*)*)", text, re.MULTILINE)
    return {
        "task_id": task.id,
        "task_name": task.name,
        "id": ticket_id,
        "name": ticket["name"],
        "stage": ticket["stage"],
        "blocked": ticket["blocked"],
        "blocked_by": ticket["blocked_by"],
        "question": question.group(1).strip() if question else None,
    }
