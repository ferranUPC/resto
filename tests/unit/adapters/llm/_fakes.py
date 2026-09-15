"""The shared `ToolAgent` fake (ADR-0001): every agent module (Network Author, Demand Generator,
Scenario Builder, Network Expert, Output Composer, Coordinator) is tested against this, never
against `adapters/llm/anthropic_client.py` — that keeps the real OpenRouter API entirely out of
`pytest` (CLAUDE.md "LLM provider & cost policy").

Most tests only need a canned result: build a `FakeToolAgent` with the `output` (and, if the
scenario needs it, `tool_calls`/`usage`/`stop_reason`) the test wants the "agent" to have
produced, and hand it to the use case under test. A test that also wants to check the use case
actually reacts to a tool being exercised can pass `interact`, which runs first and may call into
any of the offered `tools` the way a real agent's tool-calling loop would (e.g. to have a writer
tool put a real file on disk before the canned draft references it).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

from resto.application.ports.llm import AgentRun, AgentTask, Budget, StopReason, Tool
from resto.application.ports.llm import ToolCall as ToolCall
from resto.domain.value_objects.step_record import Usage

T = TypeVar("T")


@dataclass
class FakeToolAgent:
    """A canned `ToolAgent`: `run` ignores `task`/`output`/`budget` and returns the `AgentRun`
    the test scripted, after optionally running `interact(task, tools)` for its side effects.

    `output` is untyped on purpose: the port's `run` is generic *per call* (`output: type[T]`
    picks `T`), so a class-level `Generic[T]` would not satisfy the `ToolAgent` protocol."""

    output: Any
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = StopReason.OUTPUT
    interact: Callable[[AgentTask, Sequence[Tool]], None] | None = None

    def run(
        self, task: AgentTask, tools: Sequence[Tool], output: type[T], budget: Budget
    ) -> AgentRun[T]:
        if self.interact is not None:
            self.interact(task, tools)
        return AgentRun(
            output=self.output,
            tool_calls=self.tool_calls,
            usage=self.usage,
            stop_reason=self.stop_reason,
        )


def call_tool(tools: Sequence[Tool], name: str, /, **kwargs: Any) -> Any:
    """Looks `name` up in `tools` and calls it — the helper an `interact` callback uses to drive
    the same tools a real agent would have picked from `AgentTask`/`Tool.description`."""
    for tool in tools:
        if tool.name == name:
            return tool.fn(**kwargs)
    raise LookupError(f"no tool named {name!r} was offered")
