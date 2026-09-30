"""Read `.scratch/` and the progress tracker into a task tree. Reads only; nothing is cached."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    return Task(task_id, name, stage, _blocked_by(text, _TASK_ID), tickets, problems)


def _tracker_done(path: Path) -> dict[str, str]:
    """Task id -> name for every row the tracker marks done."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    rows = re.finditer(r"^\|\s*(E\d+\.\d+)\s*\|\s*(.+?)\s*\|\s*✅\s*\|", text, re.MULTILINE)
    return {m.group(1): re.sub(r"^\*\(new [\d-]+\)\*\s*", "", m.group(2)) for m in rows}


def _layout(nodes: dict[str, dict[str, Any]]) -> None:
    """Column = longest chain from a root; row = barycenter of the blockers' rows."""
    column: dict[str, int] = {}

    def depth(node_id: str, seen: frozenset[str]) -> int:
        if node_id in column:
            return column[node_id]
        if node_id in seen:
            return 0
        deps = [d for d in nodes[node_id]["blocked_by"] if d in nodes]
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
            deps = [rows[d] for d in nodes[node_id]["blocked_by"] if d in rows]
            return (sum(deps) / len(deps) if deps else 1e9, node_id)

        for row, node_id in enumerate(sorted(by_column[col], key=key)):
            rows[node_id] = row
    for node_id, node in nodes.items():
        node["column"], node["row"] = column[node_id], int(rows[node_id])


def build_tree(scratch: Path, tracker: Path) -> dict[str, Any]:
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
    for task_id, name in _tracker_done(tracker).items():
        tasks.setdefault(task_id, Task(task_id, name, "done"))
    done = {t.id for t in tasks.values() if t.stage in FINISHED}
    nodes: dict[str, dict[str, Any]] = {}
    for task in tasks.values():
        nodes[task.id] = {
            "id": task.id,
            "name": task.name,
            "stage": task.stage,
            "blocked_by": [d for d in task.blocked_by if d in tasks],
            "blocked": any(d in tasks and d not in done for d in task.blocked_by),
            "tickets": task.tickets,
            "warnings": task.warnings,
        }
    _layout(nodes)
    edges = [
        {"from": dep, "to": node["id"], "done": dep in done}
        for node in nodes.values()
        for dep in node["blocked_by"]
    ]
    return {"nodes": list(nodes.values()), "edges": edges, "stages": list(STAGES)}
