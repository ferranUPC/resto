"""Script harness (ADR-0044) against real SUMO on DEV-NET: a translated script drives a session and
changes its state, and the actions that fired land in a file.

The 10 script cases call `OnlineHarness.run` in the test process. Each registers a read-back rule
through the `on_start` hook, before the script's own rules, that samples lane permissions, an
edge's max speed or a TLS program at every step. State is read back with raw `traci`, not through
`traci_api`, so a case never checks `traci_api` against itself (DoD §4.6). The applied action's step
is the step the action fired at, so the sample one step later must show its effect and the sample
before it must not.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import traci

from resto import traci_api
from resto.adapters.sumo.constants import APPLIED_ACTIONS_FILE
from resto.adapters.sumo.script_harness import (
    REQUEST,
    DryRunHarness,
    HarnessRequest,
    OnlineHarness,
    read_applied_actions,
)
from resto.adapters.sumo.script_translator import translate_script
from resto.application.schemas import adapter_for
from resto.domain.value_objects.applied_action import ActionOrigin, AppliedAction
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.traci_script import (
    AtTime,
    CloseLane,
    OpenLane,
    Rule,
    SetSpeed,
    SetTlsProgram,
    TraciScript,
    When,
)

DEV_NET_DIR = Path(__file__).resolve().parents[4] / "eval" / "dev-net"
NET = DEV_NET_DIR / "dev-net.net.xml"
LOW_ROUTES = DEV_NET_DIR / "demand" / "low.rou.xml"
BEGIN = 28800  # the low demand departs from 08:00
LANE = "B0C0_1"
EDGE = "C0D0"
TLS = "A2"
ALT_PROGRAM = "alt"
T = BEGIN + 60

# The first vehicles are on A0A1 within a minute of BEGIN, so this holds at some step after it.
BUSY = Condition(metric=Metric.VEHICLE_COUNT, target="A0A1", op=Operator.GE, value=1)
NEVER = Condition(metric=Metric.SPEED, target="A0A1", op=Operator.GT, value=1000)

Samples = dict[int, Any]


@pytest.fixture(scope="module")
def tls_additional(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A second program on A2, so switching to it is visible (the net only has "0")."""
    path = tmp_path_factory.mktemp("tls") / "alt.add.xml"
    path.write_text(
        '<additional><tlLogic id="A2" type="static" programID="alt" offset="0">'
        '<phase duration="30" state="GgrrGG"/><phase duration="3" state="yyrrGy"/>'
        '<phase duration="30" state="rrGGGr"/><phase duration="3" state="rryyGr"/>'
        "</tlLogic></additional>"
    )
    return path


@pytest.fixture
def sumo_cmd(tls_additional: Path) -> list[str]:
    return [
        "sumo", "--net-file", str(NET), "--route-files", str(LOW_ROUTES),
        "--additional-files", str(tls_additional), "--begin", str(BEGIN),
        "--seed", "1", "--no-step-log", "--time-to-teleport", "300",
    ]  # fmt: skip


def _run(
    sumo_cmd: list[str], out_dir: Path, *rules: Rule, read: Callable[[], Any]
) -> tuple[Samples, tuple[AppliedAction, ...]]:
    """Runs the rules with `read` sampled at every step; returns the samples by time."""
    script = out_dir / "script.py"
    script.write_text(translate_script(TraciScript(rules=rules)))
    samples: Samples = {}

    def record() -> bool:
        samples[int(traci.simulation.getTime())] = read()
        return False

    def setup() -> None:
        traci.trafficlight.setProgram(TLS, "0")  # the added program starts out active
        traci_api.when(record, lambda: None)

    OnlineHarness(sumo_cmd, on_start=setup).run(script, out_dir)
    return samples, read_applied_actions(out_dir)


def _disallowed() -> int:
    return len(traci.lane.getDisallowed(LANE))


def _max_speed() -> float:
    return float(traci.lane.getMaxSpeed(f"{EDGE}_0"))


def _program() -> str:
    return str(traci.trafficlight.getProgram(TLS))


def _only(actions: tuple[AppliedAction, ...], name: str) -> AppliedAction:
    (action,) = [a for a in actions if a.action == name]
    assert action.origin is ActionOrigin.RULE
    return action


def _first(actions: tuple[AppliedAction, ...], name: str) -> AppliedAction:
    """A `When` fires on every rising edge, so the first firing is the one checked."""
    action = next(a for a in actions if a.action == name)
    assert action.origin is ActionOrigin.RULE
    return action


