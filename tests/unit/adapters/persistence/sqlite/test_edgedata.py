"""query_edgedata aggregation (DATABASE_MCP_CONTRACT.md §5.4): interval clipping, weighted
averaging, proration of counters and vehicle-second totals, omission vs zero-fill, against a
hand-crafted fixture with round numbers (so every expected value below is hand-computed, not
re-derived from the code under test) plus one real SUMO-generated file as a parsing smoke test."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.persistence.sqlite.edgedata import query_edgedata

_FIXTURE = """<?xml version="1.0"?>
<edgedata>
    <interval begin="0" end="100" id="i1">
        <edge id="E1" sampledSeconds="40" density="10" occupancy="0.1" speed="8"
              waitingTime="1" timeLoss="2" traveltime="10" entered="4" left="4"
              departed="1" arrived="0"/>
        <edge id="E2" sampledSeconds="0" density="0" occupancy="0" speed="0"
              waitingTime="0" timeLoss="0" traveltime="0" entered="0" left="0"
              departed="0" arrived="0"/>
        <edge id=":J1_0" sampledSeconds="99" density="99" occupancy="0" speed="0"
              waitingTime="0" timeLoss="0" traveltime="0" entered="0" left="0"
              departed="0" arrived="0"/>
    </interval>
    <interval begin="100" end="200" id="i2">
        <edge id="E1" sampledSeconds="60" density="20" occupancy="0.3" speed="12"
              waitingTime="3" timeLoss="4" traveltime="20" entered="6" left="5"
              departed="0" arrived="1"/>
        <edge id="E2" sampledSeconds="0" density="0" occupancy="0" speed="0"
              waitingTime="0" timeLoss="0" traveltime="0" entered="0" left="0"
              departed="0" arrived="0"/>
    </interval>
</edgedata>
"""


@pytest.fixture
def edgedata_file(tmp_path: Path) -> Path:
    path = tmp_path / "result.edgedata.xml"
    path.write_text(_FIXTURE)
    return path


def test_internal_junction_edges_are_never_returned(edgedata_file: Path) -> None:
    result = query_edgedata(edgedata_file, [], None)

    assert ":J1_0" not in result


def test_empty_edge_ids_returns_every_known_edge_sorted(edgedata_file: Path) -> None:
    result = query_edgedata(edgedata_file, [], None)

    assert list(result) == ["E1", "E2"]


def test_unknown_edge_id_is_omitted_not_zero_filled(edgedata_file: Path) -> None:
    result = query_edgedata(edgedata_file, ["E1", "NOT_A_NETWORK_EDGE"], None)

    assert list(result) == ["E1"]


def test_zero_traffic_edge_is_zero_filled_not_omitted(edgedata_file: Path) -> None:
    result = query_edgedata(edgedata_file, ["E2"], None)

    assert result["E2"]["sampled_seconds"] == 0.0
    assert result["E2"]["density"] == 0.0
    assert result["E2"]["entered"] == 0.0


def test_null_window_aggregates_the_whole_simulation(edgedata_file: Path) -> None:
    e1 = query_edgedata(edgedata_file, ["E1"], None)["E1"]

    assert e1["sampled_seconds"] == pytest.approx(100.0)
    assert e1["density"] == pytest.approx(16.0)  # (10*40 + 20*60) / 100
    assert e1["occupancy"] == pytest.approx(0.22)  # (0.1*40 + 0.3*60) / 100
    assert e1["speed"] == pytest.approx(10.4)  # (8*40 + 12*60) / 100
    assert e1["waiting_time"] == pytest.approx(4.0)  # vehicle-second totals add up: 1 + 3
    assert e1["time_loss"] == pytest.approx(6.0)  # 2 + 4, not averaged (ADR-0020)
    assert e1["entered"] == 10  # 4 + 6, fraction 1.0 both intervals
    assert e1["left"] == 9
    assert e1["departed"] == 1
    assert e1["arrived"] == 1


def test_window_clips_and_prorates_a_partially_overlapping_interval(edgedata_file: Path) -> None:
    # [0, 150): interval i1 [0,100) fully inside -> fraction 1.0; i2 [100,200) half inside -> 0.5
    e1 = query_edgedata(edgedata_file, ["E1"], (0.0, 150.0))["E1"]

    assert e1["sampled_seconds"] == pytest.approx(70.0)  # 40*1.0 + 60*0.5
    assert e1["density"] == pytest.approx(1000 / 70)  # (10*40 + 20*30) / 70
    assert e1["time_loss"] == pytest.approx(4.0)  # 2*1.0 + 4*0.5, prorated, not rounded
    assert e1["waiting_time"] == pytest.approx(2.5)  # 1*1.0 + 3*0.5
    assert e1["entered"] == 7  # 4*1.0 + 6*0.5 = 7.0 -> round-half-up 7
    assert e1["left"] == 7  # 4*1.0 + 5*0.5 = 6.5 -> round-half-up 7
    assert e1["arrived"] == 1  # 0*1.0 + 1*0.5 = 0.5 -> round-half-up 1


def test_window_outside_every_interval_zero_fills_a_known_edge(edgedata_file: Path) -> None:
    e1 = query_edgedata(edgedata_file, ["E1"], (500.0, 600.0))["E1"]

    assert e1 == {
        "sampled_seconds": 0.0,
        "density": 0.0,
        "occupancy": 0.0,
        "speed": 0.0,
        "waiting_time": 0.0,
        "time_loss": 0.0,
        "travel_time": 0.0,
        "entered": 0.0,
        "left": 0.0,
        "departed": 0.0,
        "arrived": 0.0,
    }


def test_parses_a_real_sumo_generated_edgedata_file() -> None:
    real_file = (
        Path(__file__).resolve().parents[5]
        / "eval"
        / "dev-net"
        / "demand"
        / "_runs"
        / "incident_seed1.edgedata.xml"
    )
    if not real_file.exists():
        pytest.skip("eval/dev-net/demand/_runs is generated locally, not committed")

    result = query_edgedata(real_file, ["B0C0"], None)

    assert result["B0C0"]["sampled_seconds"] > 0
