from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """Simulation-time interval in seconds, [start, end)."""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("start must be >= 0")
        if self.end <= self.start:
            raise ValueError("end must be greater than start")

    @property
    def duration(self) -> float:
        return self.end - self.start
