"""How the Executor classifies a failed step (ADR-0025 §3), in one place.

A step fails by raising `StepFailed`, which carries the `StepError` and what the step spent. The
table it implements:

- a run cut by its own budget -> `budget`; any other run without a draft -> `agent` (`draft_of`);
- a promotion that raises (`promote`): `UnknownTargetError` -> `user_input` (a target the network
  lacks was named by the user), `NotImplementedError` -> `infrastructure`, any other `ValueError`
  (a rejected draft) -> `agent`, anything else -> `infrastructure`;
- an exception nothing classified -> `infrastructure` (`crash`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NoReturn, TypeVar

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.use_cases.build_scenario import UnknownTargetError
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
    if run.stop_reason is StopReason.OUTPUT and run.output is not None:
        return run.output
    if run.stop_reason is StopReason.BUDGET:
        fail(StepErrorKind.BUDGET, f"{agent} ran out of its budget", usage=run.usage)
    fail(
        StepErrorKind.AGENT,
        f"{agent} stopped on {run.stop_reason} without a draft",
        usage=run.usage,
    )


def promote(call: Callable[[], T], usage: Usage) -> T:
    """Runs a promotion: a target the network lacks is the user's (`user_input`), any other
    rejected draft the agent's (`agent`), anything else `infrastructure`."""
    try:
        return call()
    except StepFailed:
        raise
    except UnknownTargetError as e:  # a ScenarioSemanticError, so a ValueError: checked first
        fail(StepErrorKind.USER_INPUT, str(e), usage=usage)
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
