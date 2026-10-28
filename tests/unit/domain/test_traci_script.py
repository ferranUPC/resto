"""`TraciScript` and its rules (ADR-0044): an invalid rule cannot be constructed."""

from __future__ import annotations

import math

import pytest

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


@pytest.mark.parametrize("t", [-1.0, math.inf, math.nan])
def test_at_time_rejects_a_negative_or_non_finite_time(t: float) -> None:
    with pytest.raises(ValueError):
        AtTime(t=t)


def test_at_time_accepts_zero() -> None:
    assert AtTime(t=0.0).t == 0.0


@pytest.mark.parametrize("make", [CloseLane, OpenLane])
def test_lane_actions_reject_an_empty_edge_or_a_negative_lane(make: type) -> None:
    with pytest.raises(ValueError):
        make(edge_id="", lane_index=0)
    with pytest.raises(ValueError):
        make(edge_id="E12", lane_index=-1)


def test_lane_actions_name_the_lane_like_a_lane_target() -> None:
    assert CloseLane(edge_id="E12", lane_index=1).lane_id == "E12_1"
    assert OpenLane(edge_id="E12", lane_index=0).lane_id == "E12_0"


@pytest.mark.parametrize("speed", [0.0, -3.0, math.inf, math.nan])
def test_set_speed_rejects_a_non_positive_or_non_finite_speed(speed: float) -> None:
    with pytest.raises(ValueError):
        SetSpeed(edge_id="E12", speed=speed)


def test_set_speed_rejects_an_empty_edge() -> None:
    with pytest.raises(ValueError):
        SetSpeed(edge_id="", speed=5.0)


def test_set_tls_program_rejects_an_empty_id() -> None:
    with pytest.raises(ValueError):
        SetTlsProgram(tls_id="", program_id="night")
    with pytest.raises(ValueError):
        SetTlsProgram(tls_id="J4", program_id=" ")


def test_a_script_needs_at_least_one_rule() -> None:
    with pytest.raises(ValueError):
        TraciScript(rules=())


def test_a_rule_pairs_a_trigger_with_an_action() -> None:
    condition = Condition(metric=Metric.SPEED, target="E12", op=Operator.LT, value=3.0)
    rule = Rule(trigger=When(condition), action=SetSpeed(edge_id="E12", speed=5.0))
    assert TraciScript(rules=(rule,)).rules == (rule,)
