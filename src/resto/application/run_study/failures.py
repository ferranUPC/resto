"""How the Executor classifies a failed step (ADR-0025 §3), in one place.

A step fails by raising `StepFailed`, which carries the `StepError` and what the step spent. The
table it implements:

- a promotion that raises (`promote`): a run cut by its own budget -> `budget`, any other run
  without a draft -> `agent`, a `DraftRejected` blaming the user -> `user_input` (a target
  the network lacks was named by the user), `NotImplementedError` -> `infrastructure`, any other
  `ValueError` (a rejected draft) -> `agent`, anything else -> `infrastructure`;
- an exception nothing classified -> `infrastructure` (`attempt`, which records the failure).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, NoReturn, TypeVar

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promotion import Blame, DraftRejected, RunWithoutDraft, require_draft
from resto.domain.entities.study import Study, Transition
from resto.domain.value_objects.outcomes import NeedsUser
from resto.domain.value_objects.step_record import (
    StepError,
    StepErrorKind,
    StepRecord,
    StepStatus,
    Usage,
)

T = TypeVar("T")


class StepFailed(Exception):
    """The step being run failed; carries its classification and what it spent."""

    def __init__(self, error: StepError, usage: Usage | None = None) -> None:
        super().__init__(error.message)
        self.error = error
        self.usage = usage or Usage()

    def record(self, tool: str, task: Mapping[str, Any]) -> StepRecord:
        """The failed step, as the study records it."""
        return StepRecord(tool, StepStatus.FAILED, task, error=self.error, usage=self.usage)


class StepNeedsUser(Exception):
    """The specialist running the step returned `NeedsUser`: not a failure, the user must act."""

    def __init__(self, needs_user: NeedsUser, usage: Usage | None = None) -> None:
        super().__init__(needs_user.message)
        self.needs_user = needs_user
        self.usage = usage or Usage()

    def record(self, tool: str, task: Mapping[str, Any]) -> StepRecord:
        """The step that needed the user, as the study records it."""
        return StepRecord(tool, StepStatus.NEEDS_USER, task, usage=self.usage)


def fail(kind: StepErrorKind, message: str, *details: str, usage: Usage | None = None) -> NoReturn:
    raise StepFailed(StepError(kind, message, tuple(details)), usage)


def draft_of(run: AgentRun[T], agent: str) -> T:
    """The draft of a finished run, for a step that reads it before any promotion."""
    return promote(lambda: require_draft(run, agent), run.usage)


def promote(call: Callable[[], T], usage: Usage) -> T:
    """Runs a promotion: a run cut by its budget is `budget`, any other run without a draft
    `agent`; a draft rejected on the user's account (a target the network lacks) is
    `user_input`, any other rejected draft the agent's (`agent`), anything else `infrastructure`."""
    try:
        return call()
    except StepFailed:
        raise
    except RunWithoutDraft as e:
        if e.stop_reason is StopReason.BUDGET:
            fail(StepErrorKind.BUDGET, f"{e.agent} ran out of its budget", usage=usage)
        fail(StepErrorKind.AGENT, str(e), usage=usage)
    except DraftRejected as e:
        kind = StepErrorKind.USER_INPUT if e.blame is Blame.USER else StepErrorKind.AGENT
        fail(kind, str(e), usage=usage)
    except NotImplementedError as e:
        fail(StepErrorKind.INFRASTRUCTURE, describe(e), usage=usage)
    except ValueError as e:
        fail(StepErrorKind.AGENT, str(e), usage=usage)
    except Exception as e:
        fail(StepErrorKind.INFRASTRUCTURE, describe(e), usage=usage)


def attempt(
    study: Study, kind: str, task: Mapping[str, Any], call: Callable[[], Transition]
) -> Transition:
    """Runs `call`, the `kind` step of `study` on `task`. The first failure stops the study
    (ADR-0025): the step failed (`failed`) or needing the user (`awaiting_user`), with the
    pending steps skipped; an exception nothing classified is `infrastructure`."""
    try:
        return call()
    except StepFailed as failed:
        return study.record_failure(failed.record(kind, task))
    except StepNeedsUser as needs:
        return study.record_needs_user(needs.record(kind, task), needs.needs_user)
    except Exception as e:
        error = StepError(StepErrorKind.INFRASTRUCTURE, describe(e))
        return study.record_failure(StepFailed(error).record(kind, task))


def describe(e: BaseException) -> str:
    if isinstance(e, StepFailed):
        return e.error.message
    return f"{type(e).__name__}: {e}"
