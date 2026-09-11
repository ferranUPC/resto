from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Metric(StrEnum):
    OCCUPANCY = "occupancy"
    SPEED = "speed"
    VEHICLE_COUNT = "vehicle_count"


class Operator(StrEnum):
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="


@dataclass(frozen=True, slots=True)
class Condition:
    """Runtime predicate `metric(target) op value` evaluated by the script's `when(...)`."""

    metric: Metric
    target: str
    op: Operator
    value: float

    def __post_init__(self) -> None:
        if not self.target:
            raise ValueError("a Condition requires a target id")
