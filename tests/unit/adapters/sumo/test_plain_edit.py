"""`PlainNetEditor` adapter (E6.1/06; ADR-0045): the four typed edits on a minimal plain XML, and
the edits that cannot be applied, reported as an `UnresolvableEdit` instead of approximated."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from resto.adapters.sumo.plain_edit import XmlPlainNetEditor
from resto.application.ports.sumo import UnresolvableEdit
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    SetSpeed,
)

NODES = """<nodes>
    <node id="N1" x="0" y="0"/>
    <node id="N2" x="100" y="0"/>
    <node id="N3" x="100" y="100"/>
</nodes>
"""
EDGES = """<edges>
    <edge id="e12" from="N1" to="N2" numLanes="2" speed="13.89"/>
    <edge id="e23" from="N2" to="N3" numLanes="2" speed="13.89">
        <lane index="0" speed="10"/>
    </edge>
    <edge id="e21" from="N2" to="N1" numLanes="1" speed="13.89"/>
</edges>
"""
CONNECTIONS = """<connections>
    <connection from="e12" to="e23" fromLane="0" toLane="0"/>
    <connection from="e12" to="e23" fromLane="1" toLane="1"/>
    <connection from="e12" to="e21" fromLane="1" toLane="0"/>
</connections>
"""
EDITOR = XmlPlainNetEditor()


def plain(tmp_path: Path) -> Path:
    (tmp_path / "plain.nod.xml").write_text(NODES)
    (tmp_path / "plain.edg.xml").write_text(EDGES)
    (tmp_path / "plain.con.xml").write_text(CONNECTIONS)
    return tmp_path


def edges(directory: Path) -> dict[str, ET.Element]:
    root = ET.parse(directory / "plain.edg.xml").getroot()
    return {e.get("id", ""): e for e in root.findall("edge")}


def connections(directory: Path) -> list[tuple[str | None, ...]]:
    root = ET.parse(directory / "plain.con.xml").getroot()
    return [
        (c.get("from"), c.get("to"), c.get("fromLane"), c.get("toLane"))
        for c in root.findall("connection")
    ]


def test_set_speed_changes_the_edge_and_its_lane_overrides(tmp_path: Path) -> None:
    directory = plain(tmp_path)

    EDITOR.apply(directory, SetSpeed("e23", 8.33))

    edge = edges(directory)["e23"]
    assert float(edge.get("speed", "")) == 8.33
    assert [float(lane.get("speed", "")) for lane in edge.findall("lane")] == [8.33]
    assert float(edges(directory)["e12"].get("speed", "")) == 13.89


def test_set_lanes_changes_the_count_and_folds_connections_onto_the_remaining_lanes(
    tmp_path: Path,
) -> None:
    directory = plain(tmp_path)

    EDITOR.apply(directory, SetLanes("e12", 1))

    assert edges(directory)["e12"].get("numLanes") == "1"
    assert connections(directory) == [
        ("e12", "e23", "0", "0"),
        ("e12", "e23", "0", "1"),
        ("e12", "e21", "0", "0"),
    ]


def test_set_lanes_folds_connections_arriving_on_the_edge(tmp_path: Path) -> None:
    directory = plain(tmp_path)

    EDITOR.apply(directory, SetLanes("e23", 1))

    assert connections(directory) == [
        ("e12", "e23", "0", "0"),
        ("e12", "e23", "1", "0"),
        ("e12", "e21", "1", "0"),
    ]


def test_set_lanes_drops_the_lane_overrides_beyond_the_new_count(tmp_path: Path) -> None:
    directory = plain(tmp_path)
    (directory / "plain.edg.xml").write_text(
        EDGES.replace(
            '<lane index="0" speed="10"/>',
            '<lane index="0" speed="10"/><lane index="1" speed="9"/>',
        )
    )

    EDITOR.apply(directory, SetLanes("e23", 1))

    assert [lane.get("index") for lane in edges(directory)["e23"].findall("lane")] == ["0"]


def test_remove_edge_drops_the_edge_and_every_connection_that_touches_it(tmp_path: Path) -> None:
    directory = plain(tmp_path)

    EDITOR.apply(directory, RemoveEdge("e23"))

    assert set(edges(directory)) == {"e12", "e21"}
    assert connections(directory) == [("e12", "e21", "1", "0")]


def test_add_edge_joins_two_existing_junctions(tmp_path: Path) -> None:
    directory = plain(tmp_path)

    EDITOR.apply(directory, AddEdge("N1", "N3", lanes=2, speed=11.11, edge_id="diagonal"))

    added = edges(directory)["diagonal"]
    assert (added.get("from"), added.get("to")) == ("N1", "N3")
    assert added.get("numLanes") == "2"
    assert float(added.get("speed", "")) == 11.11


def test_add_edge_without_an_id_gets_one_named_after_its_junctions(tmp_path: Path) -> None:
    directory = plain(tmp_path)

    EDITOR.apply(directory, AddEdge("N1", "N3", lanes=1, speed=8.0))

    assert "N1N3" in edges(directory)


def test_add_edge_to_a_missing_junction_asks_for_add_node(tmp_path: Path) -> None:
    directory = plain(tmp_path)

    with pytest.raises(UnresolvableEdit) as unresolvable:
        EDITOR.apply(directory, AddEdge("N1", "N9", lanes=1, speed=8.0))

    issue = unresolvable.value.issue
    assert (issue.element_kind, issue.element_id, issue.needed_tool) == (
        "junction",
        "N9",
        "add_node",
    )
    assert "N1N9" not in edges(directory)


def test_add_edge_with_a_taken_id_is_unresolved_not_overwritten(tmp_path: Path) -> None:
    directory = plain(tmp_path)

    with pytest.raises(UnresolvableEdit) as unresolvable:
        EDITOR.apply(directory, AddEdge("N1", "N3", lanes=1, speed=8.0, edge_id="e12"))

    assert unresolvable.value.issue.element_kind == "edge"
    assert unresolvable.value.issue.needed_tool is None


@pytest.mark.parametrize(
    "modification", [RemoveEdge("nope"), SetLanes("nope", 2), SetSpeed("nope", 5.0)]
)
def test_an_edit_of_an_unknown_edge_is_unresolved(
    tmp_path: Path, modification: RemoveEdge | SetLanes | SetSpeed
) -> None:
    directory = plain(tmp_path)

    with pytest.raises(UnresolvableEdit) as unresolvable:
        EDITOR.apply(directory, modification)

    assert (unresolvable.value.issue.element_kind, unresolvable.value.issue.element_id) == (
        "edge",
        "nope",
    )
