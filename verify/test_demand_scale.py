"""`demand_scale` effect verification (work-plan E2.4, DoD §4.5) on DEV-NET with real SUMO:
departed vehicle count lands within +-5% of the scaled trip count, running the actual
`SumoDemandScaler` + `SumoDemandTools.duarouter` pipeline (E2.3) end to end, not a fake."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.sumo.demand import SumoDemandTools
from resto.adapters.sumo.demand_scaling import SumoDemandScaler
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from verify.effects import count_scheduled_vehicles, verify_demand_scale

DEV_NET_DIR = Path(__file__).resolve().parent.parent / "eval" / "dev-net"
NET = artifact_ref(DEV_NET_DIR / "dev-net.net.xml", "net")
LOW_TRIPS = artifact_ref(DEV_NET_DIR / "demand" / "low.trips.xml", "trips")
FACTOR = 1.5


@pytest.fixture(scope="module")
def scaled_scenario_cfg(tmp_path_factory: pytest.TempPathFactory) -> ArtifactRef:
    out_dir = tmp_path_factory.mktemp("demand_scale")
    scaled_trips = SumoDemandScaler().scale(LOW_TRIPS, FACTOR, out_dir)
    routes = SumoDemandTools().duarouter(NET, scaled_trips, seed=1, out_dir=out_dir)
    settings = SimulationSettings(net_file=NET.path, route_files=(routes.path,))
    return SumocfgFileWriter().write(settings, out_dir, "scenario.sumocfg")


def test_demand_scale_departed_count_matches_the_scaled_factor(
    scaled_scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner().run_batch(scaled_scenario_cfg, seed=1, out_dir=tmp_path / "r")
    assert output.ok, output.error
    assert output.kpis is not None

    expected = round(count_scheduled_vehicles(LOW_TRIPS.path) * FACTOR)
    result = verify_demand_scale(output.kpis.departed, expected)
    assert result.ok, result.reason
