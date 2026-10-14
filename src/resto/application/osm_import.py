"""What the OpenStreetMap import decides in code, before the agent or `netconvert` act (ADR-0045).

- `resolve_area`: from the request to a `BBox` or `Polygon`, or a `NeedsUser` when the request
  cannot be met (unsupported requirement, place that is not a boundary, area above the size
  limit). It runs before any download.
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

from resto.application.ports.osm import Geocoder, OsmLimits, PlaceRejected
from resto.domain.services.geo import area_km2, ring_of
from resto.domain.value_objects.network_source import AreaOfInterest, BBox, PlaceName, Polygon
from resto.domain.value_objects.outcomes import (
    AreaTooLarge,
    NeedsUser,
    NetworkNotFound,
    UnsupportedRequirement,
)


@dataclass(frozen=True, slots=True)
class ImportProfile:
    """What the import keeps in the `.net.xml`: typemaps and `netconvert` options."""

    name: str
    description: str
    typemaps: tuple[str, ...]
    options: tuple[str, ...] = ()


_BASE = "osmNetconvert.typ.xml"

PROFILES: tuple[ImportProfile, ...] = (
    ImportProfile(
        "roads",
        "Roads, bicycle paths and footways as SUMO's default OSM typemap types them.",
        (_BASE,),
        ("--geometry.remove", "--roundabouts.guess"),
    ),
    ImportProfile(
        "rail",
        "Roads plus railways, trams and subways, usable in both directions (BidiRail, RailUsage).",
        (_BASE, "osmNetconvertBidiRail.typ.xml", "osmNetconvertRailUsage.typ.xml"),
        ("--geometry.remove", "--roundabouts.guess"),
    ),
    ImportProfile(
        "bicycle",
        "Roads plus bicycle lanes and tracks, with their directions.",
        (_BASE, "osmNetconvertBicycle.typ.xml"),
        ("--geometry.remove", "--roundabouts.guess", "--osm.bike-access"),
    ),
    ImportProfile(
        "pedestrian",
        "Roads plus sidewalks and crossings.",
        (_BASE, "osmNetconvertPedestrians.typ.xml"),
        ("--geometry.remove", "--roundabouts.guess", "--osm.sidewalks", "--osm.crossings"),
    ),
)

VCLASSES = (
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
)
"""Vehicle classes `keep_vclass` accepts: the ones a study can simulate."""

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
    """The `netconvert` options of an import: typemaps, profile options, the cut to `area`
    (`lon,lat` order, the reverse of Overpass), then the cleanups in a fixed order, so the same
    choices always give the same recipe."""
    typemaps = ",".join(str(typemap_dir / name) for name in profile.typemaps)
    options = ["--type-files", typemaps, *profile.options]
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
    return " ".join(f"{lon:g},{lat:g}" for lat, lon in ring_of(area))


_TRANSIT = re.compile(
    r"\b(public[ -]transport|transit|bus(es)?[ -](stops?|lines?|routes?)|tram[ -](stops?|lines?)"
    r"|metro[ -](stops?|lines?)|subway[ -](stops?|lines?)|paradas?"
    r"|l[ií]neas? de (bus|metro|tram|autob[uú]s))\b",
    re.IGNORECASE,
)


def resolve_area(
    area: AreaOfInterest,
    requirements: tuple[str, ...],
    geocoder: Geocoder,
    limits: OsmLimits,
) -> BBox | Polygon | NeedsUser:
    """The area to import, or the `NeedsUser` that says why it cannot be. Never downloads.

    Raises `ExternalServiceError` when the geocoder fails: the user cannot fix that."""
    for requirement in requirements:
        if _TRANSIT.search(requirement):
            return NeedsUser(
                reason=UnsupportedRequirement(requirement),
                message=(
                    f"The request needs {requirement!r}, but public transport stops and lines are "
                    "not part of the network file the import produces."
                ),
            )
    if isinstance(area, PlaceName):
        try:
            area = geocoder.resolve(area)
        except PlaceRejected as rejected:
            return NeedsUser(
                reason=NetworkNotFound(rejected.query),
                message=f"The place {rejected.query!r} cannot be imported: {rejected.reason}.",
                advice=("Give a bounding box or a polygon for an area that has no boundary.",),
            )
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
