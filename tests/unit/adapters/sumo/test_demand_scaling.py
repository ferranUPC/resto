"""`SumoDemandScaler` (E2.3): deterministic, RNG-free resample of a trips file by a multiplicative
factor — the departed-count side of `demand_scale`'s ±5% effect-verification bar (DoD §4.5)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.sumo.demand_scaling import SumoDemandScaler


def _trips_file(tmp_path: Path, n: int) -> Path:
    root = ET.Element("routes")
    for i in range(n):
        attrib = {"id": f"t_{i}", "depart": f"{i}.00", "from": "A0A1", "to": "B0B1"}
        ET.SubElement(root, "trip", attrib)
    path = tmp_path / "in.trips.xml"
    ET.ElementTree(root).write(path, encoding="unicode")
    return path


def _count(path: Path) -> int:
    return len(ET.parse(path).getroot().findall("trip"))


def _ids(path: Path) -> list[str]:
    return [t.attrib["id"] for t in ET.parse(path).getroot().findall("trip")]


def test_scaling_up_duplicates_trips_to_the_rounded_target_count(tmp_path: Path) -> None:
    trips = artifact_ref(_trips_file(tmp_path, 10), "trips")

    result = SumoDemandScaler().scale(trips, 1.5, tmp_path / "out")

    assert _count(result.path) == 15


def test_scaling_down_drops_trips_to_the_rounded_target_count(tmp_path: Path) -> None:
    trips = artifact_ref(_trips_file(tmp_path, 10), "trips")

    result = SumoDemandScaler().scale(trips, 0.5, tmp_path / "out")

    assert _count(result.path) == 5


def test_scaling_by_one_keeps_every_original_trip_once(tmp_path: Path) -> None:
    trips = artifact_ref(_trips_file(tmp_path, 10), "trips")

    result = SumoDemandScaler().scale(trips, 1.0, tmp_path / "out")

    assert _ids(result.path) == [f"t_{i}" for i in range(10)]


def test_duplicated_trips_get_a_unique_suffixed_id_and_keep_the_original_attributes(
    tmp_path: Path,
) -> None:
    trips = artifact_ref(_trips_file(tmp_path, 1), "trips")

    result = SumoDemandScaler().scale(trips, 3.0, tmp_path / "out")

    ids = _ids(result.path)
    assert ids == ["t_0", "t_0_x1", "t_0_x2"]
    attribs = [t.attrib for t in ET.parse(result.path).getroot().findall("trip")]
    assert all(a["depart"] == "0.00" and a["from"] == "A0A1" and a["to"] == "B0B1" for a in attribs)


def test_scaling_is_deterministic(tmp_path: Path) -> None:
    trips = artifact_ref(_trips_file(tmp_path, 7), "trips")
    scaler = SumoDemandScaler()

    a = scaler.scale(trips, 1.7, tmp_path / "a")
    b = scaler.scale(trips, 1.7, tmp_path / "b")

    assert a.path.read_text(encoding="utf-8") == b.path.read_text(encoding="utf-8")


def test_rejects_a_non_positive_factor(tmp_path: Path) -> None:
    trips = artifact_ref(_trips_file(tmp_path, 3), "trips")
    with pytest.raises(ValueError):
        SumoDemandScaler().scale(trips, 0.0, tmp_path / "out")
