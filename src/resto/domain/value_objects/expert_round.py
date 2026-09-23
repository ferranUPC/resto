from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.expert_answer import ExpertAnswer


@dataclass(frozen=True, slots=True)
class ExpertRound:
    """One iteration of the Expert <-> Simulation loop inside a Study. `forced_by_limit` marks the
    last round of a free study, sent in forced mode because the rounds ran out (ADR-0025 §4)."""

    question: str
    answer: ExpertAnswer
    forced_by_limit: bool = False

    def __post_init__(self) -> None:
        if self.forced_by_limit and self.answer.needs_simulation:
            raise ValueError("a round forced by the limit must answer, not ask for a simulation")
