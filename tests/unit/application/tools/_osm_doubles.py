"""Doubles for the OpenStreetMap import tools: a source that serves one small committed `.osm` and
counts its downloads, and a geocoder with a fixed answer. Neither touches the network."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.application.ports.osm import ExternalServiceError, PlaceRejected
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, PlaceName, Polygon

DISTRICT_OSM = Path(__file__).parent / "fixtures" / "district.osm"
"""Two crossing roads inside the district, a road leaving it, an island road inside it that joins
nothing, and a road far outside."""

DISTRICT = Polygon(
    ((41.390, 2.150), (41.390, 2.160), (41.398, 2.160), (41.398, 2.150), (41.390, 2.150)),
    osm_id=7,
)


class FakeOsmSource:
    """Serves `DISTRICT_OSM` for any area; like the real source, an area already fetched is
    returned from disk and `downloads` does not grow."""

    def __init__(self) -> None:
        self.calls: list[BBox | Polygon] = []
        self.downloads = 0

    def fetch(self, area: BBox | Polygon, out_dir: Path) -> ArtifactRef:
        self.calls.append(area)
        key = hashlib.sha256(json.dumps(repr(area)).encode()).hexdigest()[:16]
        target = out_dir / f"osm-{key}.osm"
        if not target.exists():
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(DISTRICT_OSM, target)
            self.downloads += 1
        return artifact_ref(target, "osm")


class FakeGeocoder:
    def __init__(
        self, polygon: Polygon = DISTRICT, rejection: str | None = None, down: bool = False
    ) -> None:
        self._polygon = polygon
        self._rejection = rejection
        self._down = down
        self.queries: list[str] = []

    def resolve(self, place: PlaceName) -> Polygon:
        self.queries.append(place.query)
        if self._down:
            raise ExternalServiceError("nominatim", "HTTP 503")
        if self._rejection:
            raise PlaceRejected(place.query, self._rejection)
        return self._polygon