def test_close_lane_at_time(sumo_cmd: list[str], tmp_path: Path) -> None:
    samples, actions = _run(
        sumo_cmd, tmp_path, Rule(AtTime(T), CloseLane("B0C0", 1)), read=_disallowed
    )

    applied = _only(actions, "close_lane")
    assert applied.step == T
    assert applied.params == {"lane_id": LANE}
    assert samples[T - 1] == 0
    assert samples[T + 1] > 30  # every vehicle class


def test_open_lane_at_time_restores_the_lane(sumo_cmd: list[str], tmp_path: Path) -> None:
    samples, actions = _run(
        sumo_cmd,
        tmp_path,
        Rule(AtTime(T), CloseLane("B0C0", 1)),
        Rule(AtTime(T + 30), OpenLane("B0C0", 1)),
        read=_disallowed,
    )

    applied = _only(actions, "open_lane")
    assert applied.step == T + 30
    assert samples[T + 29] > 30
    assert samples[T + 31] == 0


def test_set_speed_at_time(sumo_cmd: list[str], tmp_path: Path) -> None:
    samples, actions = _run(
        sumo_cmd, tmp_path, Rule(AtTime(T), SetSpeed(EDGE, 5.0)), read=_max_speed
    )

    applied = _only(actions, "set_speed")
    assert applied.step == T
    assert applied.params == {"edge_id": EDGE, "speed": 5.0}
    assert samples[T - 1] != pytest.approx(5.0)
    assert samples[T + 1] == pytest.approx(5.0)


def test_set_tls_program_at_time(sumo_cmd: list[str], tmp_path: Path) -> None:
    samples, actions = _run(
        sumo_cmd, tmp_path, Rule(AtTime(T), SetTlsProgram(TLS, ALT_PROGRAM)), read=_program
    )

    applied = _only(actions, "set_tls_program")
    assert applied.step == T
    assert applied.params == {"tls_id": TLS, "program_id": ALT_PROGRAM}
    assert samples[T - 1] == "0"
    assert samples[T + 1] == ALT_PROGRAM


def test_close_lane_when_condition_holds(sumo_cmd: list[str], tmp_path: Path) -> None:
    samples, actions = _run(
        sumo_cmd, tmp_path, Rule(When(BUSY), CloseLane("B0C0", 1)), read=_disallowed
    )

    applied = _first(actions, "close_lane")
    assert applied.step > BEGIN
    assert samples[applied.step - 1] == 0
    assert samples[applied.step + 1] > 30


def test_set_speed_when_condition_holds(sumo_cmd: list[str], tmp_path: Path) -> None:
    samples, actions = _run(
        sumo_cmd, tmp_path, Rule(When(BUSY), SetSpeed(EDGE, 4.0)), read=_max_speed
    )

    applied = _first(actions, "set_speed")
    assert applied.step > BEGIN
    assert samples[applied.step - 1] != pytest.approx(4.0)
    assert samples[applied.step + 1] == pytest.approx(4.0)


def test_set_tls_program_when_condition_holds(sumo_cmd: list[str], tmp_path: Path) -> None:
    samples, actions = _run(
        sumo_cmd, tmp_path, Rule(When(BUSY), SetTlsProgram(TLS, ALT_PROGRAM)), read=_program
    )

    applied = _first(actions, "set_tls_program")
    assert applied.step > BEGIN
    assert samples[applied.step - 1] == "0"
    assert samples[applied.step + 1] == ALT_PROGRAM


def test_open_lane_when_condition_holds_after_a_timed_close(
    sumo_cmd: list[str], tmp_path: Path
) -> None:
    samples, actions = _run(
        sumo_cmd,
        tmp_path,
        Rule(AtTime(BEGIN + 1), CloseLane("B0C0", 1)),
        Rule(When(BUSY), OpenLane("B0C0", 1)),
        read=_disallowed,
    )

    applied = _first(actions, "open_lane")
    assert applied.step > BEGIN + 1
    assert samples[applied.step - 1] > 30
    assert samples[applied.step + 1] == 0


def test_rules_fire_in_rule_order_within_a_step(sumo_cmd: list[str], tmp_path: Path) -> None:
    _, actions = _run(
        sumo_cmd,
        tmp_path,
        Rule(AtTime(T), SetSpeed(EDGE, 5.0)),
        Rule(AtTime(T), CloseLane("B0C0", 1)),
        read=_disallowed,
    )

    assert [(a.action, a.step, a.origin) for a in actions] == [
        ("set_speed", T, ActionOrigin.RULE),
        ("close_lane", T, ActionOrigin.RULE),
    ]


