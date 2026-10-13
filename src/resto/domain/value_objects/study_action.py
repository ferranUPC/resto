"""What a study needs next (ADR-0041 §5): the closed union `Study.next_action` answers. The
application performs the action (agents, SUMO, the budget) and the study applies its outcome."""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.study_plan import StudyPlan


@dataclass(frozen=True, slots=True)
class PlanPhase:
    """Plan the current phase's question."""


@dataclass(frozen=True, slots=True)
class RunPlan:
    """Run the steps of the current phase's accepted `plan`."""

    plan: StudyPlan


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


StudyAction = PlanPhase | RunPlan | ConsultExpert | AskExpert | OpenPhase | Close | Finished
