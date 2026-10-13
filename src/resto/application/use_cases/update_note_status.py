"""A later `SimulationResult` confirms or refutes an `ExpertNote`, deterministically and without an
LLM (ADR-0011; DATABASE_MCP_CONTRACT.md: "only code decides that").

The note decides (`ExpertNote.verify`, ADR-0041 §9); this use case delegates, stores the settled
note and returns its events.
"""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.repositories import NoteRepository
from resto.domain.entities.expert_note import ExpertNote
from resto.domain.entities.simulation_result import SimulationResult
from resto.domain.events import NoteStatusChanged


@dataclass(frozen=True, slots=True)
class UpdateNoteStatus:
    notes: NoteRepository

    def execute(self, note: ExpertNote, result: SimulationResult) -> tuple[NoteStatusChanged, ...]:
        """Verifies `note` against `result` and stores it if its status changed.

        Returns the status-change events, empty when `result` settles nothing.
        """
        verified, events = note.verify(result)
        if events:
            self.notes.update_status(verified.note_id, verified.status)
        return events
