from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.value_objects.answer_value import AnswerValue
from resto.domain.value_objects.expert_answer import Basis


class Provenance(StrEnum):
    SIMULATION = "simulation"
    OPINION = "opinion"


class NoteStatus(StrEnum):
    UNVERIFIED = "unverified"
    CONFIRMED = "confirmed"
    REFUTED = "refuted"


@dataclass(frozen=True, slots=True)
class ExpertNote:
    """Prose written by the Expert after an experiment, retrieved by RAG later.
    `provenance` and `status` are set by code, never by the agent."""

    note_id: str
    network_id: str
    study_id: str
    text: str
    provenance: Provenance
    basis: Basis
    status: NoteStatus = NoteStatus.UNVERIFIED
    scenario_id: str | None = None
    context_tags: frozenset[str] = frozenset()
    values: tuple[AnswerValue, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("an ExpertNote requires text")
        if self.provenance is Provenance.SIMULATION and self.scenario_id is None:
            raise ValueError("simulation-backed notes must reference a scenario")

    def with_status(self, status: NoteStatus) -> ExpertNote:
        from dataclasses import replace

        return replace(self, status=status)
