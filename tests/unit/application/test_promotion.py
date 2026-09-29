"""The two ways a promotion refuses an agent run, shared by every module that promotes a draft."""

import pytest

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promotion import Blame, DraftRejected, RunWithoutDraft, require_draft
from resto.domain.value_objects.step_record import Usage


def _run(stop_reason: StopReason, output: str | None = None) -> AgentRun[str]:
    return AgentRun(output=output, tool_calls=(), usage=Usage(), stop_reason=stop_reason)


def test_require_draft_returns_the_draft_of_a_run_stopped_on_output() -> None:
    assert require_draft(_run(StopReason.OUTPUT, "draft"), "expert") == "draft"


@pytest.mark.parametrize(
    ("stop_reason", "output"),
    [(StopReason.BUDGET, None), (StopReason.ERROR, None), (StopReason.OUTPUT, None)],
)
def test_require_draft_refuses_a_run_without_a_draft(
    stop_reason: StopReason, output: str | None
) -> None:
    with pytest.raises(RunWithoutDraft, match=f"expert stopped on {stop_reason} without a draft"):
        require_draft(_run(stop_reason, output), "expert")


def test_a_rejected_draft_blames_the_agent_unless_told_otherwise() -> None:
    assert DraftRejected("bad draft").blame is Blame.AGENT


def test_a_rejected_draft_can_blame_the_user() -> None:
    assert DraftRejected("unknown edge 'e9'", blame=Blame.USER).blame is Blame.USER


def test_a_rejected_draft_is_a_value_error_carrying_its_message() -> None:
    error = DraftRejected("bad draft")

    assert isinstance(error, ValueError)
    assert str(error) == "bad draft"
