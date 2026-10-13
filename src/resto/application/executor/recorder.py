"""`StudyRecorder`: the only writer of the `Study`.

It builds no state: every change is a transition of the `Study` (ADR-0041 §4), which returns the
next study and the domain events it produced. The recorder stores the new study, then publishes its
events on the event bus under the study's id (ADR-0041 §10). It traces nothing itself: the trace is
a subscriber of the bus, and telemetry goes straight to the `Tracer` port (ADR-0041 §12).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from resto.application.event_bus import EventBus
from resto.application.ports.repositories import StudyRepository
from resto.application.schemas import adapter_for
from resto.domain.entities.study import Study, Transition


def data(value: Any) -> Mapping[str, Any]:
    """`value` as the JSON-ready mapping stored in a `StepRecord`."""
    dumped: Mapping[str, Any] = adapter_for(type(value)).dump_python(value, mode="json")
    return dumped


class StudyRecorder:
    def __init__(self, opened: Transition, *, studies: StudyRepository, events: EventBus) -> None:
        """Stores the study `Study.open` returned and publishes its events."""
        self._study, opening = opened
        self._studies = studies
        self._events = events
        self._studies.store(self._study)
        self._events.publish(self._study.study_id, opening)

    @property
    def study(self) -> Study:
        return self._study

    def apply(self, transition: Transition) -> None:
        """Stores the next study, unless the transition left it as it was, then publishes the
        transition's events."""
        study, events = transition
        if study is not self._study:
            self._study = study
            self._studies.store(study)
        self._events.publish(study.study_id, events)
