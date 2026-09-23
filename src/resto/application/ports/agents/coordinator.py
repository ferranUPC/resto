from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.study_plan import CoordinatorOutput


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """What the Coordinator is told besides the question it plans. `network_id` is the network of
    the study once phase 0 fixed it (`None` while planning phase 0); `experiments` are those already
    realised in earlier phases, so a later phase reuses them instead of planning them again."""

    phase: int
    network_id: str | None = None
    experiments: tuple[Experiment, ...] = ()
    has_historical_demand: bool = False


class CoordinatorAgent(Protocol):
    """One run per phase, read-only DB tools: a `StudyPlan`, or a `ClarificationRequest` when the
    database reveals an ambiguity (ADR-0023, ADR-0025)."""

    def plan(self, question: Question, context: PlanningContext) -> AgentRun[CoordinatorOutput]: ...
