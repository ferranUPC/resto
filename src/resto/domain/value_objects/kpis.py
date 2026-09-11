from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Kpis:
    mean_delay: float
    mean_travel_time: float
    teleports: int
    departed: int
    arrived: int

    def __post_init__(self) -> None:
        if min(self.teleports, self.departed, self.arrived) < 0:
            raise ValueError("KPI counters must be >= 0")
        if self.arrived > self.departed:
            raise ValueError("arrived cannot exceed departed")
