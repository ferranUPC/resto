"""Read `.scratch/` and the progress tracker into a task tree. Reads only; nothing is cached."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from task_tree.dag import drop_time_markers, link_tasks, parse_dag

STAGES = ("needs-triage", "ready", "specified", "ticketed", "done", "wontfix", "needs-info")
FINISHED = ("done", "wontfix")
_TITLE = re.compile(
    r"^#\s+(?:(?:Refactor|Unplanned)\s+)?(?:([A-Za-z]+\d+(?:\.\d+)?):\s*)?(.+?)\s*$"
)
_STATUS = re.compile(r"^\*\*Status:\*\*\s*(\S+)", re.MULTILINE)
_BLOCKED = re.compile(r"^\*\*Blocked by:\*\*(.*(?:\n(?![\n*#]).*)*)", re.MULTILINE)
_PRIORITY = re.compile(r"^\*\*Priority:\*\*\s*urgent\s*$", re.MULTILINE | re.IGNORECASE)
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
    urgent: bool = False


def _read(path: Path, warnings: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        warnings.append(f"cannot read {path.name}: {exc}")
        return ""


def _status(text: str) -> str | None:
    match = _STATUS.search(text)
    return match.group(1).lower() if match else None


def _is_urgent(text: str, stage: str) -> bool:
    """An urgent line only counts while the work is open."""
    return stage not in FINISHED and _PRIORITY.search(text) is not None


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
    tickets: list[dict[str, Any]] = []
    for path in sorted((directory / "issues").glob("[0-9][0-9]-*.md")):
        text = _read(path, warnings)
        title = re.search(r"^#\s+(?:\d+\s*[:.-]\s*)?(.+?)\s*$", text, re.MULTILINE)
        stage = _status(text) or "needs-triage"
        tickets.append(
            {
                "id": path.name[:2],
                "name": title.group(1) if title else path.stem,
                "stage": stage,
                "blocked_by": _blocked_by(text, _TICKET_ID),
                "urgent": _is_urgent(text, stage),
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
    urgent = stage not in FINISHED and (
        _is_urgent(text, stage) or any(t["urgent"] for t in tickets)
    )
    return Task(
        task_id, name, stage, _blocked_by(text, _TASK_ID), tickets, problems, directory, urgent
    )


def _tracker_done(path: Path) -> dict[str, str]:
    """Task id -> name for every row the tracker marks done."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    rows = re.finditer(r"^\|\s*(E\d+\.\d+)\s*\|\s*(.+?)\s*\|\s*✅\s*\|", text, re.MULTILINE)
    return {m.group(1): re.sub(r"^\*\(new [\d-]+\)\*\s*", "", m.group(2)) for m in rows}


_MARKS = {"⏳": "awaiting", "🚧": "blocked"}


