"""Parse the work plan's measurement DAG (mermaid, section 4.2) into nodes and edges."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = "dag:"
_HEADING = re.compile(r"^#{2,4}\s+4\.2\b", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^#{1,4}\s", re.MULTILINE)
_BLOCK = re.compile(r"```mermaid\n(.*?)^```", re.MULTILINE | re.DOTALL)
_NODE = re.compile(
    r'(\w+)\s*(?:\(\(|\{\{|\(\[|\[\[|\[|\(|\{)"([^"]*)"(?:\)\)|\}\}|\]\)|\]\]|\]|\)|\})'
    r"(?::::(\w+))?"
)
_ARROW = re.compile(r"\s*(?:==>|-->|-\.->|---|-\.-)(?:\s*\|[^|]*\|)?\s*")
_IGNORED = re.compile(
    r"(flowchart|graph|classDef|class|style|linkStyle|subgraph|end|direction)\b"
)
_KINDS = {"pass": "milestone", "suite": "suite"}


@dataclass
class Dag:
    nodes: dict[str, tuple[str, str]] = field(default_factory=dict)  # id -> (kind, label)
    edges: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_dag(plan: Path) -> Dag:
    dag = Dag()
    try:
        text = plan.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        dag.warnings.append(f"cannot read the work plan for the measurement DAG: {exc}")
        return dag
    heading = _HEADING.search(text)
    section_end = _NEXT_HEADING.search(text, heading.end()) if heading else None
    block = (
        _BLOCK.search(text, heading.end(), section_end.start() if section_end else len(text))
        if heading
        else None
    )
    if block is None:
        dag.warnings.append("no mermaid block under section 4.2 of the work plan")
        return dag
    for raw in block.group(1).splitlines():
        line = raw.split("%%", 1)[0].strip()
        if not line or _IGNORED.match(line):
            continue
        for match in _NODE.finditer(line):
            node_id, label, style = match.groups()
            dag.nodes[node_id] = (_KINDS.get(style or "", "validates"), _label(label))
        line = _NODE.sub(lambda m: m.group(1), line)
        segments = [[i.strip() for i in seg.split("&")] for seg in _ARROW.split(line)]
        if not all(re.fullmatch(r"\w+", i) for seg in segments for i in seg):
            dag.warnings.append(f"cannot parse mermaid line: {line}")
            continue
        for before, after in zip(segments, segments[1:], strict=False):
            dag.edges.extend((a, b) for a in before for b in after)
    for a, b in dag.edges:
        for node_id in (a, b):
            if node_id not in dag.nodes:
                dag.nodes[node_id] = ("validates", node_id)
                dag.warnings.append(f"mermaid node {node_id} is used but never defined")
    if not dag.nodes:
        dag.warnings.append("the mermaid block of section 4.2 has no nodes")
    return dag


def _label(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<br\s*/?>", " ", label)).strip()


def drop_time_markers(
    nodes: dict[str, tuple[str, str]], edges: list[tuple[str, str]]
) -> tuple[dict[str, tuple[str, str]], list[tuple[str, str]]]:
    """Remove the diagram's dates, which are moments in time and not work.

    A milestone survives only when a real task has an edge into it (M8 closes E9.6 and E10.7).
    Validation 1, Validation 2, the feature freeze and "all built" have no task of their own, so
    they go, and so does any node whose only links were to them (the January buffer).
    """
    closed_by_task = {b for a, b in edges if not a.startswith(PREFIX)}
    dropped = {
        i for i, (kind, _) in nodes.items() if kind == "milestone" and i not in closed_by_task
    }
    touched = {n for e in edges if dropped.intersection(e) for n in e}
    while True:
        kept = [(a, b) for a, b in edges if a not in dropped and b not in dropped]
        linked = {n for e in kept for n in e}
        orphans = {i for i in touched if i in nodes and i not in dropped and i not in linked}
        if not orphans:
            break
        dropped |= orphans
    return {i: v for i, v in nodes.items() if i not in dropped}, kept


_TASK_IN_LABEL = re.compile(r"\bE\d+\.\d+\b")


def link_tasks(
    dag: Dag, task_ids: set[str]
) -> tuple[dict[str, tuple[str, str]], list[tuple[str, str]]]:
    """Join the diagram to the real tasks.

    A node whose label starts with a task id (`E4.10 calibration`) is that task, so it is dropped
    and its edges point at the task. A node marked done (`✅ E4.2 E4.3`) gets an edge from each
    listed task that exists. Returns the remaining `dag:` nodes and every edge with full ids.
    """
    alias: dict[str, str] = {}
    for node_id, (_, label) in dag.nodes.items():
        first = _TASK_IN_LABEL.match(label)
        if first and first.group() in task_ids:
            alias[node_id] = first.group()
    nodes = {PREFIX + i: v for i, v in dag.nodes.items() if i not in alias}

    def full(node_id: str) -> str:
        return alias.get(node_id) or PREFIX + node_id

    edges = [(full(a), full(b)) for a, b in dag.edges]
    for node_id, (_, label) in dag.nodes.items():
        if label.startswith("✅"):
            edges += [(t, PREFIX + node_id) for t in dict.fromkeys(_TASK_IN_LABEL.findall(label))
                      if t in task_ids]
    return nodes, edges
