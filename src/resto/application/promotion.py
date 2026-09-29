"""How a promotion refuses an agent run (ADR-0001), the same for every agent.

A promotion (`build_scenario`, `ask_expert`, `write_note`) takes a finished `AgentRun` and either
returns the promoted entity or raises one of two errors:

- `RunWithoutDraft`: the run ended without a draft, so there is nothing to validate;
- `DraftRejected`: the draft exists but breaks a semantic rule. `blame` says whose fault it is,
  which is what the Executor reads to classify the failure (ADR-0025 §3): an id the user named
  that the network lacks is `Blame.USER`, everything else a wrong draft, `Blame.AGENT`.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from resto.application.ports.llm import AgentRun, StopReason

T = TypeVar("T")


class Blame(Enum):
    USER = "user"
    AGENT = "agent"


class RunWithoutDraft(RuntimeError):
    """The agent stopped (budget/error) without returning its draft."""


class DraftRejected(Exception):
    """The agent returned a well-formed draft that breaks a semantic rule.

    Not a `ValueError` on purpose: the Executor also maps a bare `ValueError` to `agent`, and a
    subclass would make `blame` depend on which `except` comes first."""

    def __init__(self, message: str, *, blame: Blame = Blame.AGENT) -> None:
        super().__init__(message)
        self.blame = blame


def require_draft(run: AgentRun[T], agent: str) -> T:
    if run.stop_reason is not StopReason.OUTPUT or run.output is None:
        raise RunWithoutDraft(f"{agent} stopped on {run.stop_reason} without a draft")
    return run.output
