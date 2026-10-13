"""`StudyRecorder`: the only writer of the `Study`.

It builds no state: every change is a transition of the `Study` (ADR-0041 §4), which returns the
next study and the domain events it produced. The recorder stores the new study, then passes its
events to the tracer under the study's id. The telemetry (`ModelCall`, `NoteWriterFailed`) and the
`NoteStatusChanged` of note verification are traced through it too.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from resto.application.ports.repositories import StudyRepository
from resto.application.ports.tracing import ModelCall, NoteWriterFailed, TraceEvent, Tracer
from resto.application.schemas import adapter_for
from resto.domain.entities.study import Study, Transition
from resto.domain.events import NoteStatusChanged, SimulationsRecorded, StudyEvent
from resto.domain.value_objects.step_record import Usage


def data(value: Any) -> Mapping[str, Any]:
    """`value` as the JSON-ready mapping stored in a `StepRecord`."""
    dumped: Mapping[str, Any] = adapter_for(type(value)).dump_python(value, mode="json")
    return dumped


class StudyRecorder:
    def __init__(self, opened: Transition, *, studies: StudyRepository, tracer: Tracer) -> None:
        """Stores the study `Study.open` returned and traces its events."""
        self._study, events = opened
        self._studies = studies
        self._tracer = tracer
        self._studies.store(self._study)
        self._publish(events)

    @property
    def study(self) -> Study:
        return self._study

    def apply(self, transition: Transition) -> None:
        """Stores the next study, unless the transition left it as it was, then traces the
        transition's events."""
        study, events = transition
        if study is not self._study:
            self._study = study
            self._studies.store(study)
        self._publish(events)

    def model_call(self, usage: Usage) -> None:
        """One agent call ended (ok or not): its tokens and cost."""
        self._emit(ModelCall(usage))

    def note_status_changed(self, event: NoteStatusChanged) -> None:
        """A note settled by a result of this study (`ExpertNote.verify`)."""
        self._emit(event)

    def note_writer_failed(self, error: str) -> None:
        self._emit(NoteWriterFailed(error))

    def _publish(self, events: tuple[StudyEvent, ...]) -> None:
        for event in events:
            if isinstance(event, SimulationsRecorded):
                continue  # for note verification, which still runs inside the step: not traced
            self._emit(event)

    def _emit(self, event: TraceEvent) -> None:
        self._tracer.emit(self._study.study_id, event)
