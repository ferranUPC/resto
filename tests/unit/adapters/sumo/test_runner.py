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

import inspect
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from resto.adapters.sumo.constants import APPLIED_ACTIONS_FILE
from resto.adapters.sumo.outputs import canonical_bytes
from resto.adapters.sumo.runner import (
    EDGEDATA_PERIOD_S,
    RUN_CFG_NAME,
    SubprocessSumoRunner,
    _has_rerouter,
)
from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter, write_edgedata_additional
from resto.application.ports.sumo import DryRunOutcome
from resto.application.ports.writers import SimulationSettings
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.traci_script import (
    AtTime,
    CloseLane,
    Rule,
    SetSpeed,
    SetTlsProgram,
    TraciScript,
)

DEV_NET_DIR = Path(__file__).resolve().parents[4] / "eval" / "dev-net"
NET = DEV_NET_DIR / "dev-net.net.xml"
LOW_ROUTES = DEV_NET_DIR / "demand" / "low.rou.xml"
PEAK_ROUTES = DEV_NET_DIR / "demand" / "peak.rou.xml"
BEGIN_S = 28800.0  # 08:00, the demand profiles' first departure (ADR-0028)
END_S = 29400.0


@pytest.fixture(scope="module")
def scenario_cfg(tmp_path_factory: pytest.TempPathFactory) -> ArtifactRef:
    out_dir = tmp_path_factory.mktemp("scenario")
    settings = SimulationSettings(net_file=NET, route_files=(LOW_ROUTES,), begin=BEGIN_S, end=END_S)
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
        net_file=NET,
        route_files=(PEAK_ROUTES,),
        additional_files=(rerouter_ref.path,),
        begin=BEGIN_S,
        end=END_S,
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

    sumo_runs = [c for c in seen_commands if "-c" in c]  # not the one-off `sumo --version`
    assert sumo_runs and "--ignore-route-errors" not in sumo_runs[0]


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


def test_the_runner_reports_the_checked_sumo_version() -> None:
    assert SubprocessSumoRunner().sumo_version() == "1.27.1"


# Online mode (E2.5, ADR-0044)

ONLINE_SCRIPT = TraciScript(rules=(Rule(AtTime(BEGIN_S + 60), SetSpeed("C0D0", 5.0)),))


