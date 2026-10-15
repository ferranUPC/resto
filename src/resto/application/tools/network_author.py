"""Tools of the Network Author, declared once (ADR-0033): `find_network`, which is code, and the
generated-network tools. The rest of the catalogue (ADR-0045) lives in `network_import`,
`network_inspection` and `network_edit`.

`find_network` lists the stored networks whose label matches a name. It decides nothing: the agent
chooses between `Found`, building and `NeedsUser` from what it returns.

`generate_grid`, `generate_spider` and `generate_random` take typed parameters with SUMO's defaults
and never a free `netgenerate` option. Ranges are checked by the source dataclass, before SUMO runs,
and the `ValueError` names the parameter. Each call builds into a directory named by the source, so
the same request gives the same file and two requests never overwrite each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from resto.application.ports.llm import Tool
from resto.application.ports.repositories import NetworkRepository
from resto.application.ports.sumo import NetconvertRunner
from resto.application.tools.declaration import artifact_json, tool
from resto.domain.services.content_hash import work_key
from resto.domain.value_objects.network_source import (
    GeneratedNetwork,
    GridNetwork,
    RandomNetwork,
    SpiderNetwork,
)


@dataclass(frozen=True, slots=True)
class AuthorRun:
    """What the Network Author's tools are bound to (the `ctx` the model never sees)."""

    runner: NetconvertRunner
    out_dir: Path


@dataclass(frozen=True, slots=True)
class NetworkCatalog:
    """What `find_network` reads: the stored networks."""

    networks: NetworkRepository


def _matches(label: str, name: str) -> bool:
    """A label answers a name when either holds the other, ignoring case: "Eixample" finds
    "bcn/eixample" and a request "Eixample with the train" finds the label "eixample"."""
    label, name = label.casefold().strip(), name.casefold().strip()
    return bool(label) and bool(name) and (name in label or label in name)


@tool(
    name="find_network",
    description=(
        "List the stored networks whose label matches a name, case ignored. Returns "
        "`candidates`, each with its `network_id`, `label` and the network it `derived_from`. "
        "One candidate that is what the user means: answer Found with its id. None: build the "
        "network, or ask the user when it cannot be built. Several: ask the user which one."
    ),
)
def find_network(
    ctx: NetworkCatalog,
    name: Annotated[
        str, Field(min_length=1, description="The network reference, as the user wrote it.")
    ],
) -> Mapping[str, Any]:
    found = [
        {"network_id": n.network_id, "label": n.label, "derived_from": n.derived_from}
        for n in ctx.networks.list()
        if n.label is not None and _matches(n.label, name)
    ]
    return {"candidates": found}


def build_find_network_tool(ctx: NetworkCatalog) -> Tool:
    return find_network.bind(ctx)


def _generate(ctx: AuthorRun, source: GeneratedNetwork) -> Mapping[str, Any]:
    digest = work_key(repr(source))
    net = ctx.runner.generate(source, ctx.out_dir / "generated" / digest)
    return {
        "source": asdict(source),
        "net_artifact": artifact_json(net),
    }


@tool(
    name="generate_grid",
    description=(
        "Build a rectangular grid network with `netgenerate`, no OpenStreetMap. Returns the "
        "source to put in the recipe and the built .net.xml artifact."
    ),
)
def generate_grid(
    ctx: AuthorRun,
    x_number: Annotated[
        int, Field(ge=2, description="Junctions along x, at least 2. SUMO: 5.")
    ] = 5,
    y_number: Annotated[
        int, Field(ge=2, description="Junctions along y, at least 2. SUMO: 5.")
    ] = 5,
    x_length: Annotated[
        float, Field(gt=0, description="Length in metres of an x-direction edge. SUMO: 100.")
    ] = 100.0,
    y_length: Annotated[
        float, Field(gt=0, description="Length in metres of a y-direction edge. SUMO: 100.")
    ] = 100.0,
) -> Mapping[str, Any]:
    return _generate(ctx, GridNetwork(x_number, y_number, x_length, y_length))


@tool(
    name="generate_spider",
    description=(
        "Build a spider-web network (arms crossed by concentric circles) with `netgenerate`, no "
        "OpenStreetMap. Returns the source to put in the recipe and the built .net.xml artifact."
    ),
)
def generate_spider(
    ctx: AuthorRun,
    arm_number: Annotated[
        int, Field(ge=3, description="Number of arms, at least 3. SUMO: 13.")
    ] = 13,
    circle_number: Annotated[
        int, Field(ge=1, description="Number of circles, at least 1. SUMO: 20.")
    ] = 20,
    space_radius: Annotated[
        float, Field(gt=0, description="Distance in metres between circles. SUMO: 100.")
    ] = 100.0,
    omit_center: Annotated[
        bool, Field(description="Leave out the central junction. SUMO: false.")
    ] = False,
) -> Mapping[str, Any]:
    return _generate(ctx, SpiderNetwork(arm_number, circle_number, space_radius, omit_center))


@tool(
    name="generate_random",
    description=(
        "Build a random network with `netgenerate`, no OpenStreetMap. The seed is required: "
        "the same seed and parameters give the same network. Returns the source to put in the "
        "recipe and the built .net.xml artifact."
    ),
)
def generate_random(
    ctx: AuthorRun,
    seed: Annotated[int, Field(ge=0, description="Seed of the generator, at least 0.")],
    iterations: Annotated[
        int, Field(ge=1, description="Number of random growth steps, at least 1. SUMO: 200.")
    ] = 200,
    min_distance: Annotated[
        float, Field(gt=0, description="Minimum distance in metres between nodes. SUMO: 100.")
    ] = 100.0,
    max_distance: Annotated[
        float,
        Field(
            gt=0,
            description="Maximum distance in metres, at least min_distance. SUMO: 250.",
        ),
    ] = 250.0,
) -> Mapping[str, Any]:
    return _generate(ctx, RandomNetwork(seed, iterations, min_distance, max_distance))


def build_network_author_tools(ctx: AuthorRun) -> tuple[Tool, ...]:
    return (generate_grid.bind(ctx), generate_spider.bind(ctx), generate_random.bind(ctx))
