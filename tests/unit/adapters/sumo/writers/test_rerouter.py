"""`RerouterWriter` (E2.2/E2.3, ADR-0007): static lane_closure on a LaneTarget and static
edge_closure on an EdgeTarget, byte-stable XML."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.time_window import TimeWindow

LANE = LaneTarget(edge_id="A0A1", lane_index=1)
EDGE = EdgeTarget(edge_id="A0A1")


def lane_closure(**overrides: object) -> Intervention:
    kwargs: dict[str, object] = {
        "type": InterventionType.LANE_CLOSURE,
        "target": LANE,
        "window": TimeWindow(7 * 3600, 10 * 3600),
    }
    kwargs.update(overrides)
    return Intervention(**kwargs)  # type: ignore[arg-type]


def edge_closure(**overrides: object) -> Intervention:
    kwargs: dict[str, object] = {
        "type": InterventionType.EDGE_CLOSURE,
        "target": EDGE,
        "window": TimeWindow(7 * 3600, 10 * 3600),
    }
    kwargs.update(overrides)
    return Intervention(**kwargs)  # type: ignore[arg-type]


def test_supports_static_lane_closure_on_a_lane_target_and_edge_closure_on_an_edge_target() -> (
    None
):
    writer = RerouterWriter()
    assert writer.supports(lane_closure())
    assert writer.supports(edge_closure())
    assert not writer.supports(
        Intervention(
            type=InterventionType.LANE_CLOSURE,
            target=EdgeTarget(edge_id="A0A1"),
            window=TimeWindow(0, 60),
        )
    )
    assert not writer.supports(
        Intervention(type=InterventionType.SPEED_LIMIT, target=LANE, window=TimeWindow(0, 60))
    )


def test_write_produces_a_mechanism_and_matching_artifact_ref(tmp_path: Path) -> None:
    mechanism, ref = RerouterWriter().write(lane_closure(), tmp_path)
    assert isinstance(mechanism, StaticFileMechanism)
    assert isinstance(ref, ArtifactRef)
    assert mechanism.file_kind == "rerouter"
    assert mechanism.path == (tmp_path / "rerouter_A0A1_1.add.xml").resolve()
    assert mechanism.path == ref.path
    assert ref.kind == "additional"
    assert ref.content_hash
    assert mechanism.path.exists()


def test_write_rejects_an_unsupported_intervention(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        RerouterWriter().write(
            Intervention(type=InterventionType.SPEED_LIMIT, target=LANE, window=TimeWindow(0, 60)),
            tmp_path,
        )


def test_written_xml_has_the_closing_lane_reroute(tmp_path: Path) -> None:
    mechanism, _ = RerouterWriter().write(lane_closure(), tmp_path)
    text = mechanism.path.read_text(encoding="utf-8")
    assert '<rerouter id="rerouter_A0A1_1" edges="A0A1">' in text
    assert '<interval begin="25200" end="36000">' in text
    assert '<closingLaneReroute id="A0A1_1" />' in text


def test_authoring_is_deterministic(tmp_path: Path) -> None:
    a, _ = RerouterWriter().write(lane_closure(), tmp_path / "a")
    b, _ = RerouterWriter().write(lane_closure(), tmp_path / "b")
    assert a.path.read_text(encoding="utf-8") == b.path.read_text(encoding="utf-8")


def test_write_produces_a_mechanism_and_matching_artifact_ref_for_an_edge_closure(
    tmp_path: Path,
) -> None:
    mechanism, ref = RerouterWriter().write(edge_closure(), tmp_path)
    assert mechanism.file_kind == "rerouter"
    assert mechanism.path == (tmp_path / "rerouter_A0A1.add.xml").resolve()
    assert mechanism.path == ref.path
    assert ref.kind == "additional"


def test_written_xml_has_the_closing_reroute_for_an_edge_closure(tmp_path: Path) -> None:
    mechanism, _ = RerouterWriter().write(edge_closure(), tmp_path)
    text = mechanism.path.read_text(encoding="utf-8")
    assert '<rerouter id="rerouter_A0A1" edges="A0A1">' in text
    assert '<interval begin="25200" end="36000">' in text
    assert '<closingReroute id="A0A1" />' in text
    assert "closingLaneReroute" not in text
