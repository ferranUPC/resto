"""Append-only study trace (E0.7): the typed events a study emits and the port that stores them.

The tracer has two entries with one meaning each (ADR-0041 §12): the trace handler of the event
bus (`resto.application.event_handlers.trace.TraceHandler`) emits the domain events, and the
telemetry (`ModelCall`, `NoteWriterFailed`, `HandlerFailed`) is emitted straight to `Tracer.emit`
by whoever observed it. The event set is a closed union, so an emitter that leaves out a field
fails `mypy`. Domain events (`resto.domain.events`) join the union as they are, except
`SimulationsRecorded`, which is for note verification and not traced; the telemetry events are
defined here. The stored format is internal, not a public contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
from resto.domain.value_objects.step_record import Usage


@dataclass(frozen=True, slots=True)
class NoteWriterFailed:
    error: str


@dataclass(frozen=True, slots=True)
class HandlerFailed:
    """The event bus handler `handler` raised on an event of type `event`; the study went on."""

    handler: str
    event: str
    error: str


@dataclass(frozen=True, slots=True)
class ModelCall:
    """One agent call, its usage summed over the provider requests it made."""

    usage: Usage


TraceEvent = (
    StudyCreated
    | PhaseStarted
    | PlanMade
    | ExpertRoundHeld
    | ReportComposed
    | ModelCall
    | StepTraced
    | NetworksAdded
    | NotesWritten
    | NoteStatusChanged
    | NoteWriterFailed
    | HandlerFailed
)


class Tracer(Protocol):
    def emit(self, study_id: str, event: TraceEvent) -> None: ...
