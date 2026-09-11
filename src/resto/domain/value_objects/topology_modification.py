from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RemoveEdge:
    edge_id: str
    kind: Literal["remove_edge"] = "remove_edge"


@dataclass(frozen=True, slots=True)
class AddEdge:
    from_junction: str
    to_junction: str
    lanes: int
    speed: float
    kind: Literal["add_edge"] = "add_edge"

    def __post_init__(self) -> None:
        if self.from_junction == self.to_junction:
            raise ValueError("an edge must join two different junctions")
        if self.lanes < 1:
            raise ValueError("lanes must be >= 1")
        if self.speed <= 0:
            raise ValueError("speed must be positive (m/s)")


@dataclass(frozen=True, slots=True)
class SetLanes:
    edge_id: str
    lanes: int
    kind: Literal["set_lanes"] = "set_lanes"

    def __post_init__(self) -> None:
        if self.lanes < 1:
            raise ValueError("lanes must be >= 1")


@dataclass(frozen=True, slots=True)
class SetSpeed:
    edge_id: str
    speed: float
    kind: Literal["set_speed"] = "set_speed"

    def __post_init__(self) -> None:
        if self.speed <= 0:
            raise ValueError("speed must be positive (m/s)")


TopologyModification = RemoveEdge | AddEdge | SetLanes | SetSpeed
"""One variant per plain-XML edit tool of the Network Author. `netconvert` options are not
modifications; they live in NetworkRecipe.netconvert_options."""
