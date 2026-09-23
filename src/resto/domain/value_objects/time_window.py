from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """Time of day in seconds since midnight, [start, end): 08:00–09:00 is [28800, 32400).
    Simulations run on the same clock (ADR-0028); past midnight the count continues."""

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
