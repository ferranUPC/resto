"""Plain-XML edit tools of the Network Author (E6.1/06; ADR-0033, ADR-0045): each edit builds a new
network from the one it is given with real `netconvert`; an edit that cannot apply comes back as an
unresolved issue, never as a network."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.plain_edit import XmlPlainNetEditor
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promoters.network import NetworkPromoter
from resto.application.tools.network_edit import (
    EditRun,
    add_edge,
    build_network_edit_tools,
    remove_edge,
    set_lanes,
    set_speed,
)
from resto.domain.entities.network import Network
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.drafts import NetworkDraft
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import GridNetwork
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import NetworkTask
from resto.domain.value_objects.topology_modification import (
    RemoveEdge,
    SetSpeed,
    TopologyModification,
)
from tests.unit.domain._fixtures import good_sanity, network_draft

RUNNER = SubprocessNetconvertRunner()
GRID = GridNetwork(x_number=3, y_number=3)


def run_of(draft: NetworkDraft) -> AgentRun[NetworkDraft]:
    return AgentRun(output=draft, tool_calls=(), usage=Usage(), stop_reason=StopReason.OUTPUT)


def base(tmp_path: Path) -> Network:
    built = RUNNER.generate(GRID, tmp_path / "base")
    return Network(
        network_id=built.content_hash,
        net_xml=built,
        recipe=NetworkRecipe(source=GRID),
        sanity_report=good_sanity(),
    )


def run_in(tmp_path: Path) -> EditRun:
    return EditRun(runner=RUNNER, editor=XmlPlainNetEditor(), out_dir=tmp_path / "edits")


def test_remove_edge_returns_a_new_network_and_the_modification_to_put_in_the_recipe(
    tmp_path: Path,
) -> None:
    net = base(tmp_path).net_xml

    result = remove_edge(run_in(tmp_path), str(net.path), net.content_hash, "A0A1")

    assert result["modification"] == {"kind": "remove_edge", "edge_id": "A0A1"}
    assert result["net_artifact"]["content_hash"] != net.content_hash
    assert "unresolved" not in result
    assert 'id="A0A1"' not in Path(result["net_artifact"]["path"]).read_text()


def test_set_lanes_and_set_speed_report_what_they_applied(tmp_path: Path) -> None:
    net = base(tmp_path).net_xml

    lanes = set_lanes(run_in(tmp_path), str(net.path), net.content_hash, "A0B0", 2)
    speed = set_speed(run_in(tmp_path), str(net.path), net.content_hash, "A0B0", 8.33)

    assert lanes["modification"] == {"kind": "set_lanes", "edge_id": "A0B0", "lanes": 2}
    assert speed["modification"] == {"kind": "set_speed", "edge_id": "A0B0", "speed": 8.33}
    assert lanes["net_artifact"]["content_hash"] != speed["net_artifact"]["content_hash"]


def test_add_edge_between_existing_junctions_builds_the_network(tmp_path: Path) -> None:
    net = base(tmp_path).net_xml

    result = add_edge(
        run_in(tmp_path), str(net.path), net.content_hash, "A0", "C2", 2, 11.11, "shortcut"
    )

    assert result["modification"]["edge_id"] == "shortcut"
    assert 'id="shortcut"' in Path(result["net_artifact"]["path"]).read_text()


def test_add_edge_to_a_missing_junction_comes_back_as_unresolved_with_the_missing_tool(
    tmp_path: Path,
) -> None:
    net = base(tmp_path).net_xml

    result = add_edge(run_in(tmp_path), str(net.path), net.content_hash, "A0", "Z9", 1, 8.0, None)

    assert result == {
        "unresolved": {
            "element_kind": "junction",
            "element_id": "Z9",
            "issue": "the junction does not exist, so the edge cannot join it",
            "needed_tool": "add_node",
        }
    }


def test_an_edit_of_an_unknown_edge_comes_back_as_unresolved(tmp_path: Path) -> None:
    net = base(tmp_path).net_xml

    result = remove_edge(run_in(tmp_path), str(net.path), net.content_hash, "nope")

    assert result["unresolved"]["element_kind"] == "edge"
    assert result["unresolved"]["needed_tool"] is None


def test_out_of_range_parameters_are_rejected_before_sumo_runs(tmp_path: Path) -> None:
    net = base(tmp_path).net_xml

    with pytest.raises(ValueError, match="lanes"):
        set_lanes(run_in(tmp_path), str(net.path), net.content_hash, "A0B0", 0)


def test_edits_chained_through_the_tools_replay_to_the_hash_of_the_last_tool(
    tmp_path: Path,
) -> None:
    network = base(tmp_path)
    net = network.net_xml
    ctx = run_in(tmp_path)
    first = remove_edge(ctx, str(net.path), net.content_hash, "A0A1")
    second = set_speed(
        ctx, first["net_artifact"]["path"], first["net_artifact"]["content_hash"], "B0C0", 8.33
    )
    edits: tuple[TopologyModification, ...] = (RemoveEdge("A0A1"), SetSpeed("B0C0", 8.33))
    draft: NetworkDraft = network_draft(
        recipe=NetworkRecipe(base_network_id=network.network_id, plain_edits=edits),
        net_artifact=_artifact(second),
    )
    task = NetworkTask(base_network_id=network.network_id, max_rounds=2)

    promoted = NetworkPromoter(RUNNER, XmlPlainNetEditor()).promote(run_of(draft), task, net)

    assert promoted.network_id == second["net_artifact"]["content_hash"]
    assert promoted.derived_from == network.network_id


def _artifact(result: Mapping[str, Any]) -> ArtifactRef:
    raw = result["net_artifact"]
    return ArtifactRef(Path(raw["path"]), raw["content_hash"], raw["kind"])


def test_the_edit_tools_are_declared_once_under_their_names(tmp_path: Path) -> None:
    tools = build_network_edit_tools(run_in(tmp_path))

    assert [t.name for t in tools] == ["remove_edge", "add_edge", "set_lanes", "set_speed"]
