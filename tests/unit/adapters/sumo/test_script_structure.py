"""Script structure check (ADR-0044): what the dry run uses to confirm a generated file has the
shape the translator produces."""

from __future__ import annotations

import pytest

from resto.adapters.sumo.script_structure import check_script_structure
from resto.adapters.sumo.script_translator import translate_script
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.traci_script import (
    AtTime,
    CloseLane,
    OpenLane,
    Rule,
    TraciScript,
    When,
)


def test_structure_check_accepts_the_translator_output() -> None:
    script = TraciScript(
        rules=(
            Rule(AtTime(t=5), CloseLane(edge_id="E1", lane_index=0)),
            Rule(
                When(Condition(Metric.VEHICLE_COUNT, "E1", Operator.LT, 2)),
                OpenLane(edge_id="E1", lane_index=0),
            ),
        )
    )

    check_script_structure(translate_script(script), rule_count=2)


_GOOD = (
    "from resto.traci_api import at_time, close_lane, run\n"
    "\n"
    "at_time(1.0, lambda: close_lane('E1_0'))\n"
    "run()\n"
)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("at_time(1.0, lambda: close_lane('E1_0'", "does not parse"),
        (_GOOD.replace("resto.traci_api", "os"), "resto.traci_api"),
        ("import os\n" + _GOOD, "exactly one import"),
        (_GOOD.replace("run()\n", "at_time(2.0, lambda: close_lane('E1_0'))\nrun()\n"), "rule"),
        (_GOOD.replace("run()\n", ""), "run()"),
        (_GOOD + "close()\n", "close"),
        (_GOOD.replace("run()", "start([])\nrun()"), "start"),
        (_GOOD.replace("at_time(1.0, ", "close(), at_time(1.0, "), "close"),
        (_GOOD.replace("close_lane('E1_0')", "close()"), "close"),
    ],
)
def test_structure_check_rejects_text_that_breaks_a_rule(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        check_script_structure(text, rule_count=1)
