"""`VssWriter` (E2.2, ADR-0007): only static speed_limit on a LaneTarget, requires speed +
revert_speed in params, byte-stable XML."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.writers.vss import VssWriter
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.time_window import TimeWindow

LANE = LaneTarget(edge_id="A0A1", lane_index=0)


def speed_limit(**overrides: object) -> Intervention:
    kwargs: dict[str, object] = {
        "type": InterventionType.SPEED_LIMIT,
        "target": LANE,
        "window": TimeWindow(7 * 3600, 10 * 3600),
        "params": {"speed": 5.0, "revert_speed": 13.89},
    }
    kwargs.update(overrides)
    return Intervention(**kwargs)  # type: ignore[arg-type]


def test_supports_only_static_speed_limit_on_a_lane_target() -> None:
    writer = VssWriter()
    assert writer.supports(speed_limit())
    assert not writer.supports(
        Intervention(
            type=InterventionType.SPEED_LIMIT,
            target=EdgeTarget(edge_id="A0A1"),
            window=TimeWindow(0, 60),
        )
    )
    assert not writer.supports(
        Intervention(type=InterventionType.LANE_CLOSURE, target=LANE, window=TimeWindow(0, 60))
    )


def test_write_requires_speed_and_revert_speed_params(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        VssWriter().write(speed_limit(params={"speed": 5.0}), tmp_path)
    with pytest.raises(ValueError):
        VssWriter().write(speed_limit(params={"revert_speed": 13.89}), tmp_path)


def test_write_produces_a_mechanism_and_matching_artifact_ref(tmp_path: Path) -> None:
    mechanism, ref = VssWriter().write(speed_limit(), tmp_path)
    assert isinstance(mechanism, StaticFileMechanism)
    assert isinstance(ref, ArtifactRef)
    assert mechanism.file_kind == "vss"
    assert mechanism.path == (tmp_path / "vss_A0A1_0.add.xml").resolve()
    assert mechanism.path == ref.path
    assert ref.kind == "additional"
    assert ref.content_hash
    assert mechanism.path.exists()


def test_written_xml_has_the_two_step_profile(tmp_path: Path) -> None:
    mechanism, _ = VssWriter().write(speed_limit(), tmp_path)
    text = mechanism.path.read_text(encoding="utf-8")
    assert '<variableSpeedSign id="vss_A0A1_0" lanes="A0A1_0">' in text
    assert '<step time="25200" speed="5" />' in text
    assert '<step time="36000" speed="13.89" />' in text


def test_authoring_is_deterministic(tmp_path: Path) -> None:
    a, _ = VssWriter().write(speed_limit(), tmp_path / "a")
    b, _ = VssWriter().write(speed_limit(), tmp_path / "b")
    assert a.path.read_text(encoding="utf-8") == b.path.read_text(encoding="utf-8")
