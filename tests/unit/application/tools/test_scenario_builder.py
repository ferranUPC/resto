"""Scenario Builder tools (E2.2/E2.3): id checks against NetworkMCP, the writer tools,
`scale_demand`, and `write_sumocfg` (E2.1) — delegation only, no logic of its own (ADR-0007,
ADR-0009)."""

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
    scale_demand,
    write_rerouter,
    write_sumocfg,
    write_tls_program,
    write_vss,
)
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"
LANE = LaneTarget(edge_id="A0A1", lane_index=0)


class RecordingDemandScaler:
    def __init__(self, result: ArtifactRef | None = None) -> None:
        self.calls: list[tuple[ArtifactRef, float, Path]] = []
        self._result = result or ArtifactRef(
            path=Path("scaled.trips.xml"), content_hash="scaled1", kind="trips"
        )

    def scale(self, trips: ArtifactRef, factor: float, out_dir: Path) -> ArtifactRef:
        self.calls.append((trips, factor, out_dir))
        return self._result


class RecordingDuarouter:
    def __init__(self, result: ArtifactRef | None = None) -> None:
        self.calls: list[tuple[ArtifactRef, ArtifactRef, int, Path]] = []
        self._result = result or ArtifactRef(
            path=Path("scaled.rou.xml"), content_hash="routed1", kind="routes"
        )

    def duarouter(
        self, net_xml: ArtifactRef, trips: ArtifactRef, seed: int, out_dir: Path
    ) -> ArtifactRef:
        self.calls.append((net_xml, trips, seed, out_dir))
        return self._result

    def random_trips(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        raise AssertionError("not used")

    def route_sampler(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN201
        raise AssertionError("not used")


class RecordingDemandRepository:
    def __init__(self) -> None:
        self.stored: list = []  # noqa: ANN001

    def store(self, demand) -> None:  # noqa: ANN001
        self.stored.append(demand)

    def get(self, demand_id: str):  # noqa: ANN201
        return next((d for d in self.stored if d.demand_id == demand_id), None)

    def list(self, network_id: str):  # noqa: ANN201
        return [d for d in self.stored if d.network_id == network_id]


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


def demand_scale_intervention(scale: float = 1.2) -> Intervention:
    return Intervention(
        type=InterventionType.DEMAND_SCALE,
        target=None,
        window=TimeWindow(0, 3600),
        params={"scale": scale},
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


def test_write_tls_program_delegates_and_flattens_the_result(tmp_path: Path) -> None:
    writer = RecordingAdditionalFileWriter()
    intervention = lane_closure()

    result = write_tls_program(writer, intervention, tmp_path)

    assert writer.calls == [(intervention, tmp_path)]
    assert result["file_kind"] == "rerouter"  # the fake writer always reports this file_kind


# --- scale_demand (E2.3) ------------------------------------------------------------------------


def test_scale_demand_delegates_through_the_use_case(tmp_path: Path) -> None:
    scaler = RecordingDemandScaler()
    duarouter = RecordingDuarouter()
    demands = RecordingDemandRepository()
    demand = sample_demand()
    network = sample_network()

    result = scale_demand(
        demand, network, 1.2, scaler=scaler, duarouter=duarouter, demands=demands, out_dir=tmp_path
    )

    assert scaler.calls == [(demand.trips, 1.2, tmp_path)]
    assert duarouter.calls == [(network.net_xml, scaler._result, demand.spec.seed, tmp_path)]
    assert result == {"demand_id": "scaled1", "routes_path": str(Path("scaled.rou.xml"))}
    assert demands.stored[0].demand_id == "scaled1"


def test_scale_demand_surfaces_a_network_mismatch(tmp_path: Path) -> None:
    demand = sample_demand()
    network = sample_network()
    from dataclasses import replace

    with pytest.raises(ValueError):
        scale_demand(
            replace(demand, network_id="other"),
            network,
            1.2,
            scaler=RecordingDemandScaler(),
            duarouter=RecordingDuarouter(),
            demands=RecordingDemandRepository(),
            out_dir=tmp_path,
        )


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
    tls_program_writer=None,  # noqa: ANN001
    sumocfg_writer=None,  # noqa: ANN001
    query=None,  # noqa: ANN001
    demand_scaler=None,  # noqa: ANN001
    duarouter=None,  # noqa: ANN001
    demands=None,  # noqa: ANN001
    interventions=None,  # noqa: ANN001
):
    return build_scenario_builder_tools(
        query=query or SumolibNetworkQuery(DEV_NET),
        interventions=interventions if interventions is not None else (lane_closure(),),
        net_file=Path("net.xml"),
        route_files=(Path("routes.rou.xml"),),
        begin=0.0,
        end=3600.0,
        rerouter_writer=rerouter_writer or RecordingAdditionalFileWriter(),
        vss_writer=vss_writer or RecordingAdditionalFileWriter(),
        tls_program_writer=tls_program_writer or RecordingAdditionalFileWriter(),
        sumocfg_writer=sumocfg_writer or RecordingWriter(),
        demand=sample_demand(),
        network=sample_network(),
        demand_scaler=demand_scaler or RecordingDemandScaler(),
        duarouter=duarouter or RecordingDuarouter(),
        demands=demands or RecordingDemandRepository(),
        out_dir=tmp_path,
    )


def test_builds_exactly_the_e2_3_tool_set(tmp_path: Path) -> None:
    tools = _builder_tools(tmp_path)
    assert [t.name for t in tools] == [
        "edge_exists",
        "lane_exists",
        "write_rerouter",
        "write_vss",
        "write_tls_program",
        "scale_demand",
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


def test_bound_write_tls_program_looks_up_the_intervention_by_index(tmp_path: Path) -> None:
    tls_program_writer = RecordingAdditionalFileWriter()
    tools = {t.name: t for t in _builder_tools(tmp_path, tls_program_writer=tls_program_writer)}

    result = tools["write_tls_program"].fn(intervention_index=0)

    assert tls_program_writer.calls == [(lane_closure(), tmp_path)]
    assert result["file_kind"] == "rerouter"  # the fake writer always reports this file_kind


def test_bound_scale_demand_looks_up_the_intervention_and_applies_its_scale(
    tmp_path: Path,
) -> None:
    scaler = RecordingDemandScaler()
    duarouter = RecordingDuarouter()
    tools = {
        t.name: t
        for t in _builder_tools(
            tmp_path,
            interventions=(demand_scale_intervention(scale=1.5),),
            demand_scaler=scaler,
            duarouter=duarouter,
        )
    }

    result = tools["scale_demand"].fn(intervention_index=0)

    assert scaler.calls == [(sample_demand().trips, 1.5, tmp_path)]
    assert result["demand_id"] == "scaled1"


def test_bound_write_sumocfg_uses_the_scaled_routes_once_scale_demand_ran(tmp_path: Path) -> None:
    sumocfg_writer = RecordingWriter()
    tools = {
        t.name: t
        for t in _builder_tools(
            tmp_path,
            interventions=(demand_scale_intervention(),),
            sumocfg_writer=sumocfg_writer,
        )
    }

    tools["scale_demand"].fn(intervention_index=0)
    tools["write_sumocfg"].fn()

    ((settings, _, _),) = sumocfg_writer.calls
    assert settings.route_files == (Path("scaled.rou.xml"),)


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
    assert settings.route_files == (Path("routes.rou.xml"),)  # unscaled default
