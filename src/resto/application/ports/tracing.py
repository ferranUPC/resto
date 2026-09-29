"""Append-only study trace (E0.7): the typed events a study emits and the port that stores them.

Only `StudyRecorder` calls `Tracer.emit`. The event set is a closed union, so an emitter that leaves
out a field fails `mypy`. The stored format is internal, not a public contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from resto.domain.entities.expert_note import NoteStatus
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.step_record import StepError, StepStatus, Usage


@dataclass(frozen=True, slots=True)
class StudyCreated:
    question: Question
    parse_usage: Usage


@dataclass(frozen=True, slots=True)
class StepTraced:
    phase: int
    tool: str
    status: StepStatus
    produced_ids: tuple[str, ...]
    usage: Usage
    error: StepError | None


@dataclass(frozen=True, slots=True)
class NetworksAdded:
    network_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NotesWritten:
    note_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NoteStatusChanged:
    note_id: str
    result_id: str
    status: NoteStatus


@dataclass(frozen=True, slots=True)
class ClarificationAsked:
    reason: str


@dataclass(frozen=True, slots=True)
class NoteWriterFailed:
    error: str


@dataclass(frozen=True, slots=True)
class ModelCall:
    """One agent call, its usage summed over the provider requests it made."""

    usage: Usage


TraceEvent = (
    StudyCreated
    | ModelCall
    | StepTraced
    | NetworksAdded
    | NotesWritten
    | NoteStatusChanged
    | ClarificationAsked
    | NoteWriterFailed
)


class Tracer(Protocol):
    def emit(self, study_id: str, event: TraceEvent) -> None: ...
