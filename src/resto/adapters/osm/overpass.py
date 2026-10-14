"""Overpass downloader: the OSM map inside a polygon, fetched once per polygon (ADR-0045).

Our own client, not SUMO's `osmGet.py`: it needs no `SUMO_HOME` (ADR-0010). The filter is `poly:`
with whole ways and their nodes; cutting to the polygon happens later, in `netconvert`."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlencode

from resto.adapters.osm.http import request
from resto.adapters.persistence.filesystem import artifact_ref
from resto.application.ports.osm import ExternalServiceError, OsmLimits
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, Polygon

SERVICE = "overpass"
DEFAULT_BASE_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_USER_AGENT = "resto-tfm/0.1 (research prototype; LLM agents for SUMO networks)"
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
        ring = _ring_of(area)
        target = out_dir / f"osm-{_polygon_key(ring)}.osm"
        if target.exists():
            return artifact_ref(target, SNAPSHOT_KIND)
        body = request(
            SERVICE,
            self._base_url,
            user_agent=self._user_agent,
            timeout_s=self._client_timeout_s,
            data=urlencode({"data": self._query(ring)}).encode(),
        )
        _check_answer(body)
        out_dir.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".osm.part")
        partial.write_bytes(body)
        partial.replace(target)  # a half-written snapshot is never mistaken for a stored one
        return artifact_ref(target, SNAPSHOT_KIND)

    def _query(self, ring: tuple[tuple[float, float], ...]) -> str:
        poly = " ".join(f"{lat:g} {lon:g}" for lat, lon in ring[:-1])
        return (
            f"[out:xml][timeout:{self._limits.overpass_timeout_s}]"
            f"[maxsize:{self._limits.overpass_maxsize_bytes}];"
            f'(way["highway"](poly:"{poly}"););(._;>;);out;'
        )


def _ring_of(area: BBox | Polygon) -> tuple[tuple[float, float], ...]:
    if isinstance(area, Polygon):
        return area.ring
    s, w, n, e = area.south, area.west, area.north, area.east
    return ((s, w), (s, e), (n, e), (n, w), (s, w))


def _polygon_key(ring: tuple[tuple[float, float], ...]) -> str:
    """Hash of the ring alone: the same polygon from a geocoder or typed by hand is one snapshot."""
    return hashlib.sha256(json.dumps(ring).encode()).hexdigest()[:16]


def _check_answer(body: bytes) -> None:
    """Overpass answers 200 with a `<remark>` when the query ran out of time or memory."""
    if _RUNTIME_ERROR.search(body):
        raise ExternalServiceError(SERVICE, "the query hit a server limit (timeout or maxsize)")
    if b"<osm" not in body:
        raise ExternalServiceError(SERVICE, "the answer is not OSM XML")
