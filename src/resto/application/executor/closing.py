"""Closing a study: the Expert notes (ADR-0026: written once, after the final round; a failing note
writer never fails the study) and the report, which completes it."""

from __future__ import annotations

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, describe, draft_of, promote
from resto.application.executor.recorder import StudyRecorder
from resto.application.executor.spend import StudySpend
from resto.application.ports.agents.note_writer import NoteWriterAgent
from resto.application.ports.repositories import NetworkRepository, ScenarioRepository
from resto.application.ports.tracing import NoteWriterFailed, Tracer
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.write_note import WriteNote
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.step_record import StepRecord, StepStatus


def close(
    final: ExpertRound,
    ledger: EvidenceLedger,
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> None:
    """Closes the study after the Expert's `final` answer: the notes first, then the report."""
    write_notes(
        final,
        ledger,
        recorder,
        spend,
        deps.networks,
        deps.scenarios,
        deps.agents.note_writer,
        deps.write_note,
        deps.tracer,
    )
    compose(recorder, spend, deps)


def write_notes(
    final: ExpertRound,
    ledger: EvidenceLedger,
    recorder: StudyRecorder,
    spend: StudySpend,
    networks: NetworkRepository,
    scenarios: ScenarioRepository,
    note_writer: NoteWriterAgent,
    write_note: WriteNote,
    tracer: Tracer,
) -> None:
    """Asks the note writer about the final round and stores the notes' ids on the study; a
    failure is traced (`NoteWriterFailed`, telemetry) and leaves the study as it was."""
    try:
        study = recorder.study
        task = study.note_task(
            final,
            scenarios={i: s for i in study.scenario_ids if (s := scenarios.get(i)) is not None},
            networks={i: n for i in study.network_ids if (n := networks.get(i)) is not None},
        )
        run = spend.agent_call(lambda: note_writer.write(task))
        written = write_note.execute(run, ledger, task, study.study_id)
    except Exception as e:
        tracer.emit(recorder.study.study_id, NoteWriterFailed(describe(e)))
        return
    recorder.apply(recorder.study.record_notes(tuple(n.note_id for n in written)))


def compose(recorder: StudyRecorder, spend: StudySpend, deps: StudyDeps) -> None:
    """Asks the Output Composer for the report and closes the study as `completed`, or records
    the failure."""
    study = recorder.study
    task = {"study_id": study.study_id}
    try:
        run = spend.agent_call(lambda: deps.agents.composer.compose(study))
        draft_of(run, "composer")
        report = promote(lambda: deps.compose_report.execute(study, run), run.usage)
    except StepFailed as failed:
        recorder.apply(study.record_failure(failed.record("compose_report", task)))
        return
    except Exception as e:
        recorder.apply(study.record_failure(crash(e).record("compose_report", task)))
        return
    record = StepRecord("compose_report", StepStatus.OK, task, usage=run.usage)
    recorder.apply(study.complete(record, report))
