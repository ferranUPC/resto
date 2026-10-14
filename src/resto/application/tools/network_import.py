"""Tools that import an area of interest from OpenStreetMap (ADR-0033, ADR-0045).

The agent calls `fetch_osm` (area -> snapshot, once per polygon), `netconvert` (snapshot and
profile -> a network cut to the polygon) and then the cleanups. The area and the cleanups chosen so
far live in `ImportRun`, keyed by the snapshot's `content_hash`, so the model never retypes a
polygon or a list of options. Every call that builds returns the full `netconvert_options`: those,
the `source` and the `osm_snapshot` are the recipe, and replaying them gives the same
`content_hash`.

What the code refuses, it refuses before any download and returns as `needs_user` (the agent turns
it into a `NeedsUser`): an unsupported requirement, a place that is not a boundary, an area over the
limit. A built network with more edges than the limit is refused the same way, once `netconvert` has
counted them. A failing geocoder or Overpass raises `ExternalServiceError` and fails the step by
name.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Annotated, Any
from xml.etree import ElementTree

from pydantic import Field

from resto.application.osm_import import (
    DEFAULT_PROFILE,
    PROFILES,
    VCLASSES,
    Cleanups,
    VClass,
    netconvert_options,
    profile_named,
    resolve_area,
)
from resto.application.ports.llm import Tool
from resto.application.ports.osm import Geocoder, OsmLimits, OsmSource
from resto.application.ports.sumo import NetconvertRunner
from resto.application.tools.declaration import artifact_json, tool
from resto.domain.services.geo import area_km2
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, PlaceName, Polygon
from resto.domain.value_objects.outcomes import AreaTooLarge, NeedsUser


@dataclass(slots=True)
class _Import:
    area: BBox | Polygon
    snapshot: ArtifactRef
    profile: str = DEFAULT_PROFILE
    cleanups: Cleanups = field(default_factory=Cleanups)


@dataclass(frozen=True, slots=True)
class ImportRun:
    """What the import tools are bound to (the `ctx` the model never sees). `imports` is the state
    of one agent run: each snapshot fetched, with its area, profile and cleanups. The dataclass is
    frozen but `imports` is filled as the tools run: the model names a snapshot by hash and the
    tools must remember what it chose between calls, so the state has to live somewhere; each
    `obtain` builds its own `ImportRun`, so it never outlives or crosses a run."""

    runner: NetconvertRunner
    osm: OsmSource
    geocoder: Geocoder
    out_dir: Path
    typemap_dir: Path
    limits: OsmLimits = field(default_factory=OsmLimits)
    imports: dict[str, _Import] = field(default_factory=dict)


def _needs_user(needs: NeedsUser) -> Mapping[str, Any]:
    return {
        "needs_user": {
            "reason": asdict(needs.reason),
            "message": needs.message,
            "candidates": list(needs.candidates),
            "recommendations": list(needs.recommendations),
        }
    }


@tool(
    name="list_import_profiles",
    description=(
        "List the import profiles `netconvert` can use (what the imported network keeps: roads, "
        "rail, bicycle lanes, pedestrian paths) and the vehicle classes `keep_vclass` accepts. "
        "Public transport stops and lines and polygons are not part of any profile."
    ),
)
def list_import_profiles(ctx: ImportRun) -> Mapping[str, Any]:
    return {
        "profiles": [{"name": p.name, "description": p.description} for p in PROFILES],
        "vclasses": list(VCLASSES),
    }


@tool(
    name="fetch_osm",
    description=(
        "Download the OpenStreetMap data of an area of interest, once per polygon (a second call "
        "for the same area reuses the stored snapshot). Name the area with exactly one of `bbox`, "
        "`polygon` or `place_name` (an administrative boundary, resolved to a polygon). Put any "
        "extra thing the user asked for in `requirements`, for example 'bus stops'. Returns the "
        "`source` and the `osm_snapshot` for the recipe, or `needs_user` when the area is above "
        "the size limit, the place is not a boundary, or a requirement is unsupported (public "
        "transport stops and lines); then nothing was downloaded."
    ),
)
def fetch_osm(
    ctx: ImportRun,
    bbox: Annotated[
        list[float] | None,
        Field(
            min_length=4,
            max_length=4,
            description="[south, west, north, east] in degrees.",
        ),
    ] = None,
    polygon: Annotated[
        list[list[float]] | None,
        Field(description="Closed ring of [lat, lon] points, at most about 200 vertices."),
    ] = None,
    place_name: Annotated[
        str | None, Field(description="Name of an administrative area, e.g. 'Sant Antoni'.")
    ] = None,
    requirements: Annotated[
        list[str],
        Field(description="What else the user asked for, in their words, e.g. ['bus stops']."),
    ] = [],  # noqa: B006 - never mutated; pydantic copies the default
) -> Mapping[str, Any]:
    named = [x for x in (bbox, polygon, place_name) if x is not None]
    if len(named) != 1:
        raise ValueError("name the area with exactly one of bbox, polygon or place_name")
    request: BBox | Polygon | PlaceName
    if bbox is not None:
        request = BBox(south=bbox[0], west=bbox[1], north=bbox[2], east=bbox[3])
    elif polygon is not None:
        request = Polygon(tuple((lat, lon) for lat, lon in polygon))
    else:
        assert place_name is not None
        request = PlaceName(place_name)
    area = resolve_area(request, tuple(requirements), ctx.geocoder, ctx.limits)
    if isinstance(area, NeedsUser):
        return _needs_user(area)
    snapshot = ctx.osm.fetch(area, ctx.out_dir / "osm")
    ctx.imports[snapshot.content_hash] = _Import(area, snapshot)
    return {"source": asdict(area), "osm_snapshot": artifact_json(snapshot)}


def _build(ctx: ImportRun, key: str, state: _Import) -> Mapping[str, Any]:
    options = netconvert_options(
        profile_named(state.profile), state.area, ctx.typemap_dir, state.cleanups
    )
    net = ctx.runner.build(state.snapshot, None, options, ctx.out_dir / "imported" / key[:16])
    ctx.imports[key] = state
    return {
        "source": asdict(state.area),
        "osm_snapshot": artifact_json(state.snapshot),
        "netconvert_options": list(options),
        "net_artifact": artifact_json(net),
    }


def _edge_count(net_xml: Path) -> int:
    """Edges of a `.net.xml`, not counting the internal ones junctions add."""
    return sum(
        1
        for _, element in ElementTree.iterparse(net_xml)
        if element.tag == "edge" and element.get("function") != "internal"
    )


def _state(ctx: ImportRun, osm_snapshot: str) -> _Import:
    state = ctx.imports.get(osm_snapshot)
    if state is None:
        raise ValueError(f"no snapshot {osm_snapshot!r} in this run: call fetch_osm first")
    return state


_SNAPSHOT = Annotated[
    str, Field(description="`content_hash` of the snapshot `fetch_osm` returned.")
]


@tool(
    name="netconvert",
    description=(
        "Build the network from a fetched snapshot with `netconvert`: the chosen import profile, "
        "cut to the area's polygon, keeping the largest connected component. Starts the cleanups "
        "again. Returns the `netconvert_options` and `net_artifact` for the recipe, or "
        "`needs_user` when the network has more edges than one import allows."
    ),
)
def netconvert(
    ctx: ImportRun,
    osm_snapshot: _SNAPSHOT,
    profile: Annotated[
        str, Field(description="Profile name from `list_import_profiles`. Default 'roads'.")
    ] = DEFAULT_PROFILE,
) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    profile_named(profile)
    built = _build(ctx, osm_snapshot, replace(state, profile=profile, cleanups=Cleanups()))
    # the edges are only known once the network is built, so the limit is checked here
    edges = _edge_count(Path(built["net_artifact"]["path"]))
    if edges > ctx.limits.max_edges:
        return _needs_user(
            NeedsUser(
                reason=AreaTooLarge(
                    area_km2=area_km2(state.area),
                    limit_km2=ctx.limits.max_area_km2,
                    edges=edges,
                    limit_edges=ctx.limits.max_edges,
                ),
                message=(
                    f"The network has {edges} edges, above the limit of {ctx.limits.max_edges} "
                    "for one import."
                ),
            )
        )
    return built


@tool(
    name="keep_largest_component",
    description=(
        "Rebuild keeping only the largest connected component, so no piece of road is cut off "
        "from the rest. `netconvert` already does it; this makes the choice explicit after other "
        "cleanups. Returns the updated options."
    ),
)
def keep_largest_component(ctx: ImportRun, osm_snapshot: _SNAPSHOT) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    cleanups = replace(state.cleanups, largest_component=True)
    return _build(ctx, osm_snapshot, replace(state, cleanups=cleanups))


@tool(
    name="remove_isolated",
    description="Rebuild removing isolated edges (edges that connect to nothing at either end).",
)
def remove_isolated(ctx: ImportRun, osm_snapshot: _SNAPSHOT) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    cleanups = replace(state.cleanups, remove_isolated=True)
    return _build(ctx, osm_snapshot, replace(state, cleanups=cleanups))


@tool(
    name="join_junctions",
    description=(
        "Rebuild joining junctions that are close together (a big crossing mapped as several "
        "nodes) into one."
    ),
)
def join_junctions(ctx: ImportRun, osm_snapshot: _SNAPSHOT) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    cleanups = replace(state.cleanups, join_junctions=True)
    return _build(ctx, osm_snapshot, replace(state, cleanups=cleanups))


@tool(
    name="keep_vclass",
    description=(
        "Rebuild keeping only the edges that allow a vehicle class, for example 'passenger' to "
        "drop rail and pedestrian-only paths."
    ),
)
def keep_vclass(
    ctx: ImportRun,
    osm_snapshot: _SNAPSHOT,
    vclass: Annotated[
        VClass,
        Field(description="Vehicle class to keep."),
    ],
) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    cleanups = replace(state.cleanups, vclass=vclass)
    return _build(ctx, osm_snapshot, replace(state, cleanups=cleanups))


def build_network_import_tools(ctx: ImportRun) -> tuple[Tool, ...]:
    return (
        list_import_profiles.bind(ctx),
        fetch_osm.bind(ctx),
        netconvert.bind(ctx),
        keep_largest_component.bind(ctx),
        remove_isolated.bind(ctx),
        join_junctions.bind(ctx),
        keep_vclass.bind(ctx),
    )
