from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ActionOrigin(StrEnum):
    RULE = "rule"
    CODE = "code"


@dataclass(frozen=True, slots=True)
class AppliedAction:
    step: int
    action: str
    origin: ActionOrigin
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.step < 0:
            raise ValueError("step must be >= 0")