def test_an_online_run_succeeds_with_kpis_the_script_artifact_and_the_applied_actions(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner().run_online(
        scenario_cfg, ONLINE_SCRIPT, seed=1, out_dir=tmp_path / "r"
    )

    assert output.ok, output.error
    assert output.kpis is not None and output.kpis.departed > 0
    kinds = _kinds(output.artifacts)
    assert set(kinds) == {
        "sumocfg", "additional", "script", "edgedata", "tripinfo", "summary", "statistics",
    }  # fmt: skip
    assert kinds["script"].path.name == "script.py"
    (applied,) = output.applied_actions
    assert applied.action == "set_speed"
    assert applied.step == BEGIN_S + 60


def test_twenty_online_runs_with_the_same_seed_are_byte_identical(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    runner = SubprocessSumoRunner()
    hashes = set()
    for i in range(20):
        output = runner.run_online(
            scenario_cfg, ONLINE_SCRIPT, seed=42, out_dir=tmp_path / f"run{i}"
        )
        assert output.ok, output.error
        kinds = _kinds(output.artifacts)
        hashes.add(
            tuple(
                kinds[k].content_hash
                for k in ("sumocfg", "additional", "script", "edgedata", "tripinfo")
            )
        )

    assert len(hashes) == 1


def test_an_online_run_gives_the_batch_edgedata_when_no_rule_fires(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    runner = SubprocessSumoRunner()
    never = TraciScript(rules=(Rule(AtTime(BEGIN_S + 10_000_000), SetSpeed("C0D0", 5.0)),))

    batch = runner.run_batch(scenario_cfg, seed=7, out_dir=tmp_path / "batch")
    online = runner.run_online(scenario_cfg, never, seed=7, out_dir=tmp_path / "online")

    assert online.ok, online.error
    assert online.applied_actions == ()
    assert (
        _kinds(online.artifacts)["edgedata"].content_hash
        == _kinds(batch.artifacts)["edgedata"].content_hash
    )


def _last_summary_time(run_dir: Path) -> float:
    return float(ET.parse(run_dir / "summary.xml").getroot()[-1].get("time", "nan"))


@pytest.mark.parametrize("window_s", [3600, 900], ids=["full_hour", "cut_mid_demand"])
def test_an_online_run_over_the_peak_ends_at_the_cfg_end_like_batch(
    tmp_path: Path, window_s: int
) -> None:
    """The 900 s window leaves vehicles in the network at `end`: an online run that drained them
    instead of stopping at `end` would simulate (and write tripinfo and summary) past it."""
    settings = SimulationSettings(
        net_file=NET, route_files=(PEAK_ROUTES,), begin=BEGIN_S, end=BEGIN_S + window_s
    )
    cfg = SumocfgFileWriter().write(settings, tmp_path, "peak.sumocfg")
    runner = SubprocessSumoRunner()
    never = TraciScript(rules=(Rule(AtTime(BEGIN_S + 10_000_000), SetSpeed("C0D0", 5.0)),))

    batch = runner.run_batch(cfg, seed=1, out_dir=tmp_path / "batch")
    online = runner.run_online(cfg, never, seed=1, out_dir=tmp_path / "online")

    assert batch.ok and online.ok, (batch.error, online.error)
    for name in ("edgedata.xml", "tripinfo.xml"):
        assert canonical_bytes(tmp_path / "online" / name) == canonical_bytes(
            tmp_path / "batch" / name
        ), name
    assert _last_summary_time(tmp_path / "online") == _last_summary_time(tmp_path / "batch")


def test_a_missing_sumo_binary_is_a_failed_online_run_not_an_exception(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    output = SubprocessSumoRunner(sumo_binary="sumo-does-not-exist").run_online(
        scenario_cfg, ONLINE_SCRIPT, seed=1, out_dir=tmp_path / "r"
    )

    assert output.ok is False
    assert output.error


def test_a_missing_sumo_binary_is_a_failed_dry_run_not_an_exception(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    outcome = SubprocessSumoRunner(sumo_binary="sumo-does-not-exist").dry_run(
        scenario_cfg, ONLINE_SCRIPT, tmp_path / "r"
    )

    assert outcome.ok is False
    assert outcome.error


def test_an_action_sumo_rejects_at_run_time_fails_the_run_with_the_traceback(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    script = TraciScript(rules=(Rule(AtTime(BEGIN_S + 60), CloseLane("NO_SUCH_EDGE", 0)),))

    output = SubprocessSumoRunner().run_online(scenario_cfg, script, seed=1, out_dir=tmp_path / "r")

    assert output.ok is False
    assert output.error is not None
    assert "Traceback" in output.error
    assert "NO_SUCH_EDGE" in output.error
    assert "script" in _kinds(output.artifacts)


def test_exit_zero_without_the_applied_actions_file_is_a_failure(
    scenario_cfg: ArtifactRef, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_popen = subprocess.Popen

    def popen_noop(command, **kwargs):  # noqa: ANN001, ANN201
        # A harness that exits 0 without writing anything.
        return real_popen([sys.executable, "-c", "pass"], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", popen_noop)

    output = SubprocessSumoRunner().run_online(
        scenario_cfg, ONLINE_SCRIPT, seed=1, out_dir=tmp_path / "r"
    )

    assert output.ok is False
    assert APPLIED_ACTIONS_FILE in (output.error or "")


def test_a_timeout_fails_the_run_and_leaves_no_process_behind(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    out_dir = tmp_path / "slow"

    output = SubprocessSumoRunner(timeout_s=1.0).run_online(
        scenario_cfg, ONLINE_SCRIPT, seed=1, out_dir=out_dir
    )

    assert output.ok is False
    assert "timed out" in (output.error or "")
    time.sleep(0.5)
    left = subprocess.run(["pgrep", "-f", str(out_dir)], capture_output=True, text=True)
    assert left.stdout.strip() == ""


def test_the_online_timeout_defaults_to_600_seconds() -> None:
    default = inspect.signature(SubprocessSumoRunner).parameters["timeout_s"].default
    assert default == 600.0


def _tls_script(program_id: str, at: float) -> TraciScript:
    return TraciScript(rules=(Rule(AtTime(at), SetTlsProgram("A2", program_id)),))


def test_a_dry_run_of_a_valid_script_passes_and_leaves_no_result(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    out_dir = tmp_path / "dry_run"

    outcome = SubprocessSumoRunner().dry_run(scenario_cfg, ONLINE_SCRIPT, out_dir)

    assert outcome == DryRunOutcome(ok=True, error=None)
    assert not (out_dir / APPLIED_ACTIONS_FILE).exists()


def test_a_dry_run_fails_with_sumos_message_for_an_unknown_tls_program(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    outcome = SubprocessSumoRunner().dry_run(
        scenario_cfg, _tls_script("no-such-program", BEGIN_S + 10), tmp_path / "dry_run"
    )

    assert outcome.ok is False
    assert "no-such-program" in (outcome.error or "")


def test_a_dry_run_catches_a_bad_id_in_a_rule_that_fires_after_the_fifty_steps(
    scenario_cfg: ArtifactRef, tmp_path: Path
) -> None:
    outcome = SubprocessSumoRunner().dry_run(
        scenario_cfg, _tls_script("no-such-program", END_S - 1), tmp_path / "dry_run"
    )

    assert outcome.ok is False
    assert "no-such-program" in (outcome.error or "")


def test_a_dry_run_times_out_as_a_failure(scenario_cfg: ArtifactRef, tmp_path: Path) -> None:
    outcome = SubprocessSumoRunner(timeout_s=0.01).dry_run(
        scenario_cfg, ONLINE_SCRIPT, tmp_path / "dry_run"
    )

    assert outcome.ok is False
    assert "timed out" in (outcome.error or "")