def _tracker_marks(path: Path) -> dict[str, str]:
    """Task id -> `awaiting` (⏳) or `blocked` (🚧) for every tracker row carrying that status."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    marks: dict[str, str] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if (
            line.startswith("|")
            and len(cells) > 2
            and cells[2] in _MARKS
            and re.fullmatch(r"E\d+\.\d+", cells[0])
        ):
            marks[cells[0]] = _MARKS[cells[2]]
    return marks


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
    """Column = longest chain of work from a root; row = barycenter of blocker rows.

    Finished tasks are laid out like any other, so a finished blocker pushes its dependents right.
    `extra_deps` are the diagram's edges. They place nodes but never block a task.
    """
    for node in nodes.values():
        node["lane"] = "active"
    active = set(nodes)
    deps_of = {i: [d for d in nodes[i]["blocked_by"] + extra_deps.get(i, []) if d in active]
               for i in active}
    column: dict[str, int] = {}

    def depth(node_id: str, seen: frozenset[str]) -> int:
        if node_id in column:
            return column[node_id]
        if node_id in seen:
            return 0
        column[node_id] = 1 + max(
            (depth(d, seen | {node_id}) for d in deps_of[node_id]), default=-1
        )
        return column[node_id]

    for node_id in nodes:
        if node_id in active:
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
    for node_id in active:
        nodes[node_id]["column"], nodes[node_id]["row"] = column[node_id], int(rows[node_id])


_MONTHS = {m: i for i, m in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
_DATE = re.compile(r"(\d{1,2})(?:\s*[–-]\s*(\d{1,2}))?\s+(" + "|".join(_MONTHS) + r")\b")


def _date_key(day: str, month: str) -> int:
    """Sortable month*100+day. The TFM runs Sep 2026 to Feb 2027, so Aug-Dec sorts first."""
    number = _MONTHS[month]
    return (number if number >= 8 else number + 12) * 100 + int(day)


def _due_dates(plan: Path) -> dict[str, int]:
    """Task id -> latest date in the last cell of its work-plan row (the `Latest due` column)."""
    try:
        text = plan.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    dues: dict[str, int] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if not line.startswith("|") or len(cells) < 3 or not re.fullmatch(r"E\d+\.\d+", cells[0]):
            continue
        found = [_date_key(m.group(1), m.group(3)) for m in _DATE.finditer(cells[-1])]
        if found:
            dues[cells[0]] = max(found)
    return dues


def _plan_points(plan: Path) -> dict[str, int]:
    """Task id -> points from the `pts` column of each work-plan table.

    The column is found from the end of the row, so a `|` inside the task text cannot shift it.
    """
    try:
        text = plan.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    points: dict[str, int] = {}
    from_end: int | None = None
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        lowered = [c.lower() for c in cells]
        if cells[0] == "ID":
            from_end = len(cells) - lowered.index("pts") if "pts" in lowered else None
        elif from_end and re.fullmatch(r"E\d+\.\d+", cells[0]) and len(cells) >= from_end:
            match = re.fullmatch(r"\**(\d+)\**", cells[-from_end])
            if match:
                points[cells[0]] = int(match.group(1))
    return points


def _milestone_date(label: str) -> int | None:
    """End of the first date in a milestone label (`14–18 Dec` -> 18 Dec), or None if undated."""
    match = _DATE.search(label)
    if match is None:
        return None
    return _date_key(match.group(2) or match.group(1), match.group(3))


def _due_text(key: int) -> str:
    """Inverse of `_date_key`: 1326 -> `26 Jan`."""
    month = key // 100 - 12 if key // 100 > 12 else key // 100
    return f"{key % 100} {list(_MONTHS)[month - 1]}"


@dataclass
class Milestone:
    id: str
    title: str
    target: str | None
    deadline: str | None
    key: int | None
    tasks: list[str]


def _plain(cell: str) -> str:
    return re.sub(r"\*+", "", cell).strip()


def _date_text(cell: str) -> str | None:
    """First date of a cell, ignoring a struck-through old date (`~~Fri 5 Feb~~ Fri 29 Jan`)."""
    match = _DATE.search(re.sub(r"~~.*?~~", "", cell))
    return match.group(0) if match else None


def _task_refs(acceptance: str) -> list[str]:
    """Task ids named in an acceptance check, with `E4.2–E4.4` expanded.

    Text after an arrow is a pointer to later work (`V2 → E4.10 → E8.5`), not part of the milestone.
    """
    ids: list[str] = []
    for match in re.finditer(r"E(\d+)\.(\d+)(?:\s*[–-]\s*E\1\.(\d+))?", acceptance.split("→")[0]):
        first, last = int(match.group(2)), int(match.group(3) or match.group(2))
        ids += [f"E{match.group(1)}.{n}" for n in range(first, last + 1)]
    return list(dict.fromkeys(ids))


def _parse_milestones(plan: Path) -> tuple[list[Milestone], int | None]:
    """The milestones of the work plan's §2 table with the tasks each lists, and the freeze date.

    `FF` (feature freeze) is a date and lists no task, so it is returned apart from the milestones.
    """
    try:
        text = plan.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [], None
    milestones: list[Milestone] = []
    freeze: int | None = None
    in_table = False
    for line in text.splitlines():
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
        if cells[:2] == ["ID", "Target"]:
            in_table = True
        elif in_table and len(cells) >= 5 and re.fullmatch(r"\*{0,2}(M\d+|FF)\*{0,2}", cells[0]):
            target = _date_text(cells[1])
            key = _milestone_date(target) if target else None
            if _plain(cells[0]) == "FF":
                freeze = key
            else:
                milestones.append(
                    Milestone(_plain(cells[0]), _plain(cells[3]), target, _date_text(cells[2]),
                              key, _task_refs(cells[4]))
                )
    return milestones, freeze


def _is_refactor(task_id: str) -> bool:
    return re.fullmatch(r"r\d+|refactor-.+", task_id) is not None


def _assign_rails(
    nodes: dict[str, dict[str, Any]],
    edges: list[tuple[str, str]],
    milestones: list[Milestone],
    member: dict[str, str],
    dues: dict[str, int],
) -> list[dict[str, Any]]:
    """Group nodes into one horizontal rail per milestone and set `node["rail"]`.

    A task belongs to the milestone whose §2 row lists it. A finished task that no row lists (the
    foundations and tooling, whose milestones name no task) goes in the first milestone whose
    deadline is not before the task's due date. Any other unlisted task goes in the earliest
    milestone downstream of it, and a suite or validates node with nothing downstream goes in the
    last milestone drawn from the diagram (M7, where the results close). Refactors have no
    milestone and share a collapsed rail. What is left is in a collapsed "Unscheduled" rail below
    it. Only milestones that end up with a node get a rail.
    """
    candidates = [
        {"id": m.id, "name": f"{m.id} · {m.title}", "target": m.target, "deadline": m.deadline,
         "key": m.key}
        for m in milestones
    ]
    by_deadline = sorted(
        ((k, m.id) for m in milestones if m.deadline and (k := _milestone_date(m.deadline))),
    )

    def rail_by_due(node_id: str) -> str | None:
        due = dues.get(node_id)
        return next((r for k, r in by_deadline if due is not None and k >= due), None)

    listed = {m.id for m in milestones}
    # A diagram milestone named after a table row (`M7 · 18 Feb ...`) is that row's rail.
    same_as: dict[str, str] = {}
    for node in nodes.values():
        if node["kind"] != "milestone" or node["lane"] != "active":
            continue
        lead = re.match(r"M\d+", node["name"])
        if lead and lead.group() in listed:
            same_as[node["id"]] = lead.group()
        else:
            candidates.append({"id": node["id"], "name": node["name"], "target": None,
                               "deadline": None, "key": _milestone_date(node["name"])})
    candidates.sort(key=lambda c: c["key"] if c["key"] is not None else 10**6)
    order = {c["id"]: i for i, c in enumerate(candidates)}
    from_diagram = [c["id"] for c in candidates if c["id"] in nodes] + list(same_as.values())
    closing = max(from_diagram, key=lambda r: order.get(r, -1), default=None)
    successors: dict[str, list[str]] = {}
    for a, b in edges:
        successors.setdefault(a, []).append(b)
    known: dict[str, str | None] = {}

    def rail_of(node_id: str, seen: frozenset[str] = frozenset()) -> str | None:
        if node_id in known:
            return known[node_id]
        node = nodes.get(node_id)
        if node is None or node_id in seen:
            return None
        found: str | None = None
        if node["kind"] == "milestone":
            found = same_as.get(node_id, node_id)
        elif _is_refactor(node_id):
            found = "refactors"
        elif node_id in member:
            found = member[node_id]
        elif node["stage"] in FINISHED and rail_by_due(node_id):
            found = rail_by_due(node_id)
        else:
            below = [r for s in successors.get(node_id, [])
                     if nodes.get(s, {}).get("lane") == "active"
                     and (r := rail_of(s, seen | {node_id})) not in (None, "refactors")]
            if below:
                found = min(below, key=lambda r: order.get(r or "", 10**6))
            elif node["kind"] in ("suite", "validates"):
                found = closing
        known[node_id] = found
        return found

    chosen = {i: rail_of(i) for i, n in nodes.items() if n["lane"] == "active"}
    used = {r for r in chosen.values() if r is not None}
    rails: list[dict[str, Any]] = [
        {k: v for k, v in c.items() if k != "key"} for c in candidates if c["id"] in used
    ]
    if "refactors" in used:
        rails.append({"id": "refactors", "name": "Refactors", "collapsed": True})
    if None in chosen.values():
        rails.append({"id": "unscheduled", "name": "Unscheduled", "collapsed": True})
    index = {r["id"]: i for i, r in enumerate(rails)}
    for node_id, rail in chosen.items():
        nodes[node_id]["rail"] = index["unscheduled" if rail is None else rail]
    return rails


def _id_order(task_id: str) -> tuple[str, int, int, str]:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)(?:\.(\d+))?", task_id)
    if match is None:
        return ("~", 0, 0, task_id)
    return (match.group(1), int(match.group(2)), int(match.group(3) or 0), task_id)


def _short_name(cell: str) -> str:
    """A work-plan task cell cut to a title: no markup, no `(new ...)` tag, first clause only."""
    text = re.sub(r"\*\(.*?\)\*|[*`]", "", cell).strip()
    return re.split(r"\s+→|[.:;(]\s", text, maxsplit=1)[0].strip()[:80]


def _members(plan: Path | None) -> dict[str, str]:
    """Task id -> id of the milestone whose §2 row lists it first."""
    member: dict[str, str] = {}
    for milestone in _parse_milestones(plan)[0] if plan is not None else []:
        for task_id in milestone.tasks:
            member.setdefault(task_id, milestone.id)
    return member


def _load_tasks(
    scratch: Path, tracker: Path, plan: Path | None = None
) -> tuple[dict[str, Task], set[str]]:
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
        if task_id not in tasks:
            tasks[task_id] = Task(task_id, name, "done")
    # A finished task with no known blocker would sit in column 0 whatever its epic, so it gets
    # a guessed order too.
    guessed = {t.id for t in tasks.values() if t.stage in FINISHED and not t.blocked_by
               and re.fullmatch(r"E\d+\.\d+", t.id)}
    for task_id, deps in _infer_chains(sorted(guessed)).items():
        tasks[task_id].blocked_by = deps
    # A task a milestone lists but nobody has opened yet (E8.8, final delivery) still belongs on
    # the tree, as a task that needs triage.
    for task_id in _members(plan):
        row = _table_row(plan, task_id) if plan is not None else None
        if task_id not in tasks and row and len(row) > 1:
            tasks[task_id] = Task(task_id, _short_name(row[1]), "needs-triage")
    return tasks, guessed


def build_tree(scratch: Path, tracker: Path, plan: Path | None = None) -> dict[str, Any]:
    tasks, guessed = _load_tasks(scratch, tracker, plan)
    done = {t.id for t in tasks.values() if t.stage in FINISHED}
    points = _plan_points(plan) if plan is not None else {}
    marks = _tracker_marks(tracker)
    dues = _due_dates(plan) if plan is not None else {}
    milestones, freeze = _parse_milestones(plan) if plan is not None else ([], None)
    member = _members(plan)
    nodes: dict[str, dict[str, Any]] = {}
    for task in tasks.values():
        blocked = any(d in tasks and d not in done for d in task.blocked_by)
        nodes[task.id] = {
            "id": task.id,
            "kind": "task",
            "name": task.name,
            "points": points.get(task.id),
            "due": _due_text(dues[task.id]) if task.id in dues else None,
            "after_freeze": freeze is not None and dues.get(task.id, 0) > freeze,
            "stage": task.stage,
            "blocked_by": [d for d in task.blocked_by if d in tasks],
            "blocked": blocked,
            # Startable now: no open blocker, and the tracker has no ⏳ or 🚧 on it.
            "frontier": not blocked
            and task.stage not in (*FINISHED, "needs-info")
            and task.id not in marks,
            "urgent": task.urgent,
            "tracker_mark": marks.get(task.id),
            "tickets": task.tickets,
            "warnings": task.warnings,
        }
    tree_warnings: list[str] = []
    dag_edges: list[tuple[str, str]] = []
    if plan is not None:
        dag = parse_dag(plan)
        tree_warnings = dag.warnings
        if not milestones:
            tree_warnings.append("no milestone table (section 2) in the work plan")
        dag_nodes, dag_edges = link_tasks(dag, set(tasks))
        dag_nodes, dag_edges = drop_time_markers(dag_nodes, dag_edges)
        for dag_id, (kind, label) in dag_nodes.items():
            nodes[dag_id] = {
                "id": dag_id,
                "kind": kind,
                "name": label,
                "points": None,
                "due": None,
                "after_freeze": False,
                "stage": kind,
                "blocked_by": [],
                "blocked": False,
                "frontier": False,
                "urgent": False,
                "tracker_mark": None,
                "tickets": [],
                "warnings": [],
            }
    extra_deps: dict[str, list[str]] = {}
    for a, b in dag_edges:
        extra_deps.setdefault(b, []).append(a)
    _layout(nodes, extra_deps)
    rails = _assign_rails(nodes, dag_edges + [(d, n["id"]) for n in nodes.values()
                                               for d in n["blocked_by"]], milestones, member, dues)
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
        "rails": rails,
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
    tasks, _ = _load_tasks(scratch, tracker, plan)
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
        "has_spec": task.directory is not None,
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
