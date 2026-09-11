from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from resto.domain.value_objects.condition import Condition
from resto.domain.value_objects.intervention_target import InterventionTarget
from resto.domain.value_objects.time_window import TimeWindow


class InterventionType(StrEnum):
    LANE_CLOSURE = "lane_closure"
    EDGE_CLOSURE = "edge_closure"
    SPEED_LIMIT = "speed_limit"
    DEMAND_SCALE = "demand_scale"
    SIGNAL_PROGRAM = "signal_program"
    CUSTOM = "custom"


class Strategy(StrEnum):
    STATIC = "static"
    DYNAMIC = "dynamic"


@dataclass(frozen=True, slots=True)
class Intervention:
    """Something that happens *during* a simulation on an unchanged network.

    Permanent topology changes are not interventions: see TopologyModification.
    """

    type: InterventionType
    target: InterventionTarget | None
    params: Mapping[str, Any] = field(default_factory=dict)
    window: TimeWindow | None = None
    condition: Condition | None = None
    description: str | None = None
    expected_effect: str | None = None

    def __post_init__(self) -> None:
        if (self.window is None) == (self.condition is None):
            if self.type is InterventionType.EDGE_CLOSURE and self.window is None:
                raise ValueError(
                    "a permanent edge_closure is a TopologyModification (RemoveEdge), "
                    "not an intervention; give it a window or a condition"
                )
            raise ValueError("exactly one of window or condition must be set")
        if self.type is InterventionType.DEMAND_SCALE and self.target is not None:
            raise ValueError("demand_scale interventions are network-wide and take no target")
        if self.type not in (InterventionType.DEMAND_SCALE, InterventionType.CUSTOM) and (
            self.target is None
        ):
            raise ValueError(f"{self.type} interventions require a target")
        if self.type is InterventionType.CUSTOM and not self.description:
            raise ValueError("custom interventions require a description")

    @property
    def strategy(self) -> Strategy:
        return Strategy.STATIC if self.window is not None else Strategy.DYNAMIC
