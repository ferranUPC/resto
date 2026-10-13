"""`write_notes` needs only the repositories, the note writer and `WriteNote`, not the whole
`StudyDeps`; a failure is traced and leaves the study as it was (ADR-0026)."""

from __future__ import annotations

from resto.adapters.persistence.memory import (
    InMemoryNetworkRepository,
    InMemoryNoteRepository,
    InMemoryScenarioRepository,
)
from resto.application.event_bus import EventBus
from resto.application.executor.closing import write_notes
from resto.application.executor.deps import StudyBudget
from resto.application.executor.recorder import StudyRecorder
from resto.application.executor.spend import StudySpend
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.write_note import WriteNote
from resto.domain.entities.study import Study
from resto.domain.value_objects.expert_round import ExpertRound
from tests.unit.application._world import (
    DESCRIBE,
    FakeNoteWriter,
    RecordingStudies,
    RecordingTracer,
)
from tests.unit.domain._samples import expert_answer


def test_a_study_without_a_stored_base_network_traces_the_failure_and_changes_nothing() -> None:
    tracer = RecordingTracer()
    recorder = StudyRecorder(
        Study.open("s1", DESCRIBE.text, max_rounds=3),
        studies=RecordingStudies(),
        events=EventBus(tracer),
    )
    spend = StudySpend(StudyBudget(), lambda usage: None)
    note_writer = FakeNoteWriter()
    notes = InMemoryNoteRepository()
    before = recorder.study

    write_notes(
        ExpertRound(question="q", answer=expert_answer()),
        EvidenceLedger(),
        recorder,
        spend,
        InMemoryNetworkRepository(),
        InMemoryScenarioRepository(),
        note_writer,
        WriteNote(notes),
        tracer,
    )

    assert note_writer.calls == []
    assert recorder.study == before
    assert any(type(e).__name__ == "NoteWriterFailed" for e in tracer.events)
