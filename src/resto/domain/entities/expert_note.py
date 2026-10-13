from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.events import NoteStatusChanged
from resto.domain.services.comparison import within_tolerance
from resto.domain.value_objects.answer_value import AnswerValue, Quantity
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.note_status import NoteStatus as NoteStatus


class Provenance(StrEnum):
    SIMULATION = "simulation"
    OPINION = "opinion"


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
        return replace(self, status=status)

    def verify(self, result: SimulationResult) -> tuple[ExpertNote, tuple[NoteStatusChanged, ...]]:
        """Confirms or refutes this note against `result`, deterministically and without an LLM
        (ADR-0011: the status changes only because of a later result, never because the agent
        revises its opinion).

        Returns the next note and the event of its status change, or this note and no event when
        `result` settles nothing: the note is already resolved, is about another scenario, `result`
        has no `Kpis`, or the note carries no claim this check can evaluate.

        Only network-wide `Quantity` claims (`mean_delay`, `mean_travel_time`, `teleports`,
        `departed`, `arrived`) are checked: a direct comparison with one result's `Kpis`, with no
        room for ambiguity. Per-edge `Quantity`, `Edges`, `Change` and `BottleneckCauses` claims
        have no target this simple a check can derive from one result alone (a `Change` claim needs
        its own baseline result), so a note carrying only those stays `UNVERIFIED` rather than
        getting a guessed verdict. See eval/README.md §4.8 and ADR-0024 for where this could be
        widened.
        """
        if self.status is not NoteStatus.UNVERIFIED or self.scenario_id != result.scenario_id:
            return self, ()
        if result.kpis is None:
            return self, ()
        kpis = result.kpis
        claims = [v for v in self.values if isinstance(v, Quantity) and v.measure.is_network_wide]
        if not claims:
            return self, ()
        agrees = all(
            within_tolerance(claim.value, getattr(kpis, claim.measure.value)) for claim in claims
        )
        status = NoteStatus.CONFIRMED if agrees else NoteStatus.REFUTED
        return replace(self, status=status), (
            NoteStatusChanged(self.note_id, result.result_id, status),
        )
