from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Measure(StrEnum):
    """What a typed answer measures. The unit is fixed by the measure (`unit`), so an answer
    can never be stated in a different one. `time_loss` and `waiting_time` are totals summed over
    every vehicle on the edge (vehicle-seconds), not per-vehicle means (ADR-0020)."""

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
    Measure.TIME_LOSS: "veh·s",
    Measure.WAITING_TIME: "veh·s",
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


def _check_scope(measure: Measure, edge_id: str | None, network_id: str | None) -> None:
    if measure.is_network_wide and edge_id is not None:
        raise ValueError(f"{measure} is network-wide: edge_id must be None")
    if not measure.is_network_wide and not edge_id:
        raise ValueError(f"{measure} is measured per edge: edge_id is required")
    _check_network(edge_id, network_id)


def _check_network(edge_id: str | None, network_id: str | None) -> None:
    """An edge id repeats across a network and its derivations (ADR-0032), so a value that names
    an edge always names its network, and a value that names none names no network."""
    if edge_id is not None and not network_id:
        raise ValueError("a value that names an edge must also name its network_id")
    if edge_id is None and network_id is not None:
        raise ValueError("a network-wide value names no network_id")


def _reference(edge_id: str | None, network_id: str | None) -> tuple[tuple[str, str], ...]:
    if edge_id is None or network_id is None:
        return ()
    return ((network_id, edge_id),)


class ChangeDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class Edges:
    """A set of edges, or a ranking when `ranked` (most relevant first). Empty is a valid
    answer ("no edge does")."""

    edge_ids: tuple[str, ...]
    network_id: str
    ranked: bool = False
    kind: Literal["edges"] = "edges"

    def __post_init__(self) -> None:
        if not self.network_id:
            raise ValueError("edges must name the network_id they are on")
        if len(set(self.edge_ids)) != len(self.edge_ids):
            raise ValueError("edge_ids must not repeat")
        if any(not e for e in self.edge_ids):
            raise ValueError("edge ids must be non-empty")

    @property
    def edge_references(self) -> tuple[tuple[str, str], ...]:
        """Every (network id, edge id) this value names."""
        return tuple((self.network_id, e) for e in self.edge_ids)


@dataclass(frozen=True, slots=True)
class Quantity:
    """One measured value, in `measure.unit`, on one edge or (edge_id None) the whole network."""

    measure: Measure
    value: float
    edge_id: str | None = None
    network_id: str | None = None
    kind: Literal["quantity"] = "quantity"

    def __post_init__(self) -> None:
        _check_scope(self.measure, self.edge_id, self.network_id)
        if not math.isfinite(self.value):
            raise ValueError("a quantity must be finite")

    @property
    def edge_references(self) -> tuple[tuple[str, str], ...]:
        """Every (network id, edge id) this value names; none when network-wide."""
        return _reference(self.edge_id, self.network_id)


@dataclass(frozen=True, slots=True)
class Change:
    """How a measure changes relative to a reference (usually the baseline): a direction and,
    when known, the relative change in percent."""

    measure: Measure
    direction: ChangeDirection
    relative_change_pct: float | None = None
    edge_id: str | None = None
    network_id: str | None = None
    kind: Literal["change"] = "change"

    def __post_init__(self) -> None:
        _check_scope(self.measure, self.edge_id, self.network_id)
        pct = self.relative_change_pct
        if pct is None:
            return
        if not math.isfinite(pct):
            raise ValueError("relative_change_pct must be finite")
        if (self.direction is ChangeDirection.INCREASE and pct < 0) or (
            self.direction is ChangeDirection.DECREASE and pct > 0
        ):
            raise ValueError("relative_change_pct contradicts the direction")

    @property
    def edge_references(self) -> tuple[tuple[str, str], ...]:
        """Every (network id, edge id) this value names; none when network-wide."""
        return _reference(self.edge_id, self.network_id)


class NoValueReason(StrEnum):
    NO_TRAFFIC = "no_traffic"


PER_VEHICLE_MEASURES = frozenset({Measure.TRAVEL_TIME, Measure.SPEED})


@dataclass(frozen=True, slots=True)
class NoValue:
    """The data shows the measure is undefined, e.g. the mean travel time of an edge no vehicle
    crossed. Not an abstention: the answer rests on evidence (ADR-0021). Only per-vehicle means can
    be undefined; a 0 % occupancy or a zero total delay is a real value."""

    measure: Measure
    edge_id: str
    network_id: str
    reason: NoValueReason = NoValueReason.NO_TRAFFIC
    kind: Literal["no_value"] = "no_value"

    def __post_init__(self) -> None:
        if self.measure not in PER_VEHICLE_MEASURES:
            raise ValueError(
                f"{self.measure} always has a value; only per-vehicle means can be undefined"
            )
        if not self.edge_id:
            raise ValueError("a NoValue names the edge it refers to")
        _check_network(self.edge_id, self.network_id)

    @property
    def edge_references(self) -> tuple[tuple[str, str], ...]:
        """Every (network id, edge id) this value names."""
        return ((self.network_id, self.edge_id),)


class BottleneckCause(StrEnum):
    """Why one edge of a diagnosed bottleneck is congested (ADR-0029). Declared in precedence
    order: when several apply, the first one is the edge's cause."""

    INTERVENTION = "intervention"
    MERGE = "merge"
    SPILLBACK = "spillback"
    SIGNAL = "signal"
    DEMAND = "demand"


@dataclass(frozen=True, slots=True)
class EdgeCause:
    edge_id: str
    network_id: str
    cause: BottleneckCause

    def __post_init__(self) -> None:
        if not self.edge_id:
            raise ValueError("an edge cause names a non-empty edge id")
        _check_network(self.edge_id, self.network_id)


@dataclass(frozen=True, slots=True)
class BottleneckCauses:
    """The diagnostic "why": one `BottleneckCause` per edge of a diagnosed bottleneck
    (ADR-0029), stated next to the `Edges` value that ranks them."""

    causes: tuple[EdgeCause, ...]
    kind: Literal["causes"] = "causes"

    def __post_init__(self) -> None:
        if not self.causes:
            raise ValueError("a cause value holds at least one edge")
        edges = [(c.network_id, c.edge_id) for c in self.causes]
        if len(set(edges)) != len(edges):
            raise ValueError("an edge must not repeat in a cause value")

    @property
    def edge_ids(self) -> tuple[str, ...]:
        return tuple(c.edge_id for c in self.causes)

    @property
    def edge_references(self) -> tuple[tuple[str, str], ...]:
        """Every (network id, edge id) this value names."""
        return tuple((c.network_id, c.edge_id) for c in self.causes)


AnswerValue = Edges | Quantity | Change | NoValue | BottleneckCauses
