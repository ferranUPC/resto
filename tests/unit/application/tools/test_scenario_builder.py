"""Scenario Builder tools (E2.2): id checks against NetworkMCP, the two writer tools, and
`write_sumocfg` (E2.1) — delegation only, no logic of its own (ADR-0007, ADR-0009)."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.writers import SimulationSettings
from resto.application.tools.scenario_builder import (
    build_scenario_builder_tools,
    edge_exists,
    lane_exists,
    write_rerouter,
    write_sumocfg,
    write_vss,
)
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.time_window import TimeWindow

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"
LANE = LaneTarget(edge_id="A0A1", lane_index=0)


@pytest.fixture(scope="module")
def query() -> SumolibNetworkQuery:
    return SumolibNetworkQuery(DEV_NET)


class RecordingWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[SimulationSettings, Path, str]] = []

    def write(self, settings: SimulationSettings, out_dir: Path, name: str) -> ArtifactRef:
        self.calls.append((settings, out_dir, name))
        return ArtifactRef(path=out_dir / name, content_hash="h", kind="sumocfg")


class RecordingAdditionalFileWriter:
    """Fake `AdditionalFileWriter`: records calls, returns a canned (mechanism, ArtifactRef)."""

    def __init__(self) -> None:
        self.calls: list[tuple[Intervention, Path]] = []

    def supports(self, intervention: Intervention) -> bool:
        return True

    def write(
        self, intervention: Intervention, out_dir: Path
    ) -> tuple[StaticFileMechanism, ArtifactRef]:
        self.calls.append((intervention, out_dir))
        path = (out_dir / "closure.add.xml").resolve()
        return StaticFileMechanism(file_kind="rerouter", path=path), ArtifactRef(
            path=path, content_hash="deadbeef", kind="additional"
        )


def lane_closure() -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE, target=LANE, window=TimeWindow(0, 3600)
    )


# --- id checks -------------------------------------------------------------------------------


def test_edge_exists_delegates_to_the_query(query: NetworkQuery) -> None:
    assert edge_exists(query, "A0A1") is True
    assert edge_exists(query, "NOPE") is False


def test_lane_exists_delegates_to_the_query(query: NetworkQuery) -> None:
    assert lane_exists(query, "A0A1", 0) is True
    assert lane_exists(query, "A0A1", 5) is False


# --- writer tools ------------------------------------------------------------------------------


def test_write_rerouter_delegates_and_flattens_the_result(tmp_path: Path) -> None:
    writer = RecordingAdditionalFileWriter()
    intervention = lane_closure()

    result = write_rerouter(writer, intervention, tmp_path)

    assert writer.calls == [(intervention, tmp_path)]
    assert result == {
        "file_kind": "rerouter",
        "path": str((tmp_path / "closure.add.xml").resolve()),
        "content_hash": "deadbeef",
    }


def test_write_vss_delegates_and_flattens_the_result(tmp_path: Path) -> None:
    writer = RecordingAdditionalFileWriter()
    intervention = lane_closure()

    result = write_vss(writer, intervention, tmp_path)

    assert writer.calls == [(intervention, tmp_path)]
    assert result["file_kind"] == "rerouter"  # the fake writer always reports this file_kind


# --- write_sumocfg (E2.1) -----------------------------------------------------------------------


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


# --- build_scenario_builder_tools ----------------------------------------------------------------


def _builder_tools(  # noqa: ANN201
    tmp_path: Path,
    rerouter_writer=None,  # noqa: ANN001
    vss_writer=None,  # noqa: ANN001
    sumocfg_writer=None,  # noqa: ANN001
    query=None,  # noqa: ANN001
):
    return build_scenario_builder_tools(
        query=query or SumolibNetworkQuery(DEV_NET),
        interventions=(lane_closure(),),
        net_file=Path("net.xml"),
        route_files=(Path("routes.rou.xml"),),
        begin=0.0,
        end=3600.0,
        rerouter_writer=rerouter_writer or RecordingAdditionalFileWriter(),
        vss_writer=vss_writer or RecordingAdditionalFileWriter(),
        sumocfg_writer=sumocfg_writer or RecordingWriter(),
        out_dir=tmp_path,
    )


def test_builds_exactly_the_e2_2_minimal_tool_set(tmp_path: Path) -> None:
    tools = _builder_tools(tmp_path)
    assert [t.name for t in tools] == [
        "edge_exists",
        "lane_exists",
        "write_rerouter",
        "write_vss",
        "write_sumocfg",
    ]


def test_bound_edge_exists_and_lane_exists_use_the_given_query(tmp_path: Path) -> None:
    tools = {t.name: t for t in _builder_tools(tmp_path)}
    assert tools["edge_exists"].fn(edge_id="A0A1") is True
    assert tools["edge_exists"].fn(edge_id="NOPE") is False
    assert tools["lane_exists"].fn(edge_id="A0A1", lane_index=0) is True


def test_bound_write_rerouter_looks_up_the_intervention_by_index(tmp_path: Path) -> None:
    rerouter_writer = RecordingAdditionalFileWriter()
    tools = {t.name: t for t in _builder_tools(tmp_path, rerouter_writer=rerouter_writer)}

    result = tools["write_rerouter"].fn(intervention_index=0)

    assert rerouter_writer.calls == [(lane_closure(), tmp_path)]
    assert result["file_kind"] == "rerouter"


def test_bound_write_sumocfg_takes_no_arguments_and_includes_written_files(tmp_path: Path) -> None:
    rerouter_writer = RecordingAdditionalFileWriter()
    sumocfg_writer = RecordingWriter()
    tools = {
        t.name: t
        for t in _builder_tools(
            tmp_path, rerouter_writer=rerouter_writer, sumocfg_writer=sumocfg_writer
        )
    }

    tools["write_rerouter"].fn(intervention_index=0)
    result = tools["write_sumocfg"].fn()

    ((settings, out_dir, name),) = sumocfg_writer.calls
    assert settings.additional_files == ((tmp_path / "closure.add.xml").resolve(),)
    assert result["kind"] == "sumocfg"


def test_bound_write_sumocfg_with_nothing_written_has_no_additional_files(tmp_path: Path) -> None:
    sumocfg_writer = RecordingWriter()
    tools = {t.name: t for t in _builder_tools(tmp_path, sumocfg_writer=sumocfg_writer)}

    tools["write_sumocfg"].fn()

    ((settings, _, _),) = sumocfg_writer.calls
    assert settings.additional_files == ()
