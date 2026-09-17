from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Measure(StrEnum):
    """What a typed answer measures. The unit is fixed by the measure (`unit`), so an answer
    can never be stated in a different one."""

    # per edge (DATABASE_MCP_CONTRACT.md §5.4 names)
    TRAVEL_TIME = "travel_time"
    TIME_LOSS = "time_loss"
    WAITING_TIME = "waiting_time"
    OCCUPANCY = "occupancy"
    SPEED = "speed"
    DENSITY = "density"
    ENTERED = "entered"
    LEFT = "left"
    # network-wide (Kpis)
    MEAN_DELAY = "mean_delay"
    MEAN_TRAVEL_TIME = "mean_travel_time"
    TELEPORTS = "teleports"
    DEPARTED = "departed"
    ARRIVED = "arrived"

    @property
    def is_network_wide(self) -> bool:
        return self in _NETWORK_MEASURES

    @property
    def unit(self) -> str:
        return _UNITS[self]


_NETWORK_MEASURES = frozenset(
    {
        Measure.MEAN_DELAY,
        Measure.MEAN_TRAVEL_TIME,
        Measure.TELEPORTS,
        Measure.DEPARTED,
        Measure.ARRIVED,
    }
)
_UNITS = {
    Measure.TRAVEL_TIME: "s",
    Measure.TIME_LOSS: "s",
    Measure.WAITING_TIME: "s",
    Measure.OCCUPANCY: "%",
    Measure.SPEED: "m/s",
    Measure.DENSITY: "veh/km",
    Measure.ENTERED: "veh",
    Measure.LEFT: "veh",
    Measure.MEAN_DELAY: "s",
    Measure.MEAN_TRAVEL_TIME: "s",
    Measure.TELEPORTS: "veh",
    Measure.DEPARTED: "veh",
    Measure.ARRIVED: "veh",
}


def _check_scope(measure: Measure, edge_id: str | None) -> None:
    if measure.is_network_wide and edge_id is not None:
        raise ValueError(f"{measure} is network-wide: edge_id must be None")
    if not measure.is_network_wide and not edge_id:
        raise ValueError(f"{measure} is measured per edge: edge_id is required")


class ChangeDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class Edges:
    """A set of edges, or a ranking when `ranked` (most relevant first). Empty is a valid
    answer ("no edge does")."""

    edge_ids: tuple[str, ...]
    ranked: bool = False
    kind: Literal["edges"] = "edges"

    def __post_init__(self) -> None:
        if len(set(self.edge_ids)) != len(self.edge_ids):
            raise ValueError("edge_ids must not repeat")
        if any(not e for e in self.edge_ids):
            raise ValueError("edge ids must be non-empty")


@dataclass(frozen=True, slots=True)
class Quantity:
    """One measured value, in `measure.unit`, on one edge or (edge_id None) the whole network."""

    measure: Measure
    value: float
    edge_id: str | None = None
    kind: Literal["quantity"] = "quantity"

    def __post_init__(self) -> None:
        _check_scope(self.measure, self.edge_id)
        if not math.isfinite(self.value):
            raise ValueError("a quantity must be finite")


@dataclass(frozen=True, slots=True)
class Change:
    """How a measure changes relative to a reference (usually the baseline): a direction and,
    when known, the relative change in percent."""

    measure: Measure
    direction: ChangeDirection
    relative_change_pct: float | None = None
    edge_id: str | None = None
    kind: Literal["change"] = "change"

    def __post_init__(self) -> None:
        _check_scope(self.measure, self.edge_id)
        pct = self.relative_change_pct
        if pct is None:
            return
        if not math.isfinite(pct):
            raise ValueError("relative_change_pct must be finite")
        if (self.direction is ChangeDirection.INCREASE and pct < 0) or (
            self.direction is ChangeDirection.DECREASE and pct > 0
        ):
            raise ValueError("relative_change_pct contradicts the direction")


AnswerValue = Edges | Quantity | Change
