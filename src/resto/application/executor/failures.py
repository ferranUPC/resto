"""How the Executor classifies a failed step (ADR-0025 §3), in one place.

A step fails by raising `StepFailed`, which carries the `StepError` and what the step spent. The
table it implements:

- a run cut by its own budget -> `budget`; any other run without a draft -> `agent` (`draft_of`);
- a promotion that raises (`promote`): a `DraftRejected` blaming the user -> `user_input` (a target
  the network lacks was named by the user), `NotImplementedError` -> `infrastructure`, any other
  `ValueError` (a rejected draft) -> `agent`, anything else -> `infrastructure`;
- an exception nothing classified -> `infrastructure` (`crash`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn, TypeVar

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promotion import Blame, DraftRejected, RunWithoutDraft, require_draft
from resto.domain.value_objects.step_record import StepError, StepErrorKind, Usage

T = TypeVar("T")


class StepFailed(Exception):
    """The step being run failed; carries its classification and what it spent."""

    def __init__(self, error: StepError, usage: Usage | None = None) -> None:
        super().__init__(error.message)
        self.error = error
        self.usage = usage or Usage()


def fail(kind: StepErrorKind, message: str, *details: str, usage: Usage | None = None) -> NoReturn:
    raise StepFailed(StepError(kind, message, tuple(details)), usage)


def draft_of(run: AgentRun[T], agent: str) -> T:
    """The draft of a finished run, classified before any promotion sees it: a run cut by its
    budget is `budget`, any other run without a draft is `agent`."""
    try:
        return require_draft(run, agent)
    except RunWithoutDraft as e:
        if e.stop_reason is StopReason.BUDGET:
            fail(StepErrorKind.BUDGET, f"{agent} ran out of its budget", usage=run.usage)
        fail(StepErrorKind.AGENT, str(e), usage=run.usage)


def promote(call: Callable[[], T], usage: Usage) -> T:
    """Runs a promotion: a draft rejected on the user's account (a target the network lacks) is
    `user_input`, any other rejected draft the agent's (`agent`), anything else `infrastructure`."""
    try:
        return call()
    except StepFailed:
        raise
    except DraftRejected as e:
        kind = StepErrorKind.USER_INPUT if e.blame is Blame.USER else StepErrorKind.AGENT
        fail(kind, str(e), usage=usage)
    except NotImplementedError as e:
        fail(StepErrorKind.INFRASTRUCTURE, describe(e), usage=usage)
    except ValueError as e:
        fail(StepErrorKind.AGENT, str(e), usage=usage)
    except Exception as e:
        fail(StepErrorKind.INFRASTRUCTURE, describe(e), usage=usage)


def crash(e: BaseException) -> StepFailed:
    """An exception nothing classified: the environment's fault (logs in the trace)."""
    return StepFailed(StepError(StepErrorKind.INFRASTRUCTURE, describe(e)))


def describe(e: BaseException) -> str:
    if isinstance(e, StepFailed):
        return e.error.message
    return f"{type(e).__name__}: {e}"
