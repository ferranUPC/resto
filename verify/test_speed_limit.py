"""`speed_limit` effect verification (work-plan E2.4, DoD §4.5) on DEV-NET with real SUMO: mean
speed on the affected edge stays at or below the limit (+10% tolerance) during the window."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.outputs import parse_edgedata
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.adapters.sumo.writers.vss import VssWriter
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.time_window import TimeWindow
from verify.effects import verify_speed_limit

DEV_NET_DIR = Path(__file__).resolve().parent.parent / "eval" / "dev-net"
NET = DEV_NET_DIR / "dev-net.net.xml"
PEAK_ROUTES = DEV_NET_DIR / "demand" / "peak.rou.xml"
EDGE = "B2C2"
BEGIN_S = 28800.0  # 08:00, the peak demand's first departure (ADR-0028)
WINDOW = TimeWindow(28800.0, 29100.0)
END_S = 29400.0
LIMIT_MPS = 5.0


@pytest.fixture(scope="module")
def speed_limit_cfg(tmp_path_factory: pytest.TempPathFactory) -> ArtifactRef:
    out_dir = tmp_path_factory.mktemp("speed_limit")
    intervention = Intervention(
        type=InterventionType.SPEED_LIMIT,
        target=LaneTarget(edge_id=EDGE, lane_index=0),
        window=WINDOW,
        params={"speed": LIMIT_MPS, "revert_speed": 13.89},
    )
    _, vss_ref = VssWriter().write(intervention, out_dir)
    settings = SimulationSettings(
        net_file=NET, route_files=(PEAK_ROUTES,), additional_files=(vss_ref.path,),
        begin=BEGIN_S, end=END_S,
    )
    return SumocfgFileWriter().write(settings, out_dir, "scenario.sumocfg")


def test_speed_limit_caps_the_mean_speed_in_the_window(
    speed_limit_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner().run_batch(speed_limit_cfg, seed=1, out_dir=tmp_path / "r")
    assert output.ok, output.error

    edgedata_path = next(a.path for a in output.artifacts if a.kind == "edgedata")
    result = verify_speed_limit(parse_edgedata(edgedata_path), EDGE, WINDOW, LIMIT_MPS)
    assert result.ok, result.reason
