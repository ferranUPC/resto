"""`PlainNetEditor` adapter: applies one `TopologyModification` to the plain XML files that
`netconvert --plain-output-prefix` writes (`*.nod.xml`, `*.edg.xml`, `*.con.xml`, `*.tll.xml`)
(E6.1/06; ADR-0045).

Edits are made with ElementTree and written back to the same files, so the same edits on the same
plain files give the same bytes, which the promoter's replay relies on. Nothing is approximated:
an edge or junction that does not exist, or an id already taken, raises `UnresolvableEdit` before
any file is written. `add_edge` joins existing junctions only; a new junction is
`needed_tool: "add_node"`.

Known limit: traffic-light programs are not rewritten. Removing an edge drops its `<connection>`
entries from `*.tll.xml`, but a program whose phase states no longer match the link count is
refused by `netconvert` and surfaces as a `NetBuildError`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from resto.application.ports.sumo import UnresolvableEdit
from resto.domain.value_objects.drafts import ElementKind, UnresolvedIssue
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    SetSpeed,
    TopologyModification,
)

ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")


class XmlPlainNetEditor:
    """`PlainNetEditor` over ElementTree."""

    def apply(self, plain_dir: Path, modification: TopologyModification) -> None:
        match modification:
            case RemoveEdge():
                _remove_edge(plain_dir, modification)
            case AddEdge():
                _add_edge(plain_dir, modification)
            case SetLanes():
                _set_lanes(plain_dir, modification)
            case SetSpeed():
                _set_speed(plain_dir, modification)


class _Doc:
    """One parsed plain file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()

    def save(self) -> None:
        ET.indent(self.tree, space="    ")
        self.tree.write(self.path, encoding="utf-8", xml_declaration=True)


def _load(plain_dir: Path, suffix: str) -> list[_Doc]:
    return [_Doc(path) for path in sorted(plain_dir.glob(f"*{suffix}"))]


def _find_edge(docs: list[_Doc], edge_id: str) -> tuple[_Doc, ET.Element]:
    for doc in docs:
        for element in doc.root.findall("edge"):
            if element.get("id") == edge_id:
                return doc, element
    raise _unresolved("edge", edge_id, "the edge does not exist in the network")


def _remove_edge(plain_dir: Path, edit: RemoveEdge) -> None:
    edge_files = _load(plain_dir, ".edg.xml")
    doc, element = _find_edge(edge_files, edit.edge_id)
    doc.root.remove(element)
    doc.save()
    for suffix in (".con.xml", ".tll.xml"):
        for other in _load(plain_dir, suffix):
            for connection in other.root.findall("connection"):
                if edit.edge_id in (connection.get("from"), connection.get("to")):
                    other.root.remove(connection)
            other.save()


def _add_edge(plain_dir: Path, edit: AddEdge) -> None:
    junctions = {
        node.get("id") for doc in _load(plain_dir, ".nod.xml") for node in doc.root.findall("node")
    }
    for junction in (edit.from_junction, edit.to_junction):
        if junction not in junctions:
            raise _unresolved(
                "junction",
                junction,
                "the junction does not exist, so the edge cannot join it",
                needed_tool="add_node",
            )
    edge_files = _load(plain_dir, ".edg.xml")
    edge_id = edit.edge_id or f"{edit.from_junction}{edit.to_junction}"
    if not edge_files:
        raise _unresolved("edge", edge_id, "the network has no edge file to add the edge to")
    taken = {e.get("id") for doc in edge_files for e in doc.root.findall("edge")}
    if edge_id in taken:
        raise _unresolved("edge", edge_id, "an edge with this id already exists")
    attributes = {
        "id": edge_id,
        "from": edit.from_junction,
        "to": edit.to_junction,
        "numLanes": str(edit.lanes),
        "speed": repr(edit.speed),
    }
    ET.SubElement(edge_files[0].root, "edge", attributes)
    edge_files[0].save()


def _set_lanes(plain_dir: Path, edit: SetLanes) -> None:
    doc, element = _find_edge(_load(plain_dir, ".edg.xml"), edit.edge_id)
    element.set("numLanes", str(edit.lanes))
    for lane in element.findall("lane"):
        if int(lane.get("index", "0")) >= edit.lanes:
            element.remove(lane)
    doc.save()
    for other in _load(plain_dir, ".con.xml"):
        seen: set[tuple[tuple[str, str], ...]] = set()
        for connection in other.root.findall("connection"):
            if connection.get("from") == edit.edge_id:
                _fold(connection, "fromLane", edit.lanes)
            if connection.get("to") == edit.edge_id:
                _fold(connection, "toLane", edit.lanes)
            key = tuple(sorted(connection.attrib.items()))
            if key in seen:
                other.root.remove(connection)
            seen.add(key)
        other.save()


def _fold(connection: ET.Element, attribute: str, lanes: int) -> None:
    """A connection on a lane that no longer exists moves to the outermost remaining lane."""
    value = connection.get(attribute)
    if value is not None and int(value) >= lanes:
        connection.set(attribute, str(lanes - 1))


def _set_speed(plain_dir: Path, edit: SetSpeed) -> None:
    doc, element = _find_edge(_load(plain_dir, ".edg.xml"), edit.edge_id)
    element.set("speed", repr(edit.speed))
    for lane in element.findall("lane"):
        if lane.get("speed") is not None:
            lane.set("speed", repr(edit.speed))
    doc.save()


def _unresolved(
    kind: ElementKind, element_id: str, issue: str, *, needed_tool: str | None = None
) -> UnresolvableEdit:
    return UnresolvableEdit(UnresolvedIssue(kind, element_id, issue, needed_tool))
