"""Readers for what a `sumo` run leaves behind (ADR-0017): KPIs from `statistic-output`, per-edge
`edgedata` intervals and TLS program-switch events, and the canonical form of SUMO output files
used for their `content_hash`.

`parse_edgedata`/`EdgeInterval` is the one place that reads a SUMO `--edgedata-output` file: both
E2.4's effect-verification harness (`verify/effects.py`, exact per-interval rows) and DatabaseMCP's
`query_edgedata` (`adapters/persistence/sqlite/edgedata.py`, windowed weighted aggregation) build
on it rather than each parsing the XML themselves - originally two independent parsers of the same
file format, merged into one after the fact.

SUMO writes a `<!-- generated on <timestamp> ... -->` header into every output file, holding the
wall-clock time and the absolute paths of the run; 1.27.1 offers no option to omit it. That header
is metadata, not simulation output, so `content_hash` (and the reproducibility criterion of DoD
§4.6) is computed on the file with that one comment removed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class EdgeInterval:
    """One `<edge>` row of one `<interval>` in an `edgedata`-output file (E2.1's
    `write_edgedata_additional`). `speed`/`density`/`occupancy`/`waiting_time`/`time_loss`/
    `travel_time` are all `None` when `sampled_seconds` is 0 - verified against a real DEV-NET
    edgedata file that SUMO omits every one of those six attributes together for an edge nothing
    crossed during the interval, never just `speed` alone."""

    edge_id: str
    begin: float
    end: float
    sampled_seconds: float
    entered: int
    left: int
    departed: int
    arrived: int
    speed: float | None
    density: float | None
    occupancy: float | None
    waiting_time: float | None
    time_loss: float | None
    travel_time: float | None


def _optional_float(edge: ET.Element, attr: str) -> float | None:
    value = edge.get(attr)
    return float(value) if value is not None else None


def parse_edgedata(path: Path) -> tuple[EdgeInterval, ...]:
    """Every non-internal `<edge>` row across every `<interval>` of an edgedata-output file, in
    file order. Internal junction edges (id starting with `:`) are skipped: SUMO's own
    `--edgedata-output` always includes them, but they are never a real, addressable network
    edge (the same fact `query_edgedata`, DATABASE_MCP_CONTRACT.md §5.4, already relied on)."""
    root = ET.parse(path).getroot()
    rows = []
    for interval in root.findall("interval"):
        begin, end = float(interval.get("begin", 0)), float(interval.get("end", 0))
        for edge in interval.findall("edge"):
            edge_id = edge.get("id", "")
            if edge_id.startswith(":"):
                continue
            rows.append(
                EdgeInterval(
                    edge_id=edge_id,
                    begin=begin,
                    end=end,
                    sampled_seconds=float(edge.get("sampledSeconds", "0")),
                    entered=int(edge.get("entered", "0")),
                    left=int(edge.get("left", "0")),
                    departed=int(edge.get("departed", "0")),
                    arrived=int(edge.get("arrived", "0")),
                    speed=_optional_float(edge, "speed"),
                    density=_optional_float(edge, "density"),
                    occupancy=_optional_float(edge, "occupancy"),
                    waiting_time=_optional_float(edge, "waitingTime"),
                    time_loss=_optional_float(edge, "timeLoss"),
                    travel_time=_optional_float(edge, "traveltime"),
                )
            )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class TlsSwitch:
    """One de-duplicated program-active window from a `SaveTLSSwitchTimes` `timedEvent` output
    (`additional_file.xsd`'s `timedEventType`) - the raw file has one `<tlsSwitch>` row per
    from/to connection sharing the same `(program_id, begin, end)`, collapsed here to one."""

    tls_id: str
    program_id: str
    begin: float
    end: float


def parse_tls_switches(path: Path) -> tuple[TlsSwitch, ...]:
    """De-duplicated, time-ordered `TlsSwitch` rows from a `SaveTLSSwitchTimes` output file."""
    root = ET.parse(path).getroot()
    seen: dict[tuple[str, str, float, float], TlsSwitch] = {}
    for row in root.findall("tlsSwitch"):
        key = (
            row.get("id", ""),
            row.get("programID", ""),
            float(row.get("begin", 0)),
            float(row.get("end", 0)),
        )
        seen.setdefault(key, TlsSwitch(tls_id=key[0], program_id=key[1], begin=key[2], end=key[3]))
    return tuple(sorted(seen.values(), key=lambda s: s.begin))
