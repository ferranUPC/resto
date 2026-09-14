"""`write_sumocfg` tool (E2.1): packs its LLM-facing arguments into `SimulationSettings` and
delegates to the writer port."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.application.ports.writers import SimulationSettings
from resto.application.tools.scenario_builder import write_sumocfg
from resto.domain.value_objects.artifact_ref import ArtifactRef


class RecordingWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[SimulationSettings, Path, str]] = []

    def write(self, settings: SimulationSettings, out_dir: Path, name: str) -> ArtifactRef:
        self.calls.append((settings, out_dir, name))
        return ArtifactRef(path=out_dir / name, content_hash="h", kind="sumocfg")


def test_write_sumocfg_builds_the_settings_and_delegates(tmp_path: Path) -> None:
    writer = RecordingWriter()

    ref = write_sumocfg(
        writer,
        Path("net.xml"),
        [Path("a.rou.xml"), Path("b.rou.xml")],
        tmp_path,
        additional_files=[Path("x.add.xml")],
        begin=0,
        end=3600,
    )

    assert ref.kind == "sumocfg"
    ((settings, out_dir, name),) = writer.calls
    assert settings == SimulationSettings(
        net_file=Path("net.xml"),
        route_files=(Path("a.rou.xml"), Path("b.rou.xml")),
        additional_files=(Path("x.add.xml"),),
        begin=0,
        end=3600,
    )
    assert (out_dir, name) == (tmp_path, "scenario.sumocfg")


def test_write_sumocfg_surfaces_invalid_settings(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_sumocfg(RecordingWriter(), Path("net.xml"), [], tmp_path)
