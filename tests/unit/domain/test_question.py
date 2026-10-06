from __future__ import annotations

import pytest

from resto.domain.value_objects.arm import Arm
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import SetLanes

WINDOW = TimeWindow(28800, 32400)
CLOSURE = Intervention(InterventionType.EDGE_CLOSURE, EdgeTarget("C0D0"), window=WINDOW)


def test_network_only_defaults_to_false() -> None:
    assert Question(text="q", intent=Intent.DESCRIBE).network_only is False


def test_a_describe_with_nothing_about_traffic_can_be_network_only() -> None:
    q = Question(text="q", intent=Intent.DESCRIBE, network_ref="DEV-NET", network_only=True)
    assert q.network_only


@pytest.mark.parametrize(
    "intent", [Intent.DIAGNOSE, Intent.COMPARE, Intent.RUN]
)
def test_network_only_is_rejected_on_any_intent_but_describe(intent: Intent) -> None:
    with pytest.raises(ValueError, match="network_only"):
        Question(text="q", intent=intent, network_only=True)


@pytest.mark.parametrize(
    "extra",
    [
        {"demand_ref": "rush-hour traffic"},
        {"time_window": WINDOW},
        {"metrics_of_interest": ("mean_delay",)},
        {"interventions": (CLOSURE,)},
        {"topology_changes": (SetLanes("B0C0", 3),)},
        {"arms": (Arm("closure", interventions=(CLOSURE,)),)},
    ],
)
def test_network_only_is_rejected_when_the_question_is_about_traffic(
    extra: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="network_only"):
        Question(text="q", intent=Intent.DESCRIBE, network_only=True, **extra)  # type: ignore[arg-type]
