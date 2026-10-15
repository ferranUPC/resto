"""Where a network comes from (ADR-0045): an area of interest cut out of OpenStreetMap, or a
generated pattern that needs no OpenStreetMap. A discriminated union of small dataclasses.

Coordinates are (latitude, longitude) in degrees. `PlaceName` is a request, not a recipe value: a
geocoder resolves it once to a `Polygon` (with its `osm_id`) and the recipe stores that."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MAX_POLYGON_VERTICES = 200
"""Vertices of a `Polygon`, not counting the closing one; keeps the Overpass filter short."""


def _check_latitude(value: float, name: str) -> None:
    if not -90.0 <= value <= 90.0:
        raise ValueError(f"{name} latitude must be within [-90, 90]")


def _check_longitude(value: float, name: str) -> None:
    if not -180.0 <= value <= 180.0:
        raise ValueError(f"{name} longitude must be within [-180, 180]")


@dataclass(frozen=True, slots=True)
class BBox:
    south: float
    west: float
    north: float
    east: float
    kind: Literal["bbox"] = "bbox"

    def __post_init__(self) -> None:
        _check_latitude(self.south, "south")
        _check_latitude(self.north, "north")
        _check_longitude(self.west, "west")
        _check_longitude(self.east, "east")
        if self.south >= self.north:
            raise ValueError("south must be below north")
        if self.west >= self.east:
            raise ValueError("west must be below east")


@dataclass(frozen=True, slots=True)
class Polygon:
    """A closed ring of (lat, lon) points. `osm_id` is the OpenStreetMap relation it was resolved
    from, when a geocoder produced it."""

    ring: tuple[tuple[float, float], ...]
    osm_id: int | None = None
    kind: Literal["polygon"] = "polygon"

    def __post_init__(self) -> None:
        if len(self.ring) < 2 or self.ring[0] != self.ring[-1]:
            raise ValueError("a Polygon ring must be closed: the last point repeats the first")
        vertices = len(self.ring) - 1
        if vertices < 3:
            raise ValueError("a Polygon needs at least 3 vertices")
        if vertices > MAX_POLYGON_VERTICES:
            raise ValueError(f"a Polygon has at most {MAX_POLYGON_VERTICES} vertices")
        for lat, lon in self.ring:
            _check_latitude(lat, "ring")
            _check_longitude(lon, "ring")
        if self.osm_id is not None and self.osm_id <= 0:
            raise ValueError("osm_id must be positive when given")


@dataclass(frozen=True, slots=True)
class PlaceName:
    """A name for the geocoder to resolve to a `Polygon`. Never stored in a recipe."""

    query: str
    kind: Literal["place_name"] = "place_name"

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("a PlaceName requires a non-blank query")


@dataclass(frozen=True, slots=True)
class GridNetwork:
    """`netgenerate --grid`; defaults and ranges follow SUMO's."""

    x_number: int = 5
    y_number: int = 5
    x_length: float = 100.0
    y_length: float = 100.0
    kind: Literal["grid"] = "grid"

    def __post_init__(self) -> None:
        if self.x_number < 2:
            raise ValueError("x_number must be >= 2")
        if self.y_number < 2:
            raise ValueError("y_number must be >= 2")
        if self.x_length <= 0:
            raise ValueError("x_length must be positive (m)")
        if self.y_length <= 0:
            raise ValueError("y_length must be positive (m)")


@dataclass(frozen=True, slots=True)
class SpiderNetwork:
    """`netgenerate --spider`; defaults and ranges follow SUMO's."""

    arm_number: int = 13
    circle_number: int = 20
    space_radius: float = 100.0
    omit_center: bool = False
    kind: Literal["spider"] = "spider"

    def __post_init__(self) -> None:
        if self.arm_number < 3:
            raise ValueError("arm_number must be >= 3")
        if self.circle_number < 1:
            raise ValueError("circle_number must be >= 1")
        if self.space_radius <= 0:
            raise ValueError("space_radius must be positive (m)")


@dataclass(frozen=True, slots=True)
class RandomNetwork:
    """`netgenerate --rand`. The seed is required: asking again gives the same network."""

    seed: int
    iterations: int = 200
    min_distance: float = 100.0
    max_distance: float = 250.0
    kind: Literal["rand"] = "rand"

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be >= 0")
        if self.iterations < 1:
            raise ValueError("iterations must be >= 1")
        if self.min_distance <= 0:
            raise ValueError("min_distance must be positive (m)")
        if self.max_distance < self.min_distance:
            raise ValueError("max_distance must be >= min_distance")


AreaOfInterest = BBox | Polygon | PlaceName
GeneratedNetwork = GridNetwork | SpiderNetwork | RandomNetwork
NetworkSource = AreaOfInterest | GeneratedNetwork
