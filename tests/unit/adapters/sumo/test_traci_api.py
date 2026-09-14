"""resto.traci_api (E1.2): primitives + at_time/when/run against a live TraCI session.

One SUMO connection per test (`session`, function-scoped) - `start()` costs ~1s to connect, but
`at_time`/`when`/`run` need a clean rule/log slate per test (only `start()` resets those), and a
single shared connection across tests of different scopes deadlocks TraCI ("Connection 'default'
is already active."), so isolation wins over the ~1s/test cost here.

Effects are verified by reading state back through raw `traci` (not through traci_api's own
getters) wherever a getter exists for what changed, per DoD §4.6's "verified by reading state
back through TraCI" - avoids tautological tests that only check traci_api against itself.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import traci

from resto import traci_api
from resto.domain.value_objects.applied_action import ActionOrigin

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"
LOW_ROUTES = DEV_NET.parent / "demand" / "low.rou.xml"

SUMO_CMD = [
    "sumo",
    "--net-file",
    str(DEV_NET),
    "--route-files",
    str(LOW_ROUTES),
    "--seed",
    "1",
    "--no-step-log",
    "--time-to-teleport",
    "300",
]


@pytest.fixture
def session() -> Iterator[None]:
    traci_api.start(SUMO_CMD)
    yield
    traci_api.close()


# --- close_lane / open_lane -----------------------------------------------------------------


def test_close_lane_disallows_every_vehicle_class(session: None) -> None:
    traci_api.close_lane("B0C0_1")

    assert traci.lane.getAllowed("B0C0_1") == ()
    assert len(traci.lane.getDisallowed("B0C0_1")) > 30  # every known vClass


def test_open_lane_restores_no_restriction_when_that_was_the_original_state(
    session: None,
) -> None:
    traci_api.close_lane("B0C0_1")

    traci_api.open_lane("B0C0_1")

    assert traci.lane.getAllowed("B0C0_1") == ()
    assert traci.lane.getDisallowed("B0C0_1") == ()


def test_open_lane_restores_a_bespoke_permission_set_instead_of_opening_wide(
    session: None,
) -> None:
    traci.lane.setAllowed("B0C0_1", ["bus"])  # e.g. a pre-existing bus-only lane

    traci_api.close_lane("B0C0_1")
    assert traci.lane.getAllowed("B0C0_1") == ()  # closed: nothing allowed

    traci_api.open_lane("B0C0_1")

    assert traci.lane.getAllowed("B0C0_1") == ("bus",)  # restored, not wide open


def test_close_lane_twice_does_not_overwrite_the_original_snapshot(session: None) -> None:
    traci.lane.setAllowed("B0C0_1", ["bus"])

    traci_api.close_lane("B0C0_1")
    traci_api.close_lane("B0C0_1")  # repeated close must not snapshot the now-closed state
    traci_api.open_lane("B0C0_1")

    assert traci.lane.getAllowed("B0C0_1") == ("bus",)


def test_close_lane_unknown_lane_raises_traci_exception(session: None) -> None:
    with pytest.raises(traci.TraCIException):
        traci_api.close_lane("NOPE_0")


# --- set_speed -------------------------------------------------------------------------------


def test_set_speed_changes_every_lane_of_the_edge(session: None) -> None:
    traci_api.set_speed("A0A1", 5.0)

    assert traci.lane.getMaxSpeed("A0A1_0") == pytest.approx(5.0)


def test_set_speed_unknown_edge_raises_traci_exception(session: None) -> None:
    with pytest.raises(traci.TraCIException):
        traci_api.set_speed("NOPE", 5.0)


# --- set_tls_program ---------------------------------------------------------------------------


def test_set_tls_program_switches_the_active_program(session: None) -> None:
    traci_api.set_tls_program("A2", "0")

    assert traci.trafficlight.getProgram("A2") == "0"


def test_set_tls_program_unknown_tls_raises_traci_exception(session: None) -> None:
    with pytest.raises(traci.TraCIException):
        traci_api.set_tls_program("NOPE", "0")


# --- read-only getters -------------------------------------------------------------------------


def test_get_edge_occupancy_speed_vehicle_count_return_plausible_values(session: None) -> None:
    occupancy = traci_api.get_edge_occupancy("A1B1")
    speed = traci_api.get_edge_speed("A1B1")
    count = traci_api.get_vehicle_count("A1B1")

    assert 0.0 <= occupancy <= 1.0
    assert speed >= 0.0
    assert count >= 0


def test_get_edge_occupancy_unknown_edge_raises_traci_exception(session: None) -> None:
    with pytest.raises(traci.TraCIException):
        traci_api.get_edge_occupancy("NOPE")


# --- step ------------------------------------------------------------------------------------


def test_step_advances_simulation_time_by_n(session: None) -> None:
    before = traci.simulation.getTime()

    traci_api.step(3)

    assert traci.simulation.getTime() == pytest.approx(before + 3)


def test_step_is_not_logged_to_applied_actions(session: None) -> None:
    before = len(traci_api.applied_actions())

    traci_api.step()

    assert len(traci_api.applied_actions()) == before


# --- applied_actions / origin ------------------------------------------------------------------


def test_direct_primitive_call_is_logged_with_code_origin(session: None) -> None:
    traci_api.set_speed("E0E1", 8.0)

    matching = [a for a in traci_api.applied_actions() if a.params.get("edge_id") == "E0E1"]
    [action] = matching
    assert action.action == "set_speed"
    assert action.origin is ActionOrigin.CODE
    assert action.params == {"edge_id": "E0E1", "speed": 8.0}


# --- at_time / when / run -----------------------------------------------------------------------


def test_at_time_fires_its_action_exactly_once(session: None) -> None:
    calls = []
    traci_api.at_time(5, lambda: calls.append(traci.simulation.getTime()))

    traci_api.run(until=10)

    assert calls == [5.0]


def test_at_time_fired_action_is_logged_with_rule_origin(session: None) -> None:
    traci_api.at_time(5, lambda: traci_api.close_lane("B0C0_1"))

    traci_api.run(until=10)

    [action] = traci_api.applied_actions()
    assert action.origin is ActionOrigin.RULE
    assert action.step == 5


def test_when_fires_only_on_the_rising_edge(session: None) -> None:
    calls = []
    traci_api.when(lambda: True, lambda: calls.append(1))  # true from step 1 onward

    traci_api.run(until=5)

    assert calls == [1]  # not once per step


def test_run_with_until_stops_exactly_at_that_time(session: None) -> None:
    traci_api.run(until=7)

    assert traci.simulation.getTime() == pytest.approx(7.0)


def test_run_without_until_drains_the_route_file(session: None) -> None:
    traci_api.run()

    assert traci.simulation.getMinExpectedNumber() == 0


def test_registered_rules_reports_named_functions_and_lambda_locations(
    session: None,
) -> None:
    def reopen() -> None:
        traci_api.open_lane("B0C0_1")

    traci_api.at_time(5, reopen)
    traci_api.when(lambda: True, lambda: None)

    rules = traci_api.registered_rules()

    assert rules[0].trigger == "at_time(5)"
    assert "def reopen" in rules[0].action
    assert rules[1].trigger.startswith("<lambda ")  # can't isolate two lambdas on one line
