"""Note verification (ADR-0026, ADR-0041 §11): an event bus handler of `SimulationsRecorded`.

Once the study recorded an ok `run_simulation` step, each new result of the step, in seed order,
settles the unverified notes about its scenario (`UpdateNoteStatus`). Reused results settle
nothing. The `NoteStatusChanged` events are published on the bus, which delivers them after the
step's own events (`resto.application.event_bus`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from resto.application.ports.repositories import (
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.application.use_cases.update_note_status import UpdateNoteStatus
from resto.domain.constants import NOTE_VERIFY_LIMIT
from resto.domain.events import DomainEvent, SimulationsRecorded
from resto.domain.value_objects.note_status import NoteStatus

Publish = Callable[[str, Iterable[DomainEvent]], None]


class VerifyNotes:
    def __init__(
        self,
        *,
        notes: NoteRepository,
        scenarios: ScenarioRepository,
        results: ResultRepository,
        update_note_status: UpdateNoteStatus,
        publish: Publish,
    ) -> None:
        self._notes = notes
        self._scenarios = scenarios
        self._results = results
        self._update_note_status = update_note_status
        self._publish = publish

    def __call__(self, study_id: str, event: DomainEvent) -> None:
        if not isinstance(event, SimulationsRecorded):
            return
        scenario = self._scenarios.get(event.scenario_id)
        if scenario is None:
            raise ValueError(f"scenario {event.scenario_id!r} is not stored")
        lookup = {"scenario_id": scenario.scenario_id, "status": [NoteStatus.UNVERIFIED.value]}
        for result_id in event.new_result_ids:
            result = self._results.get(result_id)
            if result is None:
                raise ValueError(f"result {result_id!r} is not stored")
            hits = self._notes.search("", scenario.network_id, lookup, limit=NOTE_VERIFY_LIMIT)
            for note, _ in hits:
                self._publish(study_id, self._update_note_status.execute(note, result))
