"""Contract §8 item 5: `query_edgedata` - window clipping, weighted aggregation, empty
`edge_ids`, zero-sample edges present, unknown edges omitted, plus vehicle-second totals summed
(ADR-0020). Against a hand-crafted fixture with round numbers so every expected value is
hand-computed (see also `tests/unit/adapters/persistence/sqlite/test_edgedata.py`, which tests
the same aggregation in-process rather than through MCP)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from tests.unit.domain._samples import simulation_result

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.domain.value_objects.artifact_ref import ArtifactRef

_FIXTURE = """<?xml version="1.0"?>
<edgedata>
    <interval begin="0" end="100" id="i1">
        <edge id="E1" sampledSeconds="40" density="10" occupancy="0.1" speed="8"
              waitingTime="1" timeLoss="2" traveltime="10" entered="4" left="4"
              departed="1" arrived="0"/>
        <edge id="E2" sampledSeconds="0" density="0" occupancy="0" speed="0"
              waitingTime="0" timeLoss="0" traveltime="0" entered="0" left="0"
              departed="0" arrived="0"/>
    </interval>
    <interval begin="100" end="200" id="i2">
        <edge id="E1" sampledSeconds="60" density="20" occupancy="0.3" speed="12"
              waitingTime="3" timeLoss="4" traveltime="20" entered="6" left="5"
              departed="0" arrived="1"/>
    </interval>
</edgedata>
"""


@pytest.fixture
def result_id(db: McpClientDatabase, tmp_path: Path) -> str:
    edgedata_path = tmp_path / "r.edgedata.xml"
    edgedata_path.write_text(_FIXTURE)
    result = dataclasses.replace(
        simulation_result(),
        artifacts=(ArtifactRef(path=edgedata_path, content_hash="ed1", kind="edgedata"),),
    )
    db.results.store(result)
    return result.result_id


def test_empty_edge_ids_returns_every_known_edge(db: McpClientDatabase, result_id: str) -> None:
    measures = db.results.query_edgedata(result_id, [], None)

    assert set(measures) == {"E1", "E2"}


def test_unknown_edge_id_is_omitted_not_zero_filled(db: McpClientDatabase, result_id: str) -> None:
    measures = db.results.query_edgedata(result_id, ["NOT_AN_EDGE"], None)

    assert measures == {}


def test_zero_sample_edge_is_present_and_zero_filled(db: McpClientDatabase, result_id: str) -> None:
    measures = db.results.query_edgedata(result_id, ["E2"], None)

    assert measures["E2"]["sampled_seconds"] == 0.0
    assert measures["E2"]["entered"] == 0


def test_null_window_aggregates_the_whole_simulation_by_weighted_average(
    db: McpClientDatabase, result_id: str
) -> None:
    measures = db.results.query_edgedata(result_id, ["E1"], None)

    # weighted by sampledSeconds: (8*40 + 12*60) / 100 = 10.4
    assert measures["E1"]["speed"] == pytest.approx(10.4)
    assert measures["E1"]["sampled_seconds"] == pytest.approx(100.0)
    assert measures["E1"]["entered"] == 10


def test_vehicle_second_totals_are_summed_not_averaged(
    db: McpClientDatabase, result_id: str
) -> None:
    whole = db.results.query_edgedata(result_id, ["E1"], None)["E1"]
    half = db.results.query_edgedata(result_id, ["E1"], (0.0, 150.0))["E1"]

    # time_loss/waiting_time are totals over vehicles (ADR-0020): 2 + 4 and 1 + 3
    assert whole["time_loss"] == pytest.approx(6.0)
    assert whole["waiting_time"] == pytest.approx(4.0)
    # [0, 150): i1 fully inside, i2 half inside -> prorated, not rounded
    assert half["time_loss"] == pytest.approx(4.0)
    assert half["waiting_time"] == pytest.approx(2.5)


def test_window_clips_to_the_requested_interval(db: McpClientDatabase, result_id: str) -> None:
    measures = db.results.query_edgedata(result_id, ["E1"], (0.0, 100.0))

    assert measures["E1"]["speed"] == pytest.approx(8.0)
    assert measures["E1"]["sampled_seconds"] == pytest.approx(40.0)
    assert measures["E1"]["entered"] == 4
