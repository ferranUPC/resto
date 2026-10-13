"""What a `Study` has spent, checked against its `StudyBudget` before spending (ADR-0023 §5).

`StudySpend` starts at zero. Every agent call, the Input Parser's first, goes through `agent_call`,
every batch of new simulations through `reserve_simulations`. Exhausting the budget fails the step
about to run with `StepError(budget)` and spends nothing more.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from resto.application.ports.llm import AgentRun
from resto.application.ports.tracing import ModelCall, Tracer
from resto.application.run_study.failures import describe, fail
from resto.domain.constants import (
    DEFAULT_STUDY_MAX_AGENT_CALLS,
    DEFAULT_STUDY_MAX_SIMULATIONS,
    DEFAULT_STUDY_MAX_TOKENS,
)
from resto.domain.value_objects.step_record import StepErrorKind

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class StudyBudget:
    """What one `Study` may spend in total, on top of each agent call's own `Budget`
    (ADR-0023 §5). Exhausting it fails the step about to run with `StepError(budget)`."""

    max_tokens: int = DEFAULT_STUDY_MAX_TOKENS
    max_simulations: int = DEFAULT_STUDY_MAX_SIMULATIONS
    max_agent_calls: int = DEFAULT_STUDY_MAX_AGENT_CALLS


class StudySpend:
    def __init__(self, budget: StudyBudget, tracer: Tracer, study_id: str) -> None:
        """Every agent call's usage goes to `tracer` as a `ModelCall` of `study_id` (telemetry)."""
        self._tracer = tracer
        self._study_id = study_id
        self._budget = budget
        self._tokens = 0
        self._agent_calls = 0
        self._simulations = 0

    def agent_call(self, call: Callable[[], AgentRun[T]]) -> AgentRun[T]:
        """Checks the budget for one more call, counts it, runs it, adds its tokens and traces
        its usage (`ModelCall`). A call that raises is the environment's fault
        (`infrastructure`)."""
        self._check(agent_calls=1)
        self._agent_calls += 1
        try:
            run = call()
        except Exception as e:
            fail(StepErrorKind.INFRASTRUCTURE, f"agent call failed: {describe(e)}")
        self._tracer.emit(self._study_id, ModelCall(run.usage))
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
