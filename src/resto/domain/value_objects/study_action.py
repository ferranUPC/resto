"""What a study needs next (ADR-0041 §5): the closed union `Study.next_action` answers. The
application performs the action (agents, SUMO, the budget) and the study applies its outcome."""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.study_plan import PlanStep


@dataclass(frozen=True, slots=True)
class ParseRequest:
    """Turn the request's `text` into a `Question` with the Input Parser."""

    text: str


@dataclass(frozen=True, slots=True)
class PlanPhase:
    """Plan the current phase's question."""


@dataclass(frozen=True, slots=True)
class RunStep:
    """Run the next `step` of the current phase's plan. The study resolved its `FromStep`
    references: `step` names the ids the earlier steps produced."""

    step: PlanStep


@dataclass(frozen=True, slots=True)
class ConsultExpert:
    """Every step of the plan is recorded: move the study to consult the Expert."""


@dataclass(frozen=True, slots=True)
class AskExpert:
    """Ask the Expert about the study's results so far."""


@dataclass(frozen=True, slots=True)
class OpenPhase:
    """The Expert asked for a simulation: open the phase of the experiment it proposed."""


@dataclass(frozen=True, slots=True)
class Close:
    """The Expert answered without a simulation: write the notes about `final`, then compose the
    report."""

    final: ExpertRound


@dataclass(frozen=True, slots=True)
class Finished:
    """The study has a resolution: nothing more to do."""


StudyAction = (
    ParseRequest | PlanPhase | RunStep | ConsultExpert | AskExpert | OpenPhase | Close | Finished
)
