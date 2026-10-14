"""Script translator (ADR-0044): exact text per trigger and action kind, and determinism."""

from __future__ import annotations

import pytest

from resto.adapters.sumo.script_structure import check_script_structure
from resto.adapters.sumo.script_translator import translate_script
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.traci_script import (
    Action,
    AtTime,
    CloseLane,
    OpenLane,
    Rule,
    SetSpeed,
    SetTlsProgram,
    TraciScript,
    Trigger,
    When,
)
from tests.unit.domain._fixtures import traci_script


def _one(trigger: Trigger, action: Action) -> TraciScript:
    return TraciScript(rules=(Rule(trigger=trigger, action=action),))


def test_at_time_rule_with_close_lane() -> None:
    text = translate_script(_one(AtTime(t=3600), CloseLane(edge_id="E12", lane_index=1)))

    assert text == (
        "from resto.traci_api import at_time, close_lane, run\n"
        "\n"
        "at_time(3600.0, lambda: close_lane('E12_1'))\n"
        "run()\n"
    )


def test_when_rule_with_open_lane() -> None:
    condition = Condition(metric=Metric.OCCUPANCY, target="E12", op=Operator.GT, value=0.8)

    text = translate_script(_one(When(condition), OpenLane(edge_id="E12", lane_index=0)))

    assert text == (
        "from resto.traci_api import get_edge_occupancy, open_lane, run, when\n"
        "\n"
        "when(lambda: get_edge_occupancy('E12') > 0.8, lambda: open_lane('E12_0'))\n"
        "run()\n"
    )


def test_set_speed_action() -> None:
    text = translate_script(_one(AtTime(t=10.5), SetSpeed(edge_id="C0D0", speed=5.0)))

    assert "at_time(10.5, lambda: set_speed('C0D0', 5.0))\n" in text


def test_set_tls_program_action() -> None:
    text = translate_script(_one(AtTime(t=0), SetTlsProgram(tls_id="J1", program_id="night")))

    assert "at_time(0.0, lambda: set_tls_program('J1', 'night'))\n" in text


@pytest.mark.parametrize(
    ("metric", "function"),
    [
        (Metric.OCCUPANCY, "get_edge_occupancy"),
        (Metric.SPEED, "get_edge_speed"),
        (Metric.VEHICLE_COUNT, "get_vehicle_count"),
    ],
)
def test_each_metric_reads_its_function(metric: Metric, function: str) -> None:
    condition = Condition(metric=metric, target="E1", op=Operator.GE, value=3)

    text = translate_script(_one(When(condition), CloseLane(edge_id="E1", lane_index=0)))

    assert f"when(lambda: {function}('E1') >= 3.0, " in text


@pytest.mark.parametrize("op", list(Operator))
def test_each_operator_is_written_as_is(op: Operator) -> None:
    condition = Condition(metric=Metric.SPEED, target="E1", op=op, value=2.0)

    text = translate_script(_one(When(condition), CloseLane(edge_id="E1", lane_index=0)))

    assert f"get_edge_speed('E1') {op.value} 2.0," in text


def test_rules_keep_their_order_and_the_import_names_only_what_is_used() -> None:
    script = TraciScript(
        rules=(
            Rule(AtTime(t=20), SetSpeed(edge_id="B", speed=3.0)),
            Rule(AtTime(t=10), SetSpeed(edge_id="A", speed=4.0)),
        )
    )

    text = translate_script(script)

    assert text == (
        "from resto.traci_api import at_time, run, set_speed\n"
        "\n"
        "at_time(20.0, lambda: set_speed('B', 3.0))\n"
        "at_time(10.0, lambda: set_speed('A', 4.0))\n"
        "run()\n"
    )


def test_ids_with_quotes_are_escaped() -> None:
    text = translate_script(_one(AtTime(t=1), SetTlsProgram(tls_id="a'b", program_id="p")))

    assert "set_tls_program(\"a'b\", 'p')" in text
    check_script_structure(text, rule_count=1)


def test_same_script_gives_identical_bytes() -> None:
    first = translate_script(traci_script()).encode()
    second = translate_script(traci_script()).encode()

    assert first == second


def test_an_action_variant_without_a_renderer_fails_loudly() -> None:
    rule = Rule(trigger=AtTime(t=1), action=object())  # type: ignore[arg-type]

    with pytest.raises(KeyError):
        translate_script(TraciScript(rules=(rule,)))
