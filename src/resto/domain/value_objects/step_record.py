from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    simulations: int = 0


@dataclass(frozen=True, slots=True)
class StepRecord:
    """One tool call made by the Coordinator, with the typed task it sent (as data)."""

    tool: str
    status: StepStatus
    task: Mapping[str, Any] = field(default_factory=dict)
    produced_ids: tuple[str, ...] = ()
    error: str | None = None
    usage: Usage = field(default_factory=Usage)

    def __post_init__(self) -> None:
        if self.status is StepStatus.FAILED and not self.error:
            raise ValueError("a failed step must carry an error message")
