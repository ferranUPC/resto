"""The trace handler (ADR-0041 §12): every domain event but `SimulationsRecorded` is a trace event.

`SimulationsRecorded` is for note verification and is not traced. The composition root subscribes
`TraceHandler` to `TRACED_EVENTS`, first among the handlers (`resto.application.event_bus`).
"""

from __future__ import annotations

from typing import get_args

from resto.application.ports.tracing import Tracer
from resto.domain.events import (
    ExpertRoundHeld,
    NetworksAdded,
    NoteStatusChanged,
    NotesWritten,
    PhaseStarted,
    PlanMade,
    ReportComposed,
    StepTraced,
    StudyCreated,
)

TracedEvent = (
    StudyCreated
    | PhaseStarted
    | PlanMade
    | StepTraced
    | NetworksAdded
    | ExpertRoundHeld
    | NotesWritten
    | ReportComposed
    | NoteStatusChanged
)
TRACED_EVENTS: tuple[type[TracedEvent], ...] = get_args(TracedEvent)


class TraceHandler:
    name = "trace"

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer

    def __call__(self, study_id: str, event: TracedEvent) -> tuple[()]:
        """Emits `event` to the trace of the study `study_id`; produces no event."""
        self._tracer.emit(study_id, event)
        return ()
