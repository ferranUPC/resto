from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EdgeTarget:
    edge_id: str


@dataclass(frozen=True, slots=True)
class LaneTarget:
    edge_id: str
    lane_index: int


@dataclass(frozen=True, slots=True)
class TlsTarget:
    tls_id: str


@dataclass(frozen=True, slots=True)
class TazTarget:
    taz_id: str


InterventionTarget = EdgeTarget | LaneTarget | TlsTarget | TazTarget
