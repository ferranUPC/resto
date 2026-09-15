"""`RerouterWriter` (E2.2, ADR-0007): only static lane_closure on a LaneTarget, byte-stable XML."""

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


def lane_closure(**overrides: object) -> Intervention:
    kwargs: dict[str, object] = {
        "type": InterventionType.LANE_CLOSURE,
        "target": LANE,
        "window": TimeWindow(7 * 3600, 10 * 3600),
    }
    kwargs.update(overrides)
    return Intervention(**kwargs)  # type: ignore[arg-type]


def test_supports_only_static_lane_closure_on_a_lane_target() -> None:
    writer = RerouterWriter()
    assert writer.supports(lane_closure())
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
