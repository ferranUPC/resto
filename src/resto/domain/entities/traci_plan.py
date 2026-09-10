from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TraciPlanEntry:
    trigger: str
    action: str
    action_params: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TraciPlan:
    entries: tuple[TraciPlanEntry, ...]
    poll_interval: float

    def __post_init__(self) -> None:
        if not self.entries:
            raise ValueError("a TraciPlan must have at least one entry")
        if self.poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
