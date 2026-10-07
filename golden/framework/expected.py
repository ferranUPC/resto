"""The Expected trace of a golden path: data only, never agent output."""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.step_record import StepStatus


@dataclass(frozen=True, slots=True)
class ExpectedStep:
    tool: str
    status: StepStatus = StepStatus.OK


@dataclass(frozen=True, slots=True)
class ExpectedPhase:
    """What one phase must leave. `steps` is always compared; an attribute left as `None` is not."""

    steps: tuple[ExpectedStep, ...]
    arms: tuple[str, ...] | None = None
    reused: tuple[bool, ...] | None = None
    basis: Basis | None = None
    forced_by_limit: bool | None = None
    round: int | None = None


@dataclass(frozen=True, slots=True)
class ExpectedTrace:
    """One entry per `PhaseStarted`, in order. An ambiguous request that stops before planning is
    still phase 0, with no steps."""

    phases: tuple[ExpectedPhase, ...]


@dataclass(frozen=True, slots=True)
class GoldenPath:
    """A request and the trace it must leave."""

    name: str
    request: str
    expected: ExpectedTrace
