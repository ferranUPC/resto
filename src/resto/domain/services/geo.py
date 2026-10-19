"""Size of an area of interest, to refuse one too large before any download (ADR-0045 §6),
distances between points, for the coverage report (ADR-0046), and how far a point lies inside an
area, for the corridor trace (E6.1/10)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from resto.domain.value_objects.network_source import BBox, Polygon

KM_PER_DEGREE = 2 * math.pi * 6371.0 / 360.0
"""Length of one degree of latitude on a sphere of radius 6371 km."""


def ring_of(area: BBox | Polygon) -> tuple[tuple[float, float], ...]:
    """The closed (lat, lon) ring of an area; a box is its four corners."""
    if isinstance(area, Polygon):
        return area.ring
    s, w, n, e = area.south, area.west, area.north, area.east
    return ((s, w), (s, e), (n, e), (n, w), (s, w))


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Distance in metres between two (lat, lon) points, on the same local projection as
    `area_km2`: exact enough within a city."""
    x_scale = math.cos(math.radians((a[0] + b[0]) / 2))
    return 1000 * KM_PER_DEGREE * math.hypot((a[1] - b[1]) * x_scale, a[0] - b[0])


def inside_by_m(area: BBox | Polygon, point: tuple[float, float]) -> float:
    """How far `point` lies inside `area`, in metres: its distance to the border, negative when it
    is outside. On the same local projection as `distance_m`."""
    x_scale = math.cos(math.radians(point[0]))
    ring = [((lon - point[1]) * x_scale, lat - point[0]) for lat, lon in ring_of(area)]
    inside = False
    border = math.inf
    for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False):
        if (y1 > 0) != (y2 > 0) and x1 + (x2 - x1) * -y1 / (y2 - y1) > 0:
            inside = not inside
        dx, dy = x2 - x1, y2 - y1
        along = max(0.0, min(1.0, -(x1 * dx + y1 * dy) / (dx * dx + dy * dy or 1.0)))
        border = min(border, math.hypot(x1 + along * dx, y1 + along * dy))
    depth = 1000 * KM_PER_DEGREE * border
    return depth if inside else -depth


def bbox_around(points: Sequence[tuple[float, float]], margin_m: float) -> BBox:
    """The smallest box holding `points` with `margin_m` more on every side."""
    lats, lons = [p[0] for p in points], [p[1] for p in points]
    margin_lat = margin_m / (1000 * KM_PER_DEGREE)
    margin_lon = margin_lat / math.cos(math.radians(max(abs(min(lats)), abs(max(lats)))))
    return BBox(
        south=min(lats) - margin_lat,
        west=min(lons) - margin_lon,
        north=max(lats) + margin_lat,
        east=max(lons) + margin_lon,
    )


def area_km2(area: BBox | Polygon) -> float:
    """Area in km², on a local equirectangular projection at the area's mean latitude.

    Exact enough for the size limit (the error is far below 1 % for areas of tens of km)."""
    ring = ring_of(area)
    mean_lat = sum(lat for lat, _ in ring) / len(ring)
    x_scale = KM_PER_DEGREE * math.cos(math.radians(mean_lat))
    points = [(lon * x_scale, lat * KM_PER_DEGREE) for lat, lon in ring]
    twice = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False))
    return abs(twice) / 2
