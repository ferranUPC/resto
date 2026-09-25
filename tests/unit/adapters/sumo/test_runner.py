"""`SubprocessSumoRunner` batch mode on DEV-NET with real SUMO (E2.1, DoD §4.6): a run cfg SUMO
can replay by itself, the expected artifacts and KPIs, interval edgedata, SUMO errors captured
with SUMO's message, and byte-identical reproducibility over 20 runs.

Reproducibility is checked on the cfg, the additional, edgedata and tripinfo. `summary-output`
carries a per-step `duration` (computation time, ms) and `statistic-output` a `<performance>`
clock, so neither can be byte-identical across runs and neither enters `content_hash` (ADR-0017).

The cfg simulates the first 10 min of the `low` profile so the 20-run check stays fast; the
determinism it checks does not depend on the window length.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from resto.adapters.sumo.outputs import canonical_bytes
from resto.adapters.sumo.runner import (
    EDGEDATA_PERIOD_S,
    RUN_CFG_NAME,
    SubprocessSumoRunner,
    _has_rerouter,
)
from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter, write_edgedata_additional
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.time_window import TimeWindow

DEV_NET_DIR = Path(__file__).resolve().parents[4] / "eval" / "dev-net"
NET = DEV_NET_DIR / "dev-net.net.xml"
LOW_ROUTES = DEV_NET_DIR / "demand" / "low.rou.xml"
PEAK_ROUTES = DEV_NET_DIR / "demand" / "peak.rou.xml"
BEGIN_S = 28800.0  # 08:00, the demand profiles' first departure (ADR-0028)
END_S = 29400.0


@pytest.fixture(scope="module")
def scenario_cfg(tmp_path_factory: pytest.TempPathFactory) -> ArtifactRef:
    out_dir = tmp_path_factory.mktemp("scenario")
    settings = SimulationSettings(
        net_file=NET, route_files=(LOW_ROUTES,), begin=BEGIN_S, end=END_S
    )
    return SumocfgFileWriter().write(settings, out_dir, "scenario.sumocfg")


@pytest.fixture(scope="module")
def closure_scenario_cfg(tmp_path_factory: pytest.TempPathFactory) -> ArtifactRef:
    """A `lane_closure` on B2C2, an interior DEV-NET edge (three incoming, three outgoing
    connections at its junctions - not a fringe dead end), on the `peak` profile."""
    out_dir = tmp_path_factory.mktemp("closure_scenario")
    closure = Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LaneTarget(edge_id="B2C2", lane_index=0),
        window=TimeWindow(28900.0, 29100.0),
    )
    _, rerouter_ref = RerouterWriter().write(closure, out_dir)
    settings = SimulationSettings(
        net_file=NET, route_files=(PEAK_ROUTES,), additional_files=(rerouter_ref.path,),
        begin=BEGIN_S, end=END_S,
    )
    return SumocfgFileWriter().write(settings, out_dir, "scenario.sumocfg")


def _kinds(artifacts: tuple[ArtifactRef, ...]) -> dict[str, ArtifactRef]:
    return {a.kind: a for a in artifacts}


def test_has_rerouter_detects_a_rerouter_additional_file(tmp_path: Path) -> None:
    closure = Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LaneTarget(edge_id="A0A1", lane_index=0),
        window=TimeWindow(0.0, 60.0),
    )
    _, rerouter_ref = RerouterWriter().write(closure, tmp_path)
    edgedata_add = write_edgedata_additional(tmp_path, EDGEDATA_PERIOD_S, "probe_edgedata.xml")

    assert _has_rerouter((rerouter_ref.path,)) is True
    assert _has_rerouter((edgedata_add,)) is False
    assert _has_rerouter(()) is False


def test_a_lane_closure_scenario_completes_despite_an_unroutable_vehicle(
    closure_scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    """Without `--ignore-route-errors`, this exact scenario hard-fails with "no valid route" (a
    `peak` vehicle has no alternate path once B2C2 is closed) on every DEV-NET location tried
    while building E2.4, not just this one - confirmed empirically, see the module docstring."""
    output = SubprocessSumoRunner().run_batch(closure_scenario_cfg, seed=1, out_dir=tmp_path / "r")

    assert output.ok is True, output.error


def test_a_scenario_without_a_rerouter_does_not_get_ignore_route_errors(
    scenario_cfg: ArtifactRef, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_commands: list[list[str]] = []
    real_run = subprocess.run

    def spy(command, **kwargs):  # noqa: ANN001, ANN201
        seen_commands.append(list(command))
        return real_run(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)

    SubprocessSumoRunner().run_batch(scenario_cfg, seed=1, out_dir=tmp_path / "r")

    assert seen_commands and "--ignore-route-errors" not in seen_commands[0]


def test_batch_run_succeeds_with_kpis_and_the_five_output_artifacts(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner().run_batch(scenario_cfg, seed=1, out_dir=tmp_path / "r")

    assert output.ok is True, output.error
    assert output.error is None
    assert output.wall_clock_s > 0
    assert set(_kinds(output.artifacts)) == {
        "sumocfg",
        "additional",
        "edgedata",
        "tripinfo",
        "summary",
        "statistics",
    }
    assert output.kpis is not None
    assert output.kpis.departed > 0
    assert 0 < output.kpis.arrived <= output.kpis.departed
    assert output.kpis.mean_travel_time > 0


def test_run_cfg_is_self_contained_and_replayable_by_sumo_alone(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner().run_batch(scenario_cfg, seed=3, out_dir=tmp_path / "r")
    run_cfg = _kinds(output.artifacts)["sumocfg"].path
    text = run_cfg.read_text()

    assert run_cfg.name == RUN_CFG_NAME
    assert '<seed value="3" />' in text
    assert "<statistic-output" in text and "<tripinfo-output" in text
    assert '<duration-log.statistics value="true" />' in text
    assert str(tmp_path) not in text, "run cfg must not embed absolute paths"

    replay = tmp_path / "replay"
    replay.mkdir()
    for artifact in output.artifacts:
        if artifact.kind in ("sumocfg", "additional"):
            (replay / artifact.path.name).write_bytes(artifact.path.read_bytes())
    # the cfg's relative inputs point one level up from the run dir, so replay must sit beside it
    proc = subprocess.run(
        ["sumo", "-c", str(replay / RUN_CFG_NAME)], capture_output=True, text=True, cwd="/"
    )

    assert proc.returncode == 0, proc.stderr
    assert canonical_bytes(replay / "edgedata.xml") == canonical_bytes(
        _kinds(output.artifacts)["edgedata"].path
    )


def test_edgedata_is_aggregated_in_fixed_intervals(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner().run_batch(scenario_cfg, seed=1, out_dir=tmp_path / "r")
    root = ET.parse(_kinds(output.artifacts)["edgedata"].path).getroot()
    intervals = [
        (float(i.get("begin", 0)), float(i.get("end", 0))) for i in root.findall("interval")
    ]

    assert len(intervals) == (END_S - BEGIN_S) / EDGEDATA_PERIOD_S
    assert intervals[0] == (BEGIN_S, BEGIN_S + EDGEDATA_PERIOD_S)  # aligned to SUMO's begin
    assert all(end - begin == EDGEDATA_PERIOD_S for begin, end in intervals)


def test_a_sumo_error_marks_the_run_failed_with_sumos_message(tmp_path: Path) -> None:
    broken_routes = tmp_path / "broken.rou.xml"
    broken_routes.write_text(
        '<routes><vehicle id="v" depart="0"><route edges="NOPE"/></vehicle></routes>'
    )
    settings = SimulationSettings(net_file=NET, route_files=(broken_routes,), end=10.0)
    cfg = SumocfgFileWriter().write(settings, tmp_path / "s", "scenario.sumocfg")

    output = SubprocessSumoRunner().run_batch(cfg, seed=1, out_dir=tmp_path / "r")

    assert output.ok is False
    assert output.kpis is None
    assert output.error is not None and "NOPE" in output.error
    assert set(_kinds(output.artifacts)) == {"sumocfg", "additional"}


def test_a_cfg_with_a_seed_is_rejected_before_sumo_starts(tmp_path: Path) -> None:
    cfg_path = tmp_path / "run.sumocfg"
    cfg_path.write_text(
        "<configuration><input><net-file value='n'/><route-files value='r'/></input>"
        "<random_number><seed value='1'/></random_number></configuration>"
    )
    cfg = ArtifactRef(path=cfg_path, content_hash="x", kind="sumocfg")

    output = SubprocessSumoRunner().run_batch(cfg, seed=1, out_dir=tmp_path / "r")

    assert output.ok is False
    assert output.error is not None and "random_number" in output.error


def test_a_missing_sumo_binary_is_a_failed_run_not_an_exception(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner(sumo_binary="sumo-does-not-exist").run_batch(
        scenario_cfg, seed=1, out_dir=tmp_path / "r"
    )

    assert output.ok is False
    assert output.error


def test_twenty_runs_with_the_same_seed_are_byte_identical(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    runner = SubprocessSumoRunner()
    hashes = set()
    for i in range(20):
        output = runner.run_batch(scenario_cfg, seed=42, out_dir=tmp_path / f"run{i}")
        assert output.ok, output.error
        kinds = _kinds(output.artifacts)
        hashes.add(
            tuple(kinds[k].content_hash for k in ("sumocfg", "additional", "edgedata", "tripinfo"))
        )

    assert len(hashes) == 1


def test_a_different_seed_changes_the_edgedata(scenario_cfg: ArtifactRef, tmp_path: Path) -> None:
    runner = SubprocessSumoRunner()
    a = runner.run_batch(scenario_cfg, seed=1, out_dir=tmp_path / "a")
    b = runner.run_batch(scenario_cfg, seed=2, out_dir=tmp_path / "b")

    assert (
        _kinds(a.artifacts)["edgedata"].content_hash != _kinds(b.artifacts)["edgedata"].content_hash
    )
