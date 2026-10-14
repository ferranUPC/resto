"""Inspection, sanity and probe tools of the Network Author, declared once (ADR-0033, ADR-0045).

`inspect_network`, `inspect_edge` and `sanity_check` read the network through the
`EnumerableNetworkQuery` port. `probe_run` simulates light random demand through the `NetworkProber`
port; it writes under the author's working directory and never to the results store, which these
tools cannot even reach.

A tool names its network by the path of a `.net.xml` that another tool built. Only paths inside the
working directory are accepted, so the model cannot point a tool at any other file.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from resto.application.network_analysis import (
    MAX_SUSPECTS,
    edge_description,
    network_summary,
    sanity_report,
)
from resto.application.ports.llm import Tool
from resto.application.ports.network_probe import NetworkProber
from resto.application.ports.network_query import EnumerableNetworkQuery
from resto.application.tools.declaration import artifact_json, tool
from resto.domain.value_objects.artifact_ref import ArtifactRef

__all__ = [
    "MAX_SUSPECTS",
    "InspectionRun",
    "build_network_inspection_tools",
    "inspect_edge",
    "inspect_network",
    "probe_run",
    "sanity_check",
]


@dataclass(frozen=True, slots=True)
class InspectionRun:
    """What the inspection tools are bound to (the `ctx` the model never sees)."""

    open_network: Callable[[Path], EnumerableNetworkQuery]
    prober: NetworkProber
    out_dir: Path


_NetPath = Annotated[
    str, Field(description="Path of the .net.xml to look at, as a tool that built it returned it.")
]


def _inside(ctx: InspectionRun, net_path: str) -> Path:
    path = Path(net_path).resolve()
    if not path.is_relative_to(ctx.out_dir.resolve()):
        raise ValueError(f"{net_path!r} is outside the working directory")
    if not path.is_file():
        raise ValueError(f"{net_path!r} is not a file")
    return path


@tool(
    name="inspect_network",
    description=(
        "A bounded summary of a network: edge, junction and traffic light counts, total length, "
        "speed range, road types, vehicle classes, connected components and a short list of "
        "suspect edges (zero length, isolated, with no outgoing connection)."
    ),
)
def inspect_network(ctx: InspectionRun, net_path: _NetPath) -> Mapping[str, Any]:
    return network_summary(ctx.open_network(_inside(ctx, net_path)))


@tool(
    name="inspect_edge",
    description=(
        "One edge of a network: endpoints, length, speed, lanes, road type, allowed vehicle "
        "classes and the edges it leads to."
    ),
)
def inspect_edge(
    ctx: InspectionRun,
    net_path: _NetPath,
    edge_id: Annotated[str, Field(description="Edge id, e.g. 'A0A1'.")],
) -> Mapping[str, Any]:
    return edge_description(ctx.open_network(_inside(ctx, net_path)), edge_id)


@tool(
    name="sanity_check",
    description=(
        "Is the network sound? Returns the share of edges in the largest strongly connected "
        "component, the number of zero-length edges, whether every edge can be reached from the "
        "border, and whether the three together pass."
    ),
)
def sanity_check(ctx: InspectionRun, net_path: _NetPath) -> Mapping[str, Any]:
    report = sanity_report(ctx.open_network(_inside(ctx, net_path)))
    return {
        "largest_scc_ratio": report.largest_scc_ratio,
        "zero_length_edges": report.zero_length_edges,
        "all_reachable_from_fringe": report.all_reachable_from_fringe,
        "passes": report.passes(),
    }


@tool(
    name="probe_run",
    description=(
        "Simulate light random demand on a network with SUMO to see whether it jams. Returns "
        "teleports, collisions, vehicles that did not arrive, the edges where vehicles waited "
        "most and the SUMO statistics file as evidence. Nothing is stored as a result."
    ),
)
def probe_run(
    ctx: InspectionRun,
    net_path: _NetPath,
    seed: Annotated[int, Field(ge=0, description="Seed of the demand and of SUMO. Default 0.")] = 0,
    vehicles: Annotated[
        int, Field(ge=1, le=2000, description="Number of random trips, 1 to 2000. Default 100.")
    ] = 100,
    duration_s: Annotated[
        float, Field(ge=60, le=7200, description="Simulated seconds, 60 to 7200. Default 900.")
    ] = 900.0,
) -> Mapping[str, Any]:
    path = _inside(ctx, net_path)
    net = ArtifactRef(path, hashlib.sha256(path.read_bytes()).hexdigest(), "net")
    key = f"{net.content_hash}-{seed}-{vehicles}-{duration_s}".encode()
    run_dir = ctx.out_dir / "probes" / hashlib.sha256(key).hexdigest()[:16]
    report = ctx.prober.probe(net, seed, vehicles, duration_s, run_dir)
    return {
        "teleports": report.teleports,
        "collisions": report.collisions,
        "not_arrived": report.not_arrived,
        "hot_edges": list(report.hot_edges),
        "evidence": artifact_json(report.evidence),
    }


def build_network_inspection_tools(ctx: InspectionRun) -> tuple[Tool, ...]:
    return (
        inspect_network.bind(ctx),
        inspect_edge.bind(ctx),
        sanity_check.bind(ctx),
        probe_run.bind(ctx),
    )
