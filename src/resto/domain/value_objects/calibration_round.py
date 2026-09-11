from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CalibrationRound:
    round: int
    max_relative_error: float
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.round < 1:
            raise ValueError("round numbering starts at 1")
