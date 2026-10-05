"""The ADR-0025 §3 failure table, row by row: how `promote` classifies what a promotion raises
and how `draft_of` classifies a run that ended without a draft."""

from collections.abc import Callable

import pytest

from resto.application.executor.failures import StepFailed, draft_of, fail, promote
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promotion import Blame, DraftRejected
from resto.domain.value_objects.step_record import StepError, StepErrorKind, Usage

USAGE = Usage(input_tokens=10, output_tokens=5)


def _raising(exc: BaseException) -> Callable[[], object]:
    def call() -> object:
        raise exc

    return call


def _promotion_failure(exc: BaseException) -> StepFailed:
    with pytest.raises(StepFailed) as caught:
        promote(_raising(exc), USAGE)
    return caught.value


def _run(stop_reason: StopReason, output: str | None = None) -> AgentRun[str]:
    return AgentRun(output=output, tool_calls=(), usage=USAGE, stop_reason=stop_reason)


def test_promote_returns_what_the_promotion_returns() -> None:
    assert promote(lambda: "network", USAGE) == "network"


def test_promote_lets_an_already_classified_failure_pass_unchanged() -> None:
    classified = StepFailed(StepError(StepErrorKind.BUDGET, "out of budget"), Usage(simulations=2))

    assert _promotion_failure(classified) is classified


def test_promote_classifies_a_draft_rejected_for_the_user_as_user_input() -> None:
    failure = _promotion_failure(DraftRejected("unknown edge 'e9'", blame=Blame.USER))

    assert failure.error == StepError(StepErrorKind.USER_INPUT, "unknown edge 'e9'")


def test_promote_classifies_a_draft_rejected_for_the_agent_as_agent() -> None:
    failure = _promotion_failure(DraftRejected("evidence ref 'q9' matches no tool call"))

    assert failure.error == StepError(StepErrorKind.AGENT, "evidence ref 'q9' matches no tool call")


def test_promote_classifies_not_implemented_as_infrastructure() -> None:
    failure = _promotion_failure(NotImplementedError("online scenarios"))

    assert failure.error == StepError(
        StepErrorKind.INFRASTRUCTURE, "NotImplementedError: online scenarios"
    )


def test_promote_classifies_value_error_as_agent() -> None:
    failure = _promotion_failure(ValueError("demand of another network"))

    assert failure.error == StepError(StepErrorKind.AGENT, "demand of another network")


def test_promote_classifies_anything_else_as_infrastructure() -> None:
    failure = _promotion_failure(OSError("disk full"))

    assert failure.error == StepError(StepErrorKind.INFRASTRUCTURE, "OSError: disk full")


def test_promote_attaches_the_usage_passed_in() -> None:
    assert _promotion_failure(ValueError("bad draft")).usage == USAGE


def test_draft_of_returns_the_draft_of_a_run_stopped_on_output() -> None:
    assert draft_of(_run(StopReason.OUTPUT, "plan"), "coordinator") == "plan"


def test_draft_of_classifies_a_run_stopped_by_its_budget_as_budget() -> None:
    with pytest.raises(StepFailed) as caught:
        draft_of(_run(StopReason.BUDGET), "coordinator")

    assert caught.value.error == StepError(
        StepErrorKind.BUDGET, "coordinator ran out of its budget"
    )
    assert caught.value.usage == USAGE


@pytest.mark.parametrize(
    ("stop_reason", "output"), [(StopReason.ERROR, None), (StopReason.OUTPUT, None)]
)
def test_draft_of_classifies_any_other_run_without_a_draft_as_agent(
    stop_reason: StopReason, output: str | None
) -> None:
    with pytest.raises(StepFailed) as caught:
        draft_of(_run(stop_reason, output), "expert")

    assert caught.value.error == StepError(
        StepErrorKind.AGENT, f"expert stopped on {stop_reason} without a draft"
    )
    assert caught.value.usage == USAGE


def test_fail_raises_the_classified_failure_with_its_details_and_usage() -> None:
    with pytest.raises(StepFailed) as caught:
        fail(StepErrorKind.AGENT, "the plan is invalid", "step 0: unknown network", usage=USAGE)

    assert caught.value.error == StepError(
        StepErrorKind.AGENT, "the plan is invalid", ("step 0: unknown network",)
    )
    assert caught.value.usage == USAGE
