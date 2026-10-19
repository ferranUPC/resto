"""Nominatim geocoder: a place name to the polygon of its administrative boundary (ADR-0045 §2),
or a place of any kind to a point (ADR-0046).

Follows the public usage policy: at most one request per second, a User-Agent that identifies the
application, and results cached so a name is asked once."""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from resto.adapters.osm.http import DEFAULT_USER_AGENT, request
from resto.application.ports.osm import ExternalServiceError, LocatedPlace, PlaceRejected
from resto.domain.value_objects.network_source import MAX_POLYGON_VERTICES, PlaceName, Polygon

SERVICE = "nominatim"
DEFAULT_BASE_URL = "https://nominatim.openstreetmap.org"
DEFAULT_MIN_INTERVAL_S = 1.0
DEFAULT_TIMEOUT_S = 30.0

_Ring = list[tuple[float, float]]  # (lon, lat), as GeoJSON


class NominatimGeocoder:
    """`Geocoder` over the Nominatim search API. `cache_dir` holds one JSON file per normalised
    query and kind of answer (boundary or point); only successful answers are cached."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._cache_dir = cache_dir
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self.min_interval_s = min_interval_s
        self._timeout_s = timeout_s
        self._lock = threading.Lock()
        self._last_request_at: float | None = None

    def resolve(self, place: PlaceName) -> Polygon:
        cache_file = self._cache_file(self._cache_dir, place.query)
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
            return Polygon(tuple((lat, lon) for lat, lon in cached["ring"]), cached["osm_id"])
        results = self._search({"q": place.query, "polygon_geojson": 1})
        polygon = _polygon_of(place.query, results)
        self._store(cache_file, {"osm_id": polygon.osm_id, "ring": [list(p) for p in polygon.ring]})
        return polygon

    def locate(self, query: str) -> LocatedPlace | None:
        cache_file = self._cache_file(self._cache_dir / "points", query)
        if cache_file.exists():
            # the cache key ignores case and spacing; the answer names the query as asked
            return LocatedPlace(**{**json.loads(cache_file.read_text()), "query": query})
        results = self._search({"q": query})
        if not results:
            return None
        top = results[0]
        try:
            place = LocatedPlace(
                query=query,
                lat=float(top["lat"]),
                lon=float(top["lon"]),
                category=str(top.get("category") or top.get("class") or ""),
                type=str(top.get("type") or ""),
                name=str(top.get("name") or top.get("display_name") or ""),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ExternalServiceError(SERVICE, "a result has no usable lat and lon") from e
        self._store(cache_file, asdict(place))
        return place

    def _cache_file(self, folder: Path, query: str) -> Path:
        """Boundaries sit at the top of the cache, where earlier runs stored them; points under
        `points/`, so the same name can hold both."""
        key = hashlib.sha256(" ".join(query.lower().split()).encode()).hexdigest()
        return folder / f"{key}.json"

    def _store(self, cache_file: Path, answer: dict[str, Any]) -> None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(answer))

    def _search(self, params: dict[str, Any]) -> list[Any]:
        """The results of one search, best first, at most one."""
        query = urlencode({**params, "format": "jsonv2", "limit": 1})
        with self._lock:  # one request at a time, spaced by the minimum interval
            self._wait_turn()
            try:
                body = request(
                    SERVICE,
                    f"{self._base_url}/search?{query}",
                    user_agent=self._user_agent,
                    timeout_s=self._timeout_s,
                )
            finally:
                self._last_request_at = time.monotonic()
        try:
            results = json.loads(body)
        except ValueError as e:
            raise ExternalServiceError(SERVICE, "the answer is not JSON") from e
        if not isinstance(results, list):
            raise ExternalServiceError(SERVICE, "the answer is not a list of results")
        return results

    def _wait_turn(self) -> None:
        if self._last_request_at is None:
            return
        remaining = self._last_request_at + self.min_interval_s - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)


def _polygon_of(query: str, results: list[Any]) -> Polygon:
    if not results:
        raise PlaceRejected(query, "no result: Nominatim does not know this place")
    top = results[0]
    osm_type, category = top.get("osm_type"), top.get("category") or top.get("class")
    if osm_type != "relation" or category != "boundary":
        raise PlaceRejected(
            query,
            f"the best match is a {osm_type} of category {category!r}, not a boundary relation; "
            "name an administrative area or give a bounding box",
        )
    geometry = top.get("geojson") or {}
    rings = _outer_rings(geometry)
    if not rings:
        raise PlaceRejected(query, "the boundary has no polygon geometry")
    ring = max(rings, key=_area)
    ring = _simplify_to_limit(ring)
    return Polygon(tuple((lat, lon) for lon, lat in ring), osm_id=int(top["osm_id"]))


def _outer_rings(geometry: dict[str, Any]) -> list[_Ring]:
    kind, coordinates = geometry.get("type"), geometry.get("coordinates") or []
    polygons: list[Any]
    if kind == "Polygon":
        polygons = [coordinates]
    elif kind == "MultiPolygon":
        polygons = coordinates
    else:
        return []
    return [[(float(x), float(y)) for x, y in polygon[0]] for polygon in polygons]


def _area(ring: _Ring) -> float:
    """Absolute shoelace area, in square degrees; only used to rank the parts of a boundary."""
    return (
        abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:], strict=False))) / 2
    )


def _simplify_to_limit(ring: _Ring) -> _Ring:
    """Douglas-Peucker with a growing tolerance until the ring fits `MAX_POLYGON_VERTICES`."""
    if len(ring) - 1 <= MAX_POLYGON_VERTICES:
        return ring
    tolerance = 1e-6
    while True:
        simplified = _douglas_peucker(ring[:-1], tolerance)
        if len(simplified) <= MAX_POLYGON_VERTICES:
            return [*simplified, simplified[0]]
        tolerance *= 1.5


def _douglas_peucker(points: _Ring, tolerance: float) -> _Ring:
    """Simplifies the open path `points`, keeping its first point and the farthest one from it,
    so the result stays a ring after closing."""
    anchor = max(range(1, len(points)), key=lambda i: math.dist(points[0], points[i]))
    first = _dp_path(points[: anchor + 1], tolerance)
    second = _dp_path([*points[anchor:], points[0]], tolerance)
    return [*first[:-1], *second[:-1]]


def _dp_path(path: _Ring, tolerance: float) -> _Ring:
    if len(path) < 3:
        return path
    start, end = path[0], path[-1]
    distances = [_distance_to_segment(p, start, end) for p in path[1:-1]]
    far = max(range(len(distances)), key=distances.__getitem__)
    if distances[far] <= tolerance:
        return [start, end]
    left = _dp_path(path[: far + 2], tolerance)
    right = _dp_path(path[far + 1 :], tolerance)
    return [*left[:-1], *right]


def _distance_to_segment(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.dist(p, (ax + t * dx, ay + t * dy))
