"""Note verification (ADR-0026, ADR-0041 §11, ADR-0042 §11): the handler of `SimulationsRecorded`.

Once the study recorded an ok `run_simulation` step, each new result of the step, in seed order,
settles the unverified notes about its scenario. A later result confirms or refutes a note
deterministically and without an LLM (ADR-0011; DATABASE_MCP_CONTRACT.md: "only code decides
that"): the note decides (`ExpertNote.verify`), the handler stores it and yields its
`NoteStatusChanged` events. Reused results settle nothing. The bus delivers the events after the
step's own events (`resto.application.event_bus`).
"""

from __future__ import annotations

from collections.abc import Iterator

from resto.application.ports.repositories import (
    NoteRepository,
    ResultRepository,
    ScenarioRepository,
)
from resto.domain.constants import NOTE_VERIFY_LIMIT
from resto.domain.events import NoteStatusChanged, SimulationsRecorded
from resto.domain.value_objects.note_status import NoteStatus


class NoteVerificationHandler:
    name = "note_verification"

    def __init__(
        self,
        *,
        notes: NoteRepository,
        scenarios: ScenarioRepository,
        results: ResultRepository,
    ) -> None:
        self._notes = notes
        self._scenarios = scenarios
        self._results = results

    def __call__(self, study_id: str, event: SimulationsRecorded) -> Iterator[NoteStatusChanged]:
        """Yields the events of each note it settled, once that note is stored."""
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
                verified, events = note.verify(result)
                if events:
                    self._notes.update_status(verified.note_id, verified.status)
                yield from events
