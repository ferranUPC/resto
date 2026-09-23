from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepErrorKind(StrEnum):
    """What the user can do about a failure (ADR-0025 §3): rephrase, narrow or raise the budget,
    retry or change the approach, or nothing (logs given)."""

    USER_INPUT = "user_input"
    BUDGET = "budget"
    AGENT = "agent"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True, slots=True)
class StepError:
    """Why a step failed, classified by the Executor. `details` are the items the rendered study
    lists: the wrong edge, the rejected intervention and its reason, `unresolved[]`, a logs path."""

    kind: StepErrorKind
    message: str
    details: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("a StepError requires a message")


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    simulations: int = 0


@dataclass(frozen=True, slots=True)
class StepRecord:
    """One call made by the Executor (a plan step, planning, the Expert or the report), with the
    typed task it sent (as data)."""

    tool: str
    status: StepStatus
    task: Mapping[str, Any] = field(default_factory=dict)
    produced_ids: tuple[str, ...] = ()
    error: StepError | None = None
    usage: Usage = field(default_factory=Usage)

    def __post_init__(self) -> None:
        if (self.status is StepStatus.FAILED) != (self.error is not None):
            raise ValueError("a step carries a StepError if and only if it failed")
