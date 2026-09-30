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
            dag.nodes[node_id] = (_KINDS.get(style or "", "result"), _label(label))
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
                dag.nodes[node_id] = ("result", node_id)
                dag.warnings.append(f"mermaid node {node_id} is used but never defined")
    if not dag.nodes:
        dag.warnings.append("the mermaid block of section 4.2 has no nodes")
    return dag


def _label(label: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<br\s*/?>", " ", label)).strip()
