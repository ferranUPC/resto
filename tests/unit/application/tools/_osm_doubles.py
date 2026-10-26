"""Doubles for the OpenStreetMap import tools: a source that serves one small committed `.osm` and
counts its downloads, and a geocoder with a fixed answer. Neither touches the network."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from resto.adapters.persistence.filesystem import artifact_ref
from resto.application.ports.osm import ExternalServiceError, LocatedPlace, PlaceRejected
from resto.application.tools.network_import import AreaArg
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.network_source import BBox, PlaceName, Polygon

DISTRICT_OSM = Path(__file__).parent / "fixtures" / "district.osm"
"""Two crossing roads inside the district, a road leaving it, an island road inside it that joins
nothing, and a road far outside."""

CAMPUS_OSM = Path(__file__).parent / "fixtures" / "campus.osm"
"""A residential road crossed by a named service street, a driveway and a parking aisle."""

CORRIDOR_OSM = Path(__file__).parent / "fixtures" / "corridor.osm"
"""The Diagonal in small, along lat 41.39 from lon 2.100 to 2.150: a primary road called "Carretera
Reial" (way 301) that becomes "Avinguda Diagonal" (300, 303), all three with `ref` N-340. An
unnamed `primary_link` (304, 42 m) joins 301 to 300 and a square with another name ("Plaça de Pius
XII", 302, 125 m) joins 300 to 303. A lateral lane, also "Avinguda Diagonal" but with no ref
(305, lat 41.3903), touches the main road only through the 33 m of Balmes between them. A footway
named "Passeig de la Diagonal" (306) leaves the west end. Two cross streets (Muntaner 310, Balmes
311) and a street north of the corridor (Carrer de Dalt 320) close a loop away from it."""

CORRIDOR = BBox(south=41.384, west=2.099, north=41.396, east=2.151)

WEST_END = LocatedPlace("Hospital Broggi", 41.3901, 2.1001, "amenity", "hospital", "Hospital")
"""Next to the west end of the corridor (node 1)."""

EAST_END = LocatedPlace("Francesc Macià", 41.3901, 2.1499, "place", "square", "Francesc Macià")
"""Next to the east end of the corridor (node 8)."""

DIAGONAL_B23_OSM = Path(__file__).parent / "fixtures" / "diagonal_b23.osm"
"""The Diagonal that continues as the B-23. A tertiary "Avinguda del Baix Llobregat" (401, 167 m)
leaves the hospital (node 1) to a `motorway_link` (402) that enters the eastbound carriageway at
node 3 (E). The B-23 is a motorway with `ref` and no name, two one-way carriageways (403 east, 404
west) at 80 km/h that meet at both ends. At node 12 it becomes "Avinguda Diagonal" with `ref` B-23
(405) and then "Avinguda Diagonal" alone (406), at 50 km/h, up to the square (node 17). A decoy
"Carretera Reial" `ref` N-340 (407) goes straight from the hospital to the square: about 260 m
shorter, but at 30 km/h. "Carrer de l'Illa" (408) joins nothing."""

INTERCHANGE_OSM = Path(__file__).parent / "fixtures" / "interchange.osm"
"""The B-23 with the link to a town, as it is in OSM: two one-way carriageways with `ref` B-23 and
no name (501, 502), two unnamed `primary` roundabouts (601, 602) and four unnamed `motorway_link`
(701 to 704) that leave and enter the carriageways through them. A tertiary "Carrer de Sant Just"
(603) leaves R2 and crosses the edge of `INTERCHANGE_ZONE`; "Carrer del Mig" is a residential (801)
that ends in an unnamed service street (802) inside the zone, and another (803) 1.7 km north. An
unnamed `motorway_link` (804) 2 km away from the junction groups with the four ramps by class."""

INTERCHANGE_BOX = BBox(south=41.370, west=2.055, north=41.395, east=2.085)

INTERCHANGE_ZONE: AreaArg = {"near": [41.3750, 2.0700], "radius_m": 300}
"""Holds the junction, the ramps and 603 up to node 31; node 32 is 375 m away."""

DIAGONAL_AREA = BBox(south=41.370, west=2.060, north=41.398, east=2.150)

HOSPITAL = LocatedPlace("Hospital Broggi", 41.3743, 2.0718, "amenity", "hospital", "Hospital")
"""About 20 m from the start of the access road (node 1) and 250 m from E."""

MACIA = LocatedPlace("Francesc Macià", 41.3925, 2.1440, "place", "square", "Francesc Macià")
"""At the end of the Diagonal (node 17)."""

DISTRICT = Polygon(
    ((41.390, 2.150), (41.390, 2.160), (41.398, 2.160), (41.398, 2.150), (41.390, 2.150)),
    osm_id=7,
)


class FakeOsmSource:
    """Serves `source` (`DISTRICT_OSM` by default) for any area, and `road` (`CORRIDOR_OSM`) for the
    line of any road; like the real source, what was already fetched is returned from disk and
    `downloads` does not grow."""

    def __init__(self, source: Path = DISTRICT_OSM, road: Path = CORRIDOR_OSM) -> None:
        self.calls: list[BBox | Polygon] = []
        self.road_calls: list[tuple[str, BBox]] = []
        self.downloads = 0
        self._source = source
        self._road = road

    def fetch(self, area: BBox | Polygon, out_dir: Path) -> ArtifactRef:
        self.calls.append(area)
        return self._serve(self._source, out_dir / f"osm-{_key(area)}.osm")

    def fetch_road(self, ref: str, area: BBox, out_dir: Path) -> ArtifactRef:
        self.road_calls.append((ref, area))
        return self._serve(self._road, out_dir / f"road-{_key((ref, area))}.osm")

    def _serve(self, source: Path, target: Path) -> ArtifactRef:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source, target)
            self.downloads += 1
        return artifact_ref(target, "osm")


def _key(value: object) -> str:
    return hashlib.sha256(json.dumps(repr(value)).encode()).hexdigest()[:16]


class FakeGeocoder:
    """Resolves every boundary to `polygon` and locates only the `places` it was given."""

    def __init__(
        self,
        polygon: Polygon = DISTRICT,
        rejection: str | None = None,
        down: bool = False,
        places: tuple[LocatedPlace, ...] = (),
    ) -> None:
        self._polygon = polygon
        self._rejection = rejection
        self._down = down
        self._places = {p.query: p for p in places}
        self.queries: list[str] = []

    def resolve(self, place: PlaceName) -> Polygon:
        self.queries.append(place.query)
        if self._down:
            raise ExternalServiceError("nominatim", "HTTP 503")
        if self._rejection:
            raise PlaceRejected(place.query, self._rejection)
        return self._polygon

    def locate(self, query: str) -> LocatedPlace | None:
        self.queries.append(query)
        if self._down:
            raise ExternalServiceError("nominatim", "HTTP 503")
        return self._places.get(query)
