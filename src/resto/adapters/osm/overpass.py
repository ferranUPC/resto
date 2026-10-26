"""Overpass downloader: the OSM map inside a polygon, fetched once per polygon (ADR-0045).

Our own client, not SUMO's `osmGet.py`: it needs no `SUMO_HOME` (ADR-0010). The filter is `poly:`
with whole ways and their nodes; cutting to the polygon happens later, in `netconvert`. Roads and
railways are both downloaded: the snapshot is keyed by the polygon alone and the import profile
(`rail` needs the railways) is chosen afterwards.

The line of a road (`fetch_road`, ADR-0050) is a lighter query: only the highways whose `ref` is
that road's, inside a box, so the band around it can be drawn before the area is downloaded."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlencode

from resto.adapters.osm.http import DEFAULT_USER_AGENT, request
from resto.adapters.persistence.filesystem import artifact_ref
from resto.application.ports.osm import ExternalServiceError, OsmLimits
from resto.domain.services.content_hash import work_key
from resto.domain.services.geo import format_coordinate, ring_of
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, Polygon

SERVICE = "overpass"
DEFAULT_BASE_URL = "https://overpass-api.de/api/interpreter"
SNAPSHOT_KIND = "osm"
_CLIENT_MARGIN_S = 15.0
"""Extra time the client waits beyond the query timeout the server enforces."""
_RUNTIME_ERROR = re.compile(rb"<remark>[^<]*(runtime error|timed out|out of memory)", re.IGNORECASE)


class OverpassOsmSource:
    """`OsmSource` over an Overpass interpreter endpoint."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        limits: OsmLimits | None = None,
        user_agent: str = DEFAULT_USER_AGENT,
        client_timeout_s: float | None = None,
    ) -> None:
        self._base_url = base_url
        self._limits = limits or OsmLimits()
        self._user_agent = user_agent
        self._client_timeout_s = (
            client_timeout_s
            if client_timeout_s is not None
            else self._limits.overpass_timeout_s + _CLIENT_MARGIN_S
        )

    def fetch(self, area: BBox | Polygon, out_dir: Path) -> ArtifactRef:
        ring = ring_of(area)
        return self._download(self._query(ring), out_dir / f"osm-{_polygon_key(ring)}.osm")

    def fetch_road(self, ref: str, area: BBox, out_dir: Path) -> ArtifactRef:
        pattern = _ref_pattern(ref)
        box = ",".join(format_coordinate(v) for v in (area.south, area.west, area.north, area.east))
        query = f'{self._header()}way["highway"]["ref"~"{pattern}",i]({box});(._;>;);out;'
        return self._download(query, out_dir / f"road-{work_key(json.dumps([pattern, box]))}.osm")

    def _download(self, query: str, target: Path) -> ArtifactRef:
        if target.exists():
            return artifact_ref(target, SNAPSHOT_KIND)
        body = request(
            SERVICE,
            self._base_url,
            user_agent=self._user_agent,
            timeout_s=self._client_timeout_s,
            data=urlencode({"data": query}).encode(),
        )
        _check_answer(body)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".osm.part")
        partial.write_bytes(body)
        partial.replace(target)  # a half-written snapshot is never mistaken for a stored one
        return artifact_ref(target, SNAPSHOT_KIND)

    def _query(self, ring: tuple[tuple[float, float], ...]) -> str:
        poly = " ".join(
            f"{format_coordinate(lat)} {format_coordinate(lon)}" for lat, lon in ring[:-1]
        )
        return (
            f"{self._header()}"
            f'(way["highway"](poly:"{poly}");way["railway"](poly:"{poly}"););(._;>;);out;'
        )

    def _header(self) -> str:
        return (
            f"[out:xml][timeout:{self._limits.overpass_timeout_s}]"
            f"[maxsize:{self._limits.overpass_maxsize_bytes}];"
        )


def _ref_pattern(ref: str) -> str:
    """A regular expression (case-insensitive in the query) for one ref in the `ref` tag, which
    may hold several separated by ';': its letters and digits, with anything else between and
    around them, so "A2" finds "A-2" but not "A-21". `OsmMap.road_line` compares refs by the same
    rule (`_ref_key`)."""
    parts = re.findall(r"[a-z]+|[0-9]+", ref.casefold())
    if not parts:
        raise ValueError(f"the ref {ref!r} has no letter or digit")
    other = "[^0-9a-z;]*"
    return f"^(.*;)?{other}" + other.join(parts) + f"{other}(;.*)?$"


def _polygon_key(ring: tuple[tuple[float, float], ...]) -> str:
    """Hash of the ring alone: the same polygon from a geocoder or typed by hand is one snapshot."""
    return work_key(json.dumps(ring))


def _check_answer(body: bytes) -> None:
    """Overpass answers 200 with a `<remark>` when the query ran out of time or memory."""
    if _RUNTIME_ERROR.search(body):
        raise ExternalServiceError(SERVICE, "the query hit a server limit (timeout or maxsize)")
    if b"<osm" not in body:
        raise ExternalServiceError(SERVICE, "the answer is not OSM XML")
