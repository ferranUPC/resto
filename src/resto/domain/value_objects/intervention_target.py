from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class EdgeTarget:
    edge_id: str
    kind: Literal["edge"] = "edge"


@dataclass(frozen=True, slots=True)
class LaneTarget:
    edge_id: str
    lane_index: int
    kind: Literal["lane"] = "lane"

    def __post_init__(self) -> None:
        if self.lane_index < 0:
            raise ValueError("lane_index must be >= 0")

    @property
    def lane_id(self) -> str:
        return f"{self.edge_id}_{self.lane_index}"


@dataclass(frozen=True, slots=True)
class TlsTarget:
    tls_id: str
    kind: Literal["tls"] = "tls"


@dataclass(frozen=True, slots=True)
class TazTarget:
    taz_id: str
    kind: Literal["taz"] = "taz"


InterventionTarget = EdgeTarget | LaneTarget | TlsTarget | TazTarget
