"""What a `Study` has spent, checked against its `StudyBudget` before spending (ADR-0023 §5).

The Input Parser's call is the study's first: `StudySpend` starts with its tokens and one agent
call. Every later agent call goes through `agent_call`, every batch of new simulations through
`reserve_simulations`. Exhausting the budget fails the step about to run with `StepError(budget)`
and spends nothing more.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from resto.application.executor.deps import StudyBudget
from resto.application.executor.failures import describe, fail
from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.step_record import StepErrorKind, Usage

T = TypeVar("T")


class StudySpend:
    def __init__(self, budget: StudyBudget, parse_usage: Usage) -> None:
        self._budget = budget
        self._tokens = parse_usage.input_tokens + parse_usage.output_tokens
        self._agent_calls = 1
        self._simulations = 0

    def agent_call(self, call: Callable[[], AgentRun[T]]) -> AgentRun[T]:
        """Checks the budget for one more call, counts it, runs it and adds its tokens. A call
        that raises is the environment's fault (`infrastructure`)."""
        self._check(agent_calls=1)
        self._agent_calls += 1
        try:
            run = call()
        except Exception as e:
            fail(StepErrorKind.INFRASTRUCTURE, f"agent call failed: {describe(e)}")
        self._tokens += run.usage.input_tokens + run.usage.output_tokens
        return run

    def reserve_simulations(self, n: int) -> None:
        """Checks the budget for `n` new simulations; each is counted as it runs."""
        self._check(simulations=n)

    def count_simulation(self) -> None:
        self._simulations += 1

    def _check(self, *, agent_calls: int = 0, simulations: int = 0) -> None:
        budget = self._budget
        if agent_calls and self._agent_calls + agent_calls > budget.max_agent_calls:
            fail(
                StepErrorKind.BUDGET,
                "the study's agent-call budget is exhausted",
                f"{self._agent_calls} of {budget.max_agent_calls} agent calls used",
            )
        if agent_calls and self._tokens >= budget.max_tokens:
            fail(
                StepErrorKind.BUDGET,
                "the study's token budget is exhausted",
                f"{self._tokens} of {budget.max_tokens} tokens used",
            )
        if simulations and self._simulations + simulations > budget.max_simulations:
            fail(
                StepErrorKind.BUDGET,
                "the study's simulation budget is exhausted",
                f"{self._simulations} of {budget.max_simulations} simulations used, "
                f"{simulations} more needed",
            )
