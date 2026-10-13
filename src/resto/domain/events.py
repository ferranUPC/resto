"""Domain events: what a transition of an aggregate produced (ADR-0041 §10).

A transition returns its next value and the events it produced; the use case stores the value, then
publishes the events. Event types import value objects only, never the entities that return them.
"""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.note_status import NoteStatus


@dataclass(frozen=True, slots=True)
class NoteStatusChanged:
    """`result_id` settled the note `note_id` as `status` (`ExpertNote.verify`)."""

    note_id: str
    result_id: str
    status: NoteStatus
