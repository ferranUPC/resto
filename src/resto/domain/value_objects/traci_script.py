"""A scenario's script as typed data (ADR-0044): a list of rules, each pairing one trigger with one
action. Code writes the Python from these; a script that imports anything is not expressible."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from resto.domain.value_objects.condition import Condition


@dataclass(frozen=True, slots=True)
class AtTime:
    """Fires once, when the simulation time reaches `t` seconds."""

    t: float
    kind: Literal["at_time"] = "at_time"

    def __post_init__(self) -> None:
        if not math.isfinite(self.t) or self.t < 0:
            raise ValueError("t must be a finite time >= 0")


@dataclass(frozen=True, slots=True)
class When:
    """Fires each time `condition` goes from false to true."""

    condition: Condition
    kind: Literal["when"] = "when"


Trigger = AtTime | When


def _require_id(value: str, what: str) -> None:
    if not value.strip():
        raise ValueError(f"{what} must not be empty")


def _require_lane(edge_id: str, lane_index: int) -> None:
    _require_id(edge_id, "edge_id")
    if lane_index < 0:
        raise ValueError("lane_index must be >= 0")


@dataclass(frozen=True, slots=True)
class CloseLane:
    edge_id: str
    lane_index: int
    kind: Literal["close_lane"] = "close_lane"

    def __post_init__(self) -> None:
        _require_lane(self.edge_id, self.lane_index)

    @property
    def lane_id(self) -> str:
        return f"{self.edge_id}_{self.lane_index}"


@dataclass(frozen=True, slots=True)
class OpenLane:
    edge_id: str
    lane_index: int
    kind: Literal["open_lane"] = "open_lane"

    def __post_init__(self) -> None:
        _require_lane(self.edge_id, self.lane_index)

    @property
    def lane_id(self) -> str:
        return f"{self.edge_id}_{self.lane_index}"


@dataclass(frozen=True, slots=True)
class SetSpeed:
    """Sets the maximum speed of an edge, in m/s. Not the network-level `SetSpeed` of
    `topology_modification`, which edits the network file."""

    edge_id: str
    speed: float
    kind: Literal["set_speed"] = "set_speed"

    def __post_init__(self) -> None:
        _require_id(self.edge_id, "edge_id")
        if not math.isfinite(self.speed) or self.speed <= 0:
            raise ValueError("speed must be a finite value > 0 (m/s)")


@dataclass(frozen=True, slots=True)
class SetTlsProgram:
    tls_id: str
    program_id: str
    kind: Literal["set_tls_program"] = "set_tls_program"

    def __post_init__(self) -> None:
        _require_id(self.tls_id, "tls_id")
        _require_id(self.program_id, "program_id")


Action = CloseLane | OpenLane | SetSpeed | SetTlsProgram


@dataclass(frozen=True, slots=True)
class Rule:
    trigger: Trigger
    action: Action


@dataclass(frozen=True, slots=True)
class TraciScript:
    rules: tuple[Rule, ...]

    def __post_init__(self) -> None:
        if not self.rules:
            raise ValueError("a TraciScript needs at least one rule")
