"""`lane_closure` effect verification (work-plan E2.4, DoD §4.5) on DEV-NET with real SUMO:
zero flow on the closed edge during the window, nonzero outside, >=90% of scheduled vehicles
still depart despite the closure.

B2C2 (an interior, single-lane, three-way-connected junction pair - not a fringe dead end) and
window `[0, 300)` are not arbitrary: they are exactly what made the Runner's `--ignore-route-errors`
fix and the edgedata-period-alignment requirement reproducible - see `adapters/sumo/runner.py`'s
and this package's own docstrings.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.outputs import parse_edgedata
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.time_window import TimeWindow
from verify.effects import count_scheduled_vehicles, verify_completion_rate, verify_edge_flow

DEV_NET_DIR = Path(__file__).resolve().parent.parent / "eval" / "dev-net"
NET = DEV_NET_DIR / "dev-net.net.xml"
PEAK_ROUTES = DEV_NET_DIR / "demand" / "peak.rou.xml"
EDGE = "B2C2"
WINDOW = TimeWindow(0.0, 300.0)
END_S = 600.0


@pytest.fixture(scope="module")
def closure_cfg(tmp_path_factory: pytest.TempPathFactory) -> ArtifactRef:
    out_dir = tmp_path_factory.mktemp("lane_closure")
    closure = Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LaneTarget(edge_id=EDGE, lane_index=0),
        window=WINDOW,
    )
    _, rerouter_ref = RerouterWriter().write(closure, out_dir)
    settings = SimulationSettings(
        net_file=NET, route_files=(PEAK_ROUTES,), additional_files=(rerouter_ref.path,), end=END_S
    )
    return SumocfgFileWriter().write(settings, out_dir, "scenario.sumocfg")


def test_lane_closure_zeroes_flow_in_the_window_and_completes_most_departures(
    closure_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner().run_batch(closure_cfg, seed=1, out_dir=tmp_path / "r")
    assert output.ok, output.error
    assert output.kpis is not None

    edgedata_path = next(a.path for a in output.artifacts if a.kind == "edgedata")
    flow = verify_edge_flow(parse_edgedata(edgedata_path), EDGE, WINDOW)
    assert flow.ok, flow.reason

    scheduled = count_scheduled_vehicles(PEAK_ROUTES, before=END_S)
    completion = verify_completion_rate(output.kpis.departed, scheduled)
    assert completion.ok, completion.reason
