from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.expert_answer import ExpertAnswer


@dataclass(frozen=True, slots=True)
class ExpertRound:
    """One iteration of the Expert <-> Simulation loop inside a Study."""

    question: str
    answer: ExpertAnswer
    triggered_experiments: tuple[int, ...] = ()  # indexes into Study.experiments
