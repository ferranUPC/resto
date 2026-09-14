"""Readers for what a `sumo` run leaves behind (ADR-0017): KPIs from `statistic-output`, and
the canonical form of SUMO output files used for their `content_hash`.

SUMO writes a `<!-- generated on <timestamp> ... -->` header into every output file, holding the
wall-clock time and the absolute paths of the run; 1.27.1 offers no option to omit it. That header
is metadata, not simulation output, so `content_hash` (and the reproducibility criterion of DoD
§4.6) is computed on the file with that one comment removed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from resto.adapters.persistence.filesystem import sha256_of
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.kpis import Kpis

_SUMO_HEADER = re.compile(rb"<!-- generated on .*?-->\r?\n?", re.DOTALL)


def canonical_bytes(path: Path) -> bytes:
    """The file's bytes with SUMO's generated-on header comment stripped."""
    return _SUMO_HEADER.sub(b"", path.read_bytes(), count=1)


def output_artifact(path: Path, kind: str) -> ArtifactRef:
    return ArtifactRef(
        path=path.resolve(), content_hash=sha256_of(canonical_bytes(path)), kind=kind
    )


def parse_kpis(statistics_xml: Path) -> Kpis:
    """`Kpis` from a `statistic-output` file written with `duration-log.statistics` on.

    Mapping (ADR-0017): mean_travel_time <- vehicleTripStatistics/@duration, mean_delay <-
    vehicleTripStatistics/@timeLoss, teleports <- teleports/@total, departed <- vehicles/@inserted,
    arrived <- vehicleTripStatistics/@count. Means are 0.0 when no vehicle completed its trip.

    Raises:
        ValueError: a required element is missing (typically `duration-log.statistics` was off).
    """
    root = ET.parse(statistics_xml).getroot()
    vehicles = root.find("vehicles")
    teleports = root.find("teleports")
    trips = root.find("vehicleTripStatistics")
    if vehicles is None or teleports is None or trips is None:
        raise ValueError(
            f"{statistics_xml.name}: missing vehicles/teleports/vehicleTripStatistics; "
            "was the run written with duration-log.statistics?"
        )
    arrived = int(trips.get("count", "0"))
    return Kpis(
        mean_delay=float(trips.get("timeLoss", "0")) if arrived else 0.0,
        mean_travel_time=float(trips.get("duration", "0")) if arrived else 0.0,
        teleports=int(teleports.get("total", "0")),
        departed=int(vehicles.get("inserted", "0")),
        arrived=arrived,
    )
