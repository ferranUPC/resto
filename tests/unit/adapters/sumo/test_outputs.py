"""Readers of SUMO output (E2.1, ADR-0017): KPI mapping from `statistic-output` and the header
stripping behind `content_hash`."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.outputs import canonical_bytes, output_artifact, parse_kpis

_STATISTICS = """<?xml version="1.0" encoding="UTF-8"?>

<!-- generated on 2026-09-14T15:19:41.019156+01:00 by Eclipse SUMO sumo 1.27.1
<sumoConfiguration>
    <input><net-file value="/abs/path/dev-net.net.xml"/></input>
</sumoConfiguration>
-->

<statistics>
    <performance clockBegin="1789391981.02" clockEnd="1789391981.04" clockDuration="0.02"/>
    <vehicles loaded="53" inserted="50" running="7" waiting="0"/>
    <teleports total="2" jam="1" yield="1" wrongLane="0"/>
    <vehicleTripStatistics count="43" routeLength="811.06" speed="9.98" duration="85.39"
        waitingTime="12.77" timeLoss="24.38" departDelay="0.02"/>
</statistics>
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "statistics.xml"
    path.write_text(text)
    return path


def test_kpis_follow_the_adr_0017_mapping(tmp_path: Path) -> None:
    kpis = parse_kpis(_write(tmp_path, _STATISTICS))

    assert kpis.mean_travel_time == pytest.approx(85.39)
    assert kpis.mean_delay == pytest.approx(24.38)
    assert kpis.teleports == 2
    assert kpis.departed == 50
    assert kpis.arrived == 43


def test_means_are_zero_when_no_vehicle_completed_its_trip(tmp_path: Path) -> None:
    text = _STATISTICS.replace('count="43"', 'count="0"').replace(
        'duration="85.39"', 'duration="-1.00"'
    )

    kpis = parse_kpis(_write(tmp_path, text))

    assert (kpis.arrived, kpis.mean_travel_time, kpis.mean_delay) == (0, 0.0, 0.0)


def test_missing_trip_statistics_is_an_error_not_zeros(tmp_path: Path) -> None:
    text = _STATISTICS.replace("<vehicleTripStatistics", "<!--").replace(
        'departDelay="0.02"/>', "-->"
    )

    with pytest.raises(ValueError, match="duration-log.statistics"):
        parse_kpis(_write(tmp_path, text))


def test_canonical_bytes_drop_only_the_generated_on_header(tmp_path: Path) -> None:
    body = canonical_bytes(_write(tmp_path, _STATISTICS))

    assert b"generated on" not in body
    assert b"/abs/path" not in body
    assert body.startswith(b'<?xml version="1.0" encoding="UTF-8"?>\n\n\n<statistics>')


def test_output_artifact_hash_ignores_the_timestamp_in_the_header(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    later = _STATISTICS.replace("15:19:41.019156", "16:00:00.000000")

    a = output_artifact(_write(tmp_path / "a", _STATISTICS), "statistics")
    b = output_artifact(_write(tmp_path / "b", later), "statistics")

    assert a.content_hash == b.content_hash
    assert a.kind == "statistics"
