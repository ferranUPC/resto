"""OpenStreetMap access for the Network Author (ADR-0045, ADR-0046): a geocoder that resolves a
place name to a polygon or locates it as a point, and a source that downloads the map inside a
polygon once."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, PlaceName, Polygon


class ExternalServiceError(Exception):
    """A public service (`nominatim`, `overpass`) failed or answered something unusable. The user
    cannot fix it, so it fails the step by name instead of becoming `NeedsUser` (ADR-0045 §7)."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(f"{service}: {detail}")
        self.service = service
        self.detail = detail


class PlaceRejected(Exception):
    """The place name does not resolve to an administrative boundary (ADR-0045 §2). `reason` says
    why, in words the user can act on."""

    def __init__(self, query: str, reason: str) -> None:
        super().__init__(f"{query!r}: {reason}")
        self.query = query
        self.reason = reason


@dataclass(frozen=True, slots=True)
class OsmLimits:
    """Limits on what is imported from OpenStreetMap. Initial values, to calibrate on
    GEN-LOCATIONS (ADR-0045 §6)."""

    max_area_km2: float = 25.0
    max_edges: int = 25_000
    overpass_maxsize_bytes: int = 256 * 1024 * 1024
    overpass_timeout_s: int = 90

    def __post_init__(self) -> None:
        if self.max_area_km2 <= 0:
            raise ValueError("max_area_km2 must be positive")
        if self.max_edges < 1:
            raise ValueError("max_edges must be >= 1")
        if self.overpass_maxsize_bytes < 1:
            raise ValueError("overpass_maxsize_bytes must be >= 1")
        if self.overpass_timeout_s < 1:
            raise ValueError("overpass_timeout_s must be >= 1")


@dataclass(frozen=True, slots=True)
class LocatedPlace:
    """Where a place or point of interest is (ADR-0046): its point, what OpenStreetMap says it is
    (`category` and `type`, e.g. `amenity`/`hospital`) and the name the geocoder matched."""

    query: str
    lat: float
    lon: float
    category: str
    type: str
    name: str


class Geocoder(Protocol):
    def resolve(self, place: PlaceName) -> Polygon:
        """The boundary of `place`; raises `PlaceRejected` when it is not an administrative
        boundary and `ExternalServiceError` when the service fails."""
        ...

    def locate(self, query: str) -> LocatedPlace | None:
        """The best match for `query` as a point, of any kind (a hospital, a square, a street), or
        `None` when the geocoder knows nothing by that name. Raises `ExternalServiceError` when
        the service fails."""
        ...


class OsmSource(Protocol):
    def fetch(self, area: BBox | Polygon, out_dir: Path) -> ArtifactRef:
        """The `.osm` snapshot of `area` in `out_dir`, keyed by the polygon's hash: asking again
        for the same polygon returns the stored file without a new download. Raises
        `ExternalServiceError` when the service fails."""
        ...
