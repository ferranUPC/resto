from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.value_objects.time_window import TimeWindow


class DemandProfile(StrEnum):
    LOW = "low"
    PEAK = "peak"
    INCIDENT = "incident"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class DemandSpec:
    profile: DemandProfile
    window: TimeWindow
    seed: int
    scale: float = 1.0
    vehicles_per_hour: float | None = None
    sampler_options: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError("scale must be positive")
        if self.vehicles_per_hour is not None and self.vehicles_per_hour < 0:
            raise ValueError("vehicles_per_hour must be >= 0")
