"""The single agent port shared by the six agents (DoD §2.2)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar

from resto.domain.value_objects.step_record import Usage

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Tool:
    """A typed Python function offered to the LLM (in-process or via MCP)."""

    name: str
    description: str
    fn: Callable[..., Any]
    input_schema: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentTask:
    system_prompt: str
    input: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Budget:
    max_steps: int
    max_tokens: int
    max_seconds: float


class StopReason(StrEnum):
    OUTPUT = "output"
    BUDGET = "budget"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any]
    result_summary: str


@dataclass(frozen=True, slots=True)
class StepTrace:
    """One model call of a run: which tools it asked for (empty for a plain-text reply), how long
    its text was, and why it stopped (`"length"` = cut at the output-token limit)."""

    tool_calls: tuple[str, ...]
    text_chars: int
    finish_reason: str | None
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class AgentRun(Generic[T]):
    output: T | None
    tool_calls: tuple[ToolCall, ...]
    usage: Usage
    stop_reason: StopReason
    steps: tuple[StepTrace, ...] = ()


class ToolAgent(Protocol):
    def run(
        self, task: AgentTask, tools: Sequence[Tool], output: type[T], budget: Budget
    ) -> AgentRun[T]: ...
