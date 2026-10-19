"""Tools that import an area of interest from OpenStreetMap (ADR-0033, ADR-0045, ADR-0046).

The agent calls `fetch_osm` (area -> snapshot, once per polygon), `netconvert` (snapshot and
profile -> a network cut to the polygon) and then the cleanups. The area and the cleanups chosen so
far live in `ImportRun`, keyed by the snapshot's `content_hash`, so the model never retypes a
polygon or a list of options. Every call that builds returns the full `netconvert_options`: those,
the `source` and the `osm_snapshot` are the recipe, and replaying them gives the same
`content_hash`.

When the user wants some streets and not a whole area, the agent works in three steps
(ADR-0046): it locates the places the user named (`locate_place`), selects the streets from the
downloaded snapshot (`list_streets`, `select_streets`, which writes a derived snapshot the recipe
replays from) and checks what it built (`verify_coverage`). For a corridor between two places,
`trace_corridor` finds the road between them and suggests the selection that keeps it, whatever
names the road takes on the way.

What the code refuses, it refuses before any download and returns as `needs_user` (the agent turns
it into a `NeedsUser`): an unsupported requirement, a place that is not a boundary, an area over the
limit. A built network with more edges than the limit is refused the same way, once `netconvert` has
counted them. A failing geocoder or Overpass raises `ExternalServiceError` and fails the step by
name.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Annotated, Any, cast
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
from resto.application.osm_map import (
    MAX_CONNECTOR_M,
    MAX_LISTED,
    MAX_SNAP_M,
    Connectors,
    NetEdge,
    OsmMap,
)
from resto.application.ports.llm import Tool
from resto.application.ports.osm import Geocoder, LocatedPlace, OsmLimits, OsmSource
from resto.application.ports.sumo import NetconvertRunner
from resto.application.tools.declaration import artifact_json, tool
from resto.domain.services.content_hash import short_hash, work_key
from resto.domain.services.geo import area_km2, bbox_around, inside_by_m, ring_of
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, PlaceName, Polygon
from resto.domain.value_objects.outcomes import AreaTooLarge, NeedsUser


@dataclass(slots=True)
class _Import:
    area: BBox | Polygon
    snapshot: ArtifactRef
    profile: str = DEFAULT_PROFILE
    cleanups: Cleanups = field(default_factory=Cleanups)
    net: ArtifactRef | None = None


@dataclass(frozen=True, slots=True)
class ImportRun:
    """What the import tools are bound to (the `ctx` the model never sees). `imports` is the state
    of one agent run: each snapshot fetched or selected, with its area, profile, cleanups and the
    last network built from it. The dataclass is frozen but `imports` is filled as the tools run:
    the model names a snapshot by hash and the tools must remember what it chose between calls,
    so the state has to live somewhere; each `obtain` builds its own `ImportRun`, so it never
    outlives or crosses a run. `located` holds the places `locate_place` found, by query, for
    `verify_coverage`."""

    runner: NetconvertRunner
    osm: OsmSource
    geocoder: Geocoder
    out_dir: Path
    typemap_dir: Path
    limits: OsmLimits = field(default_factory=OsmLimits)
    imports: dict[str, _Import] = field(default_factory=dict)
    located: dict[str, LocatedPlace] = field(default_factory=dict)


_ONE_AREA = "name the area with exactly one of bbox, polygon or place_name"

EDGE_MARGIN_M = 300.0
"""How far inside the fetched area a point must be for `trace_corridor` to trust the roads
around it: closer to the edge, the road the trace needs may have been cut off."""


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
        raise ValueError(_ONE_AREA)
    request: BBox | Polygon | PlaceName
    if bbox is not None:
        request = BBox(south=bbox[0], west=bbox[1], north=bbox[2], east=bbox[3])
    elif polygon is not None:
        request = Polygon(tuple((lat, lon) for lat, lon in polygon))
    else:
        request = PlaceName(cast("str", place_name))
    area = resolve_area(request, tuple(requirements), ctx.geocoder, ctx.limits)
    if isinstance(area, NeedsUser):
        return _needs_user(area)
    snapshot = ctx.osm.fetch(area, ctx.out_dir / "osm")
    ctx.imports[snapshot.content_hash] = _Import(area, snapshot)
    return {"source": asdict(area), "osm_snapshot": artifact_json(snapshot)}


_SNAPSHOT = Annotated[
    str,
    Field(description="`content_hash` of a snapshot `fetch_osm` or `select_streets` returned."),
]


@tool(
    name="locate_place",
    description=(
        "Find where a place or point of interest is (a hospital, a square, a station, an "
        "address), so the area you download is drawn from data and not from memory. Returns its "
        "`lat`, `lon` and what it is (`category`, `type`, `name`), or `not_found` when the "
        "geocoder does not know it: then try another wording (the official name, with the city, "
        "in Catalan or Spanish). `verify_coverage` reports how far the network ends from every "
        "place located in this run."
    ),
)
def locate_place(
    ctx: ImportRun,
    query: Annotated[
        str,
        Field(
            description=(
                "The place, with the city, e.g. 'Hospital Moisès Broggi, Sant Joan Despí' or "
                "'Plaça de Francesc Macià, Barcelona'."
            )
        ),
    ],
) -> Mapping[str, Any]:
    place = ctx.geocoder.locate(query.strip())
    if place is None:
        return {"not_found": f"the geocoder knows no place called {query!r}"}
    ctx.located[place.query] = place
    return asdict(place)


@tool(
    name="list_streets",
    description=(
        "The streets of a fetched snapshot, longest first: name, ref (e.g. 'N-340'), road "
        "classes, total length and extent. Highways with no name and no ref are grouped by "
        "class. Use it before `select_streets` to see how the streets the user named are "
        "spelled, and whether the road changes name along the stretch. With `near`, only the "
        f"streets that pass within `radius_m` of that point. At most {MAX_LISTED} rows."
    ),
)
def list_streets(
    ctx: ImportRun,
    osm_snapshot: _SNAPSHOT,
    near: Annotated[
        list[float] | None,
        Field(
            min_length=2,
            max_length=2,
            description="[lat, lon] of a point, e.g. one `locate_place` returned.",
        ),
    ] = None,
    radius_m: Annotated[
        float, Field(ge=10, le=5000, description="Radius around `near`, in metres. Default 300.")
    ] = 300.0,
) -> Mapping[str, Any]:
    osm = OsmMap.read(_state(ctx, osm_snapshot).snapshot.path)
    point = (near[0], near[1]) if near is not None else None
    streets = osm.streets(point, radius_m)
    return {"streets": streets[:MAX_LISTED], "total": len(streets)}


@tool(
    name="select_streets",
    description=(
        "Keep only some streets of a fetched snapshot, before `netconvert`: every highway whose "
        "name contains one of `names`, or whose ref is one of `refs` (a road that changes name "
        "keeps its ref), plus the `connectors` you ask for. Writes a new snapshot and returns "
        "its `osm_snapshot` and `source` for the recipe; build it with `netconvert` like any "
        "other. Also returns what was kept and in how many `pieces`: more than one means gaps "
        "a vehicle cannot cross. Fails when nothing matches; then check the names with "
        "`list_streets`. Trying another selection downloads nothing."
    ),
)
def select_streets(
    ctx: ImportRun,
    osm_snapshot: _SNAPSHOT,
    names: Annotated[
        list[str],
        Field(description="Names or parts of names, any case, e.g. ['Avinguda Diagonal']."),
    ] = [],  # noqa: B006 - never mutated; pydantic copies the default
    refs: Annotated[list[str], Field(description="Road refs, any case, e.g. ['N-340'].")] = [],  # noqa: B006 - never mutated; pydantic copies the default
    connectors: Annotated[
        Connectors,
        Field(
            description=(
                "Which other ways join the pieces of the selection: 'none'; 'links', only "
                "`*_link` ramps; 'all', any road (links, squares and crossings with another "
                f"name), at most {MAX_CONNECTOR_M:g} m long. Default 'all'."
            )
        ),
    ] = "all",
) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    key = work_key(json.dumps([osm_snapshot, sorted(names), sorted(refs), connectors]))
    selected, summary = OsmMap.read(state.snapshot.path).select(names, refs, connectors)
    derived = selected.write(ctx.out_dir / "osm" / f"selected-{key}.osm")
    ctx.imports.setdefault(derived.content_hash, _Import(state.area, derived))
    return {"source": asdict(state.area), "osm_snapshot": artifact_json(derived), **summary}


_POINT = Field(min_length=2, max_length=2, description="[lat, lon], e.g. from `locate_place`.")


@tool(
    name="trace_corridor",
    description=(
        "Find the road a car takes between two points of a fetched snapshot (the quickest, from "
        "the speed limits), and which streets to select to keep it. A road often changes name on "
        "the way, or has only a ref (a motorway): the trace follows it anyway. Returns its "
        "stretches (`route`), `total_m`, `minutes`, where each point was put on a road "
        "(`snapped`), the first and last point on the suggested streets (`joins_at`, "
        "`leaves_at`) and `suggested_selection`, to pass as it is to `select_streets`. Returns "
        "`not_reached` with the box to `fetch_osm` instead when a point is outside the fetched "
        f"area or less than {EDGE_MARGIN_M:g} m from its edge, or when no road joins the two "
        f"points (a point more than {MAX_SNAP_M:g} m from any road that does)."
    ),
)
def trace_corridor(
    ctx: ImportRun,
    osm_snapshot: _SNAPSHOT,
    from_point: Annotated[list[float], _POINT],
    to_point: Annotated[list[float], _POINT],
    prefer: Annotated[
        list[str],
        Field(
            description=(
                "Streets the user named, as names or parts of names (any case) or refs, e.g. "
                "['Avinguda Diagonal', 'B-23']: when two roads take about as long, the trace "
                "keeps to these, and the suggested selection includes the ones it touches."
            )
        ),
    ] = [],  # noqa: B006 - never mutated; pydantic copies the default
) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    area = state.area
    start, end = (from_point[0], from_point[1]), (to_point[0], to_point[1])
    for point in (start, end):
        if inside_by_m(area, point) < EDGE_MARGIN_M:
            return _not_reached(point, "outside the fetched area", area, (start, end))
    traced = OsmMap.read(state.snapshot.path).trace(start, end, prefer)
    if "not_reached" in traced:
        point = traced["not_reached"]["point"]
        return _not_reached((point[0], point[1]), "no drivable path", area, (start, end))
    return traced


def _not_reached(
    point: tuple[float, float],
    reason: str,
    area: BBox | Polygon,
    points: tuple[tuple[float, float], ...],
) -> Mapping[str, Any]:
    """The box to fetch: the points with `EDGE_MARGIN_M` around them, joined to the area."""
    around = bbox_around(points, EDGE_MARGIN_M)
    box = bbox_around([*ring_of(area), (around.south, around.west), (around.north, around.east)], 0)
    return {
        "not_reached": {
            "point": [round(point[0], 5), round(point[1], 5)],
            "reason": reason,
            "fetch": {
                "south": round(box.south, 5),
                "west": round(box.west, 5),
                "north": round(box.north, 5),
                "east": round(box.east, 5),
            },
        }
    }


def _build(ctx: ImportRun, key: str, state: _Import) -> Mapping[str, Any]:
    options = netconvert_options(
        profile_named(state.profile), state.area, ctx.typemap_dir, state.cleanups
    )
    net = ctx.runner.build(
        state.snapshot, None, options, ctx.out_dir / "imported" / short_hash(key)
    )
    state = replace(state, net=net)
    ctx.imports[key] = state
    # the edges are only known once the network is built, so the limit is checked here, for the
    # import and for every cleanup that rebuilds it
    edges = _edge_count(net.path)
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
    return _build(ctx, osm_snapshot, replace(state, profile=profile, cleanups=Cleanups()))


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


@tool(
    name="verify_coverage",
    description=(
        "Is the network you last built from a snapshot the one the user asked for? Returns its "
        "extent; its connected components with their ends; the streets of the snapshot with "
        "stretches that did not make it into the network (where they are and how long); and, "
        "for every place `locate_place` found in this run, how far the network and its nearest "
        "end are from it. Call it before you submit a network of selected streets; what it "
        "shows and you cannot fix goes to unresolved[] with its numbers."
    ),
)
def verify_coverage(ctx: ImportRun, osm_snapshot: _SNAPSHOT) -> Mapping[str, Any]:
    state = _state(ctx, osm_snapshot)
    if state.net is None:
        raise ValueError(f"nothing was built from {osm_snapshot!r}: call netconvert first")
    osm = OsmMap.read(state.snapshot.path)
    return osm.coverage(NetEdge.read_all(state.net.path), list(ctx.located.values()))


def build_network_import_tools(ctx: ImportRun) -> tuple[Tool, ...]:
    return (
        locate_place.bind(ctx),
        list_import_profiles.bind(ctx),
        fetch_osm.bind(ctx),
        list_streets.bind(ctx),
        trace_corridor.bind(ctx),
        select_streets.bind(ctx),
        netconvert.bind(ctx),
        keep_largest_component.bind(ctx),
        remove_isolated.bind(ctx),
        join_junctions.bind(ctx),
        keep_vclass.bind(ctx),
        verify_coverage.bind(ctx),
    )
