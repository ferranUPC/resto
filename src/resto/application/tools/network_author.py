"""Tools of the Network Author, declared once (ADR-0033). This slice holds the generated-network
tools; the rest of the catalogue (ADR-0045) joins as its slices land.

`generate_grid`, `generate_spider` and `generate_random` take typed parameters with SUMO's defaults
and never a free `netgenerate` option. Ranges are checked by the source dataclass, before SUMO runs,
and the `ValueError` names the parameter. Each call builds into a directory named by the source, so
the same request gives the same file and two requests never overwrite each other.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from resto.application.ports.llm import Tool
from resto.application.ports.sumo import NetconvertRunner
from resto.application.tools.declaration import tool
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


def _generate(ctx: AuthorRun, source: GeneratedNetwork) -> Mapping[str, Any]:
    digest = hashlib.sha256(repr(source).encode()).hexdigest()[:16]
    net = ctx.runner.generate(source, ctx.out_dir / "generated" / digest)
    return {
        "source": asdict(source),
        "net_artifact": {
            "path": str(net.path),
            "content_hash": net.content_hash,
            "kind": net.kind,
        },
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
