"""What the OpenStreetMap import decides in code, before the agent or `netconvert` act (ADR-0045).

- `resolve_area`: from the request to a `BBox` or `Polygon`, or a `NeedsUser` when the request
  cannot be met (unsupported requirement, place that is not a boundary, area above the size
  limit). It runs before any download; `unsupported_requirement` is its first check alone, for a
  road whose area is known only after its line is downloaded.
- The catalogue of import profiles and the `netconvert` options an import is built with: the
  profile, the cut to the polygon, and the cleanups. The options are what the recipe stores, so
  they are a pure function of the profile, the area and the cleanups.

Typemaps are named here and resolved against a directory the caller gives (the SUMO package, by
absolute path), so this module needs no SUMO and no `SUMO_HOME`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from resto.application.ports.osm import Geocoder, OsmLimits, PlaceRejected
from resto.domain.services.geo import area_km2, expand_area, format_coordinate, ring_of
from resto.domain.value_objects.network_source import AreaOfInterest, BBox, PlaceName, Polygon
from resto.domain.value_objects.outcomes import (
    AreaTooLarge,
    NeedsUser,
    PlaceNotBoundary,
    UnsupportedRequirement,
)


@dataclass(frozen=True, slots=True)
class ImportProfile:
    """What the import keeps in the `.net.xml`: typemaps and `netconvert` options. `typemaps` are
    resolved against the directory the caller gives (SUMO's); `own_typemaps` against `OWN_TYPEMAPS`
    and come last, so they override SUMO's."""

    name: str
    description: str
    typemaps: tuple[str, ...]
    options: tuple[str, ...] = ()
    own_typemaps: tuple[str, ...] = ()


_BASE = "osmNetconvert.typ.xml"
OWN_TYPEMAPS = Path(__file__).resolve().parent / "typemaps"
_SERVICE_ROADS = ("restoServiceRoads.typ.xml",)

PROFILES: tuple[ImportProfile, ...] = (
    ImportProfile(
        "roads",
        "Roads, bicycle paths and footways as SUMO types them. Service streets (campuses, "
        "industrial parks) are open to cars; driveways and parking aisles are not.",
        (_BASE,),
        ("--geometry.remove", "--roundabouts.guess"),
        _SERVICE_ROADS,
    ),
    ImportProfile(
        "rail",
        "Roads plus railways, trams and subways, usable in both directions (BidiRail, RailUsage).",
        (_BASE, "osmNetconvertBidiRail.typ.xml", "osmNetconvertRailUsage.typ.xml"),
        ("--geometry.remove", "--roundabouts.guess"),
        _SERVICE_ROADS,
    ),
    ImportProfile(
        "bicycle",
        "Roads plus bicycle lanes and tracks, with their directions.",
        (_BASE, "osmNetconvertBicycle.typ.xml"),
        ("--geometry.remove", "--roundabouts.guess", "--osm.bike-access"),
        _SERVICE_ROADS,
    ),
    ImportProfile(
        "pedestrian",
        "Roads plus sidewalks and crossings.",
        (_BASE, "osmNetconvertPedestrians.typ.xml"),
        ("--geometry.remove", "--roundabouts.guess", "--osm.sidewalks", "--osm.crossings"),
        _SERVICE_ROADS,
    ),
)

VClass = Literal[
    "passenger",
    "bus",
    "truck",
    "delivery",
    "taxi",
    "motorcycle",
    "bicycle",
    "pedestrian",
    "tram",
    "rail",
]
"""Vehicle classes `keep_vclass` accepts: the ones a study can simulate."""

VCLASSES: tuple[str, ...] = get_args(VClass)

DEFAULT_PROFILE = PROFILES[0].name


def profile_named(name: str) -> ImportProfile:
    for profile in PROFILES:
        if profile.name == name:
            return profile
    raise ValueError(f"unknown import profile {name!r}; choose one of {[p.name for p in PROFILES]}")


@dataclass(frozen=True, slots=True)
class Cleanups:
    """Which cleanups a build applies. The largest component is kept unless turned off, because
    the cut to the polygon can leave pieces that join nothing (ADR-0045 §8)."""

    largest_component: bool = True
    remove_isolated: bool = False
    join_junctions: bool = False
    vclass: str | None = None


def netconvert_options(
    profile: ImportProfile, area: BBox | Polygon, typemap_dir: Path, cleanups: Cleanups
) -> tuple[str, ...]:
    """The `netconvert` options of an import: typemaps, profile options, the OSM ways each edge
    comes from (`--output.original-names`, read by the coverage report, ADR-0046), the cut to
    `area` (`lon,lat` order, the reverse of Overpass), then the cleanups in a fixed order, so the
    same choices always give the same recipe."""
    typemaps = ",".join(
        [str(typemap_dir / name) for name in profile.typemaps]
        + [str(OWN_TYPEMAPS / name) for name in profile.own_typemaps]
    )
    options = ["--type-files", typemaps, *profile.options, "--output.original-names"]
    options += ["--keep-edges.in-geo-boundary", _boundary(area)]
    if cleanups.largest_component:
        options += ["--keep-edges.components", "1"]
    if cleanups.remove_isolated:
        options += ["--remove-edges.isolated"]
    if cleanups.join_junctions:
        options += ["--junctions.join"]
    if cleanups.vclass:
        options += ["--keep-edges.by-vclass", cleanups.vclass]
    return tuple(options)


def _boundary(area: BBox | Polygon) -> str:
    return " ".join(
        f"{format_coordinate(lon)},{format_coordinate(lat)}" for lat, lon in ring_of(area)
    )


DEFAULT_MARGIN_PCT = 5.0
"""Margin of an import when the caller names none (ADR-0049): a boundary often runs along the axis
of a street, and the street must not sit on the edge of the cut."""

_TRANSIT = re.compile(
    r"\b(public[ -]transport|transit|bus(es)?[ -](stops?|lines?|routes?)|tram[ -](stops?|lines?)"
    r"|metro[ -](stops?|lines?)|subway[ -](stops?|lines?)|paradas?"
    r"|l[ií]neas? de (bus|metro|tram|autob[uú]s))\b",
    re.IGNORECASE,
)


def unsupported_requirement(requirements: tuple[str, ...]) -> NeedsUser | None:
    """The `NeedsUser` for the first requirement no import can meet (public transport stops and
    lines, ADR-0045 §5), or None."""
    for requirement in requirements:
        if _TRANSIT.search(requirement):
            return NeedsUser(
                reason=UnsupportedRequirement(requirement),
                message=(
                    f"The request needs {requirement!r}, but public transport stops and lines are "
                    "not part of the network file the import produces."
                ),
            )
    return None


def resolve_area(
    area: AreaOfInterest,
    requirements: tuple[str, ...],
    geocoder: Geocoder,
    limits: OsmLimits,
    margin_pct: float = DEFAULT_MARGIN_PCT,
) -> BBox | Polygon | NeedsUser:
    """The area to import grown by `margin_pct` (see `expand_area`), or the `NeedsUser` that says
    why it cannot be. The size limit is checked on the grown area, the one that is downloaded.
    Never downloads.

    Raises `ExternalServiceError` when the geocoder fails: the user cannot fix that."""
    unsupported = unsupported_requirement(requirements)
    if unsupported is not None:
        return unsupported
    if isinstance(area, PlaceName):
        try:
            area = geocoder.resolve(area)
        except PlaceRejected as rejected:
            return NeedsUser(
                reason=PlaceNotBoundary(rejected.query),
                message=f"The place {rejected.query!r} cannot be imported: {rejected.reason}.",
            )
    area = expand_area(area, margin_pct)
    size = area_km2(area)
    if size > limits.max_area_km2:
        return NeedsUser(
            reason=AreaTooLarge(area_km2=size, limit_km2=limits.max_area_km2),
            message=(
                f"The area is {size:.1f} km², above the limit of {limits.max_area_km2:g} km² for "
                "one import. Nothing was downloaded."
            ),
        )
    return area
