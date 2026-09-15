"""Readers of SUMO output (E2.1, ADR-0017): KPI mapping from `statistic-output`, the header
stripping behind `content_hash`, and `parse_edgedata`/`EdgeInterval` (E2.4/E1.3-E1.4's shared
edgedata reader - `verify/effects.py` and `adapters/persistence/sqlite/edgedata.py` both build on
it rather than each parsing the XML themselves)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.outputs import (
    canonical_bytes,
    output_artifact,
    parse_edgedata,
    parse_kpis,
)

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


_EDGEDATA = """<?xml version="1.0"?>
<edgedata>
    <interval begin="0" end="300" id="i1">
        <edge id="E1" sampledSeconds="40.00" density="10" occupancy="0.1" speed="8"
              waitingTime="1" timeLoss="2" traveltime="10" entered="4" left="4"
              departed="1" arrived="0"/>
        <edge id="E2" sampledSeconds="0.00" entered="0" left="0" departed="0" arrived="0"/>
        <edge id=":J1_0" sampledSeconds="99" density="99" occupancy="0" speed="0"
              waitingTime="0" timeLoss="0" traveltime="0" entered="0" left="0"
              departed="0" arrived="0"/>
    </interval>
</edgedata>
"""


def _write_edgedata(tmp_path: Path) -> Path:
    path = tmp_path / "edgedata.xml"
    path.write_text(_EDGEDATA)
    return path


def test_parse_edgedata_reads_every_field_of_a_sampled_edge(tmp_path: Path) -> None:
    rows = parse_edgedata(_write_edgedata(tmp_path))
    e1 = next(r for r in rows if r.edge_id == "E1")

    assert (e1.begin, e1.end) == (0.0, 300.0)
    assert e1.sampled_seconds == pytest.approx(40.0)
    assert (e1.entered, e1.left, e1.departed, e1.arrived) == (4, 4, 1, 0)
    assert e1.speed == pytest.approx(8.0)
    assert e1.density == pytest.approx(10.0)
    assert e1.occupancy == pytest.approx(0.1)
    assert e1.waiting_time == pytest.approx(1.0)
    assert e1.time_loss == pytest.approx(2.0)
    assert e1.travel_time == pytest.approx(10.0)


def test_parse_edgedata_leaves_every_omitted_attribute_none_not_zero(tmp_path: Path) -> None:
    rows = parse_edgedata(_write_edgedata(tmp_path))
    e2 = next(r for r in rows if r.edge_id == "E2")

    assert e2.sampled_seconds == 0.0
    assert (e2.speed, e2.density, e2.occupancy, e2.waiting_time) == (None, None, None, None)
    assert (e2.time_loss, e2.travel_time) == (None, None)


def test_parse_edgedata_skips_internal_junction_edges(tmp_path: Path) -> None:
    rows = parse_edgedata(_write_edgedata(tmp_path))

    assert {r.edge_id for r in rows} == {"E1", "E2"}
