"""Plain-XML edit tools of the Network Author, declared once (ADR-0033; E6.1/06, ADR-0045):
`remove_edge`, `add_edge`, `set_lanes` and `set_speed`.

Each tool takes the `.net.xml` to edit (the `net_artifact` an earlier tool returned), exports it to
plain XML, applies one typed `TopologyModification` and recompiles with `netconvert`. It returns
the new `net_artifact` and the `modification` to append to the recipe's `plain_edits`. An edit that
cannot apply (an edge or junction that does not exist, an id already taken) returns
`{"unresolved": {...}}` instead of a network, ready for `NetworkDraft.unresolved[]`; a junction
that is missing carries `needed_tool: "add_node"`. Ranges are checked by the modification
dataclass, before SUMO runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from resto.application.ports.llm import Tool
from resto.application.ports.sumo import NetconvertRunner, PlainNetEditor, UnresolvableEdit
from resto.application.tools.declaration import artifact_json, tool
from resto.domain.services.content_hash import work_key
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    SetSpeed,
    TopologyModification,
)


@dataclass(frozen=True, slots=True)
class EditRun:
    """What the edit tools are bound to (the `ctx` the model never sees)."""

    runner: NetconvertRunner
    editor: PlainNetEditor
    out_dir: Path


NetPath = Annotated[
    str, Field(description="`net_artifact.path` of the .net.xml to edit, from an earlier tool.")
]
NetHash = Annotated[str, Field(description="`net_artifact.content_hash` of that same .net.xml.")]
EdgeId = Annotated[str, Field(min_length=1, description="Id of an existing edge.")]


def _edit(
    ctx: EditRun, net_path: str, net_hash: str, modification: TopologyModification
) -> Mapping[str, Any]:
    net = ArtifactRef(Path(net_path), net_hash, "net")
    digest = work_key(f"{net_hash}{modification!r}")
    work = ctx.out_dir / "edits" / digest
    plain = ctx.runner.export_plain(net, work / "plain")
    try:
        ctx.editor.apply(plain, modification)
    except UnresolvableEdit as unresolvable:
        return {"unresolved": asdict(unresolvable.issue)}
    built = ctx.runner.build(None, plain, (), work / "built")
    return {
        "modification": asdict(modification),
        "net_artifact": artifact_json(built),
    }


@tool(
    name="remove_edge",
    description=(
        "Remove an edge, and every connection that starts or ends on it, from a network and "
        "recompile. Returns the new net_artifact and the modification to put in the recipe, or "
        "`unresolved` when the edge does not exist."
    ),
)
def remove_edge(
    ctx: EditRun, net_path: NetPath, net_hash: NetHash, edge_id: EdgeId
) -> Mapping[str, Any]:
    return _edit(ctx, net_path, net_hash, RemoveEdge(edge_id))


@tool(
    name="add_edge",
    description=(
        "Add an edge between two junctions that already exist and recompile; SUMO guesses its "
        "connections. A junction that does not exist is not created: the result is `unresolved` "
        "with needed_tool `add_node`. Returns the new net_artifact and the modification to put "
        "in the recipe."
    ),
)
def add_edge(
    ctx: EditRun,
    net_path: NetPath,
    net_hash: NetHash,
    from_junction: Annotated[str, Field(min_length=1, description="Id of the junction it leaves.")],
    to_junction: Annotated[str, Field(min_length=1, description="Id of the junction it enters.")],
    lanes: Annotated[int, Field(ge=1, description="Number of lanes, at least 1.")],
    speed: Annotated[float, Field(gt=0, description="Speed limit in m/s, above 0.")],
    edge_id: Annotated[
        str | None,
        Field(description="Id the new edge gets; by default the two junction ids joined."),
    ] = None,
) -> Mapping[str, Any]:
    return _edit(
        ctx, net_path, net_hash, AddEdge(from_junction, to_junction, lanes, speed, edge_id)
    )


@tool(
    name="set_lanes",
    description=(
        "Set the number of lanes of an existing edge and recompile. Connections on a lane that "
        "no longer exists move to the outermost remaining lane. Returns the new net_artifact and "
        "the modification to put in the recipe, or `unresolved` when the edge does not exist."
    ),
)
def set_lanes(
    ctx: EditRun,
    net_path: NetPath,
    net_hash: NetHash,
    edge_id: EdgeId,
    lanes: Annotated[int, Field(ge=1, description="New number of lanes, at least 1.")],
) -> Mapping[str, Any]:
    return _edit(ctx, net_path, net_hash, SetLanes(edge_id, lanes))


@tool(
    name="set_speed",
    description=(
        "Set the speed limit of an existing edge, all its lanes included, and recompile. Returns "
        "the new net_artifact and the modification to put in the recipe, or `unresolved` when "
        "the edge does not exist."
    ),
)
def set_speed(
    ctx: EditRun,
    net_path: NetPath,
    net_hash: NetHash,
    edge_id: EdgeId,
    speed: Annotated[float, Field(gt=0, description="New speed limit in m/s, above 0.")],
) -> Mapping[str, Any]:
    return _edit(ctx, net_path, net_hash, SetSpeed(edge_id, speed))


def build_network_edit_tools(ctx: EditRun) -> tuple[Tool, ...]:
    return (
        remove_edge.bind(ctx),
        add_edge.bind(ctx),
        set_lanes.bind(ctx),
        set_speed.bind(ctx),
    )
