"""Size of an area of interest, to refuse one too large before any download (ADR-0045 §6),
distances between points, for the coverage report (ADR-0046), and how far a point lies inside an
area, for the corridor trace (E6.1/10), and an area grown by a margin, so the import keeps whole the
streets along its edge (E6.1/14)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from resto.domain.value_objects.network_source import BBox, Polygon

KM_PER_DEGREE = 2 * math.pi * 6371.0 / 360.0
"""Length of one degree of latitude on a sphere of radius 6371 km."""

MAX_MARGIN_PCT = 50.0
"""The largest margin `expand_area` accepts, in percent of a square's side."""

COORDINATE_DECIMALS = 7
"""Decimals of a degree kept in a coordinate: about 1 cm, so a point is never moved by rounding."""


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


def expand_area(area: BBox | Polygon, margin_pct: float) -> BBox | Polygon:
    """`area` grown outwards by `margin_pct` percent of the side of a square of its surface, in
    metres, so the margin does not depend on the orientation or the shape.

    A box stays a box with every side moved by the margin. A polygon becomes its convex hull moved
    outwards by the margin: it never crosses itself, and every original point ends at least the
    margin from the new border."""
    if not 0 <= margin_pct <= MAX_MARGIN_PCT:
        raise ValueError(f"margin_pct must be within [0, {MAX_MARGIN_PCT:g}]")
    if margin_pct == 0:
        return area
    margin_m = margin_pct / 100 * 1000 * math.sqrt(area_km2(area))
    margin_lat = margin_m / (1000 * KM_PER_DEGREE)
    if isinstance(area, BBox):
        margin_lon = margin_lat / math.cos(math.radians((area.south + area.north) / 2))
        return BBox(
            south=max(-90.0, _round_coordinate(area.south - margin_lat)),
            west=max(-180.0, _round_coordinate(area.west - margin_lon)),
            north=min(90.0, _round_coordinate(area.north + margin_lat)),
            east=min(180.0, _round_coordinate(area.east + margin_lon)),
        )
    mean_lat = sum(lat for lat, _ in area.ring) / len(area.ring)
    x_scale = math.cos(math.radians(mean_lat))
    # degrees with longitude shrunk by the latitude: a metric plane up to one constant
    hull = _convex_hull([(lon * x_scale, lat) for lat, lon in area.ring[:-1]])
    grown = _offset(hull, margin_lat)
    ring = tuple((_round_coordinate(y), _round_coordinate(x / x_scale)) for x, y in grown)
    return Polygon(ring=(*ring, ring[0]), osm_id=area.osm_id)


def format_coordinate(degrees: float) -> str:
    """A coordinate as text with up to `COORDINATE_DECIMALS` decimals and no exponent, for the
    queries and options that carry an area; `:g` would keep only six significant digits."""
    return f"{degrees:.{COORDINATE_DECIMALS}f}".rstrip("0").rstrip(".")


def _round_coordinate(degrees: float) -> float:
    return round(degrees, COORDINATE_DECIMALS)


def _cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _convex_hull(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Counter-clockwise hull without repeated or collinear points (Andrew's monotone chain)."""
    ordered = sorted(set(points))
    if len(ordered) < 3:
        raise ValueError("a polygon needs at least 3 distinct points to be grown")
    chains: list[list[tuple[float, float]]] = []
    for sequence in (ordered, ordered[::-1]):
        chain: list[tuple[float, float]] = []
        for point in sequence:
            while len(chain) >= 2 and _cross(chain[-2], chain[-1], point) <= 0:
                chain.pop()
            chain.append(point)
        chains.append(chain[:-1])
    hull = chains[0] + chains[1]
    if len(hull) < 3:
        raise ValueError("a polygon whose points are all on one line cannot be grown")
    return hull


def _offset(hull: Sequence[tuple[float, float]], distance: float) -> list[tuple[float, float]]:
    """The counter-clockwise convex `hull` with every edge moved `distance` outwards; each corner
    is where the two moved edges meet."""
    count = len(hull)
    moved: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i in range(count):
        (x1, y1), (x2, y2) = hull[i], hull[(i + 1) % count]
        length = math.hypot(x2 - x1, y2 - y1)
        nx, ny = (y2 - y1) / length, -(x2 - x1) / length  # outwards for a counter-clockwise ring
        moved.append(
            ((x1 + nx * distance, y1 + ny * distance), (x2 + nx * distance, y2 + ny * distance))
        )
    corners = []
    for i in range(count):
        (ax, ay), (bx, by) = moved[i - 1]
        (cx, cy), (dx, dy) = moved[i]
        d1x, d1y, d2x, d2y = bx - ax, by - ay, dx - cx, dy - cy
        along = ((cx - ax) * d2y - (cy - ay) * d2x) / (d1x * d2y - d1y * d2x)
        corners.append((ax + d1x * along, ay + d1y * along))
    return corners
