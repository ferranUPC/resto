"""Closing a study (ADR-0042 §9): two stages, the Expert notes and then the report, which
completes it. Every study that reaches closing tries to write notes; a failing note writer is
telemetry and never fails the study (ADR-0026)."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.agents.composer import ComposerAgent
from resto.application.ports.agents.note_writer import NoteWriterAgent
from resto.application.ports.repositories import (
    NetworkRepository,
    NoteRepository,
    ScenarioRepository,
)
from resto.application.ports.tracing import NoteWriterFailed, Tracer
from resto.application.promoters.notes import NoteContext, NotePromoter
from resto.application.promoters.report import ReportPromoter
from resto.application.run_study.failures import StepFailed, crash, describe, draft_of, promote
from resto.application.run_study.spend import StudySpend
from resto.domain.entities.study import Study, Transition
from resto.domain.value_objects.step_record import StepRecord, StepStatus


@dataclass(frozen=True, slots=True)
class NotesStage:
    """The one stage that stores: notes are an aggregate of their own (ADR-0042 §3)."""

    note_writer: NoteWriterAgent
    promoter: NotePromoter
    networks: NetworkRepository
    scenarios: ScenarioRepository
    notes: NoteRepository
    tracer: Tracer

    def execute(self, study: Study, spend: StudySpend) -> Transition:
        """Asks the note writer about the final round, stores the notes the promoter returns and
        records their ids; a failure is traced (`NoteWriterFailed`) and leaves the study as it
        was. The promoter checks every draft before any note is stored."""
        final = study.current_phase.round
        assert final is not None  # a closing study ends on an Expert answer
        try:
            task = study.note_task(
                final,
                scenarios={
                    i: s for i in study.scenario_ids if (s := self.scenarios.get(i)) is not None
                },
                networks={
                    i: n for i in study.network_ids if (n := self.networks.get(i)) is not None
                },
            )
            run = spend.agent_call(lambda: self.note_writer.write(task))
            written = self.promoter.promote(run, NoteContext(task=task, study_id=study.study_id))
            for note in written:
                self.notes.store(note)
        except Exception as e:
            self.tracer.emit(study.study_id, NoteWriterFailed(describe(e)))
            return study, ()
        return study.record_notes(tuple(n.note_id for n in written))


@dataclass(frozen=True, slots=True)
class ComposeStage:
    composer: ComposerAgent
    promoter: ReportPromoter

    def execute(self, study: Study, spend: StudySpend) -> Transition:
        """Asks the Output Composer for the report and closes the study as `completed`, or
        records the failure."""
        task = {"study_id": study.study_id}
        try:
            run = spend.agent_call(lambda: self.composer.compose(study))
            draft_of(run, "composer")
            report = promote(lambda: self.promoter.promote(run, study), run.usage)
        except StepFailed as failed:
            return study.record_failure(failed.record("compose_report", task))
        except Exception as e:
            return study.record_failure(crash(e).record("compose_report", task))
        record = StepRecord("compose_report", StepStatus.OK, task, usage=run.usage)
        return study.complete(record, report)
