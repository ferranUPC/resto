"""Size of an area of interest, to refuse one too large before any download (ADR-0045 §6)."""

from __future__ import annotations

import math

from resto.domain.value_objects.network_source import BBox, Polygon

KM_PER_DEGREE = 2 * math.pi * 6371.0 / 360.0
"""Length of one degree of latitude on a sphere of radius 6371 km."""


def ring_of(area: BBox | Polygon) -> tuple[tuple[float, float], ...]:
    """The closed (lat, lon) ring of an area; a box is its four corners."""
    if isinstance(area, Polygon):
        return area.ring
    s, w, n, e = area.south, area.west, area.north, area.east
    return ((s, w), (s, e), (n, e), (n, w), (s, w))


def area_km2(area: BBox | Polygon) -> float:
    """Area in km², on a local equirectangular projection at the area's mean latitude.

    Exact enough for the size limit (the error is far below 1 % for areas of tens of km)."""
    ring = ring_of(area)
    mean_lat = sum(lat for lat, _ in ring) / len(ring)
    x_scale = KM_PER_DEGREE * math.cos(math.radians(mean_lat))
    points = [(lon * x_scale, lat * KM_PER_DEGREE) for lat, lon in ring]
    twice = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False))
    return abs(twice) / 2
