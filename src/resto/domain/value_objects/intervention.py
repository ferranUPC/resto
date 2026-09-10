from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from resto.domain.value_objects.intervention_target import InterventionTarget


class InterventionType(StrEnum):
    LANE_CLOSURE = "lane_closure"
    EDGE_CLOSURE = "edge_closure"
    SPEED_LIMIT = "speed_limit"
    DEMAND_SCALE = "demand_scale"
    SIGNAL_PROGRAM = "signal_program"


class Strategy(StrEnum):
    STATIC = "static"
    DYNAMIC = "dynamic"


@dataclass(frozen=True, slots=True)
class Intervention:
    type: InterventionType
    target: InterventionTarget | None
    params: Mapping[str, Any] = field(default_factory=dict)
    window: tuple[float, float] | None = None
    condition: str | None = None

    def __post_init__(self) -> None:
        if (self.window is None) == (self.condition is None):
            raise ValueError("exactly one of window or condition must be set")
        if self.type is InterventionType.DEMAND_SCALE and self.target is not None:
            raise ValueError("demand_scale interventions are network-wide and take no target")
        if self.type is not InterventionType.DEMAND_SCALE and self.target is None:
            raise ValueError(f"{self.type} interventions require a target")

    @property
    def strategy(self) -> Strategy:
        return Strategy.STATIC if self.window is not None else Strategy.DYNAMIC