def test_rules_whose_trigger_never_holds_leave_no_applied_action(
    sumo_cmd: list[str], tmp_path: Path
) -> None:
    samples, actions = _run(
        sumo_cmd,
        tmp_path,
        Rule(When(NEVER), CloseLane("B0C0", 1)),
        Rule(AtTime(10 * BEGIN), SetSpeed(EDGE, 5.0)),
        read=_disallowed,
    )

    assert actions == ()
    assert set(samples.values()) == {0}


def test_applied_actions_file_round_trips_through_the_boundary_schemas(
    sumo_cmd: list[str], tmp_path: Path
) -> None:
    _run(sumo_cmd, tmp_path, Rule(AtTime(T), SetSpeed(EDGE, 5.0)), read=_max_speed)

    adapter = adapter_for(tuple[AppliedAction, ...])
    actions = adapter.validate_json((tmp_path / APPLIED_ACTIONS_FILE).read_bytes())

    assert actions == (
        AppliedAction(T, "set_speed", ActionOrigin.RULE, {"edge_id": EDGE, "speed": 5.0}),
    )
    assert adapter.validate_json(adapter.dump_json(actions)) == actions


def _entry_point(request: HarnessRequest) -> subprocess.CompletedProcess[str]:
    """The harness as the launcher starts it: a request as JSON on stdin."""
    return subprocess.run(
        [sys.executable, "-m", "resto.adapters.sumo.script_harness"],
        input=REQUEST.dump_json(request).decode(),
        capture_output=True,
        text=True,
    )


def test_the_entry_point_exits_non_zero_with_the_traceback_when_the_script_raises(
    sumo_cmd: list[str], tmp_path: Path
) -> None:
    script = tmp_path / "script.py"
    script.write_text(
        "from resto.traci_api import run, set_tls_program\n\n"
        "set_tls_program('A2', 'no-such-program')\n"
        "run()\n"
    )

    proc = _entry_point(HarnessRequest(tuple(sumo_cmd), script, tmp_path))

    assert proc.returncode != 0
    assert "Traceback" in proc.stderr
    assert "no-such-program" in proc.stderr
    assert not (tmp_path / APPLIED_ACTIONS_FILE).exists()


def _dry_run(sumo_cmd: list[str], out_dir: Path, *rules: Rule, read: Callable[[], Any]) -> Samples:
    script = out_dir / "script.py"
    script.write_text(translate_script(TraciScript(rules=rules)))
    samples: Samples = {}

    def record() -> bool:
        samples[int(traci.simulation.getTime())] = read()
        return False

    def setup() -> None:
        traci.trafficlight.setProgram(TLS, "0")
        traci_api.when(record, lambda: None)

    DryRunHarness(sumo_cmd, on_start=setup).run(script, out_dir)
    return samples


def test_a_dry_run_steps_fifty_times_forces_every_rule_and_writes_nothing(
    sumo_cmd: list[str], tmp_path: Path
) -> None:
    samples = _dry_run(
        sumo_cmd,
        tmp_path,
        Rule(AtTime(10 * BEGIN), SetSpeed(EDGE, 5.0)),
        Rule(When(NEVER), CloseLane("B0C0", 1)),
        read=_max_speed,
    )

    assert max(samples) == BEGIN + 50
    assert not (tmp_path / APPLIED_ACTIONS_FILE).exists()


def test_a_dry_run_applies_a_rule_that_would_fire_late_so_a_bad_id_in_it_raises(
    sumo_cmd: list[str], tmp_path: Path
) -> None:
    script = tmp_path / "script.py"
    script.write_text(
        translate_script(
            TraciScript(rules=(Rule(AtTime(10 * BEGIN), SetTlsProgram(TLS, "no-such-program")),))
        )
    )

    with pytest.raises(traci.TraCIException, match="no-such-program"):
        DryRunHarness(sumo_cmd).run(script, tmp_path)


def test_the_entry_point_dry_run_request_exits_zero_and_writes_nothing(
    sumo_cmd: list[str], tmp_path: Path
) -> None:
    script = tmp_path / "script.py"
    script.write_text(translate_script(TraciScript(rules=(Rule(AtTime(T), SetSpeed(EDGE, 5.0)),))))

    proc = _entry_point(HarnessRequest(tuple(sumo_cmd), script, tmp_path, dry_run=True))

    assert proc.returncode == 0, proc.stderr
    assert not (tmp_path / APPLIED_ACTIONS_FILE).exists()
