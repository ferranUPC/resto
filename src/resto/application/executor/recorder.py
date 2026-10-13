"""`StudyRecorder`: the only writer of the `Study`.

Every change builds the next state with `dataclasses.replace` (so the domain invariants check it),
stores it and traces it, in one call. Nothing else in the Executor builds or stores a `Study`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from resto.application.executor.failures import StepFailed, StepNeedsUser
from resto.application.ports.repositories import StudyRepository
from resto.application.ports.tracing import (
    ExpertRoundHeld,
    ModelCall,
    NetworksAdded,
    NotesWritten,
    NoteWriterFailed,
    PhaseStarted,
    PlanMade,
    ReportComposed,
    StepTraced,
    StudyCreated,
    TraceEvent,
    Tracer,
)
from resto.application.schemas import adapter_for
from resto.domain.entities.study import Phase, Study, StudyResolution, StudyStage
from resto.domain.events import NoteStatusChanged
from resto.domain.services.ids import new_id
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepRecord, StepStatus, Usage
from resto.domain.value_objects.study_plan import PlanStep, StudyPlan


def data(value: Any) -> Mapping[str, Any]:
    """`value` as the JSON-ready mapping stored in a `StepRecord`."""
    dumped: Mapping[str, Any] = adapter_for(type(value)).dump_python(value, mode="json")
    return dumped


class StudyRecorder:
    def __init__(
        self,
        question: Question,
        parse_usage: Usage,
        *,
        max_rounds: int,
        studies: StudyRepository,
        tracer: Tracer,
    ) -> None:
        """Opens the `Study` on phase 0 at `planning` (`awaiting_user` at `parsing` if the
        question is ambiguous), stores it and traces it as `StudyCreated`, then `PhaseStarted`
        for phase 0."""
        if question.is_ambiguous:
            stage, resolution = StudyStage.PARSING, StudyResolution.AWAITING_USER
        else:
            stage, resolution = StudyStage.PLANNING, None
        self._study = Study(
            new_id(), stage, (Phase(question),), resolution=resolution, max_rounds=max_rounds
        )
        self._studies = studies
        self._tracer = tracer
        self._studies.store(self._study)
        self._emit(StudyCreated(question, parse_usage))
        self._emit(PhaseStarted(0))
        self.model_call(parse_usage)

    # -- reading ------------------------------------------------------------------------------

    @property
    def study(self) -> Study:
        return self._study

    @property
    def phase(self) -> Phase:
        return self._study.phases[-1]

    @property
    def phase_index(self) -> int:
        return len(self._study.phases) - 1

    def result_ids(self) -> tuple[str, ...]:
        """The result ids of every experiment of the study, in order, without repeats."""
        ids = (r for p in self._study.phases for e in p.experiments for r in e.result_ids)
        return tuple(dict.fromkeys(ids))

    # -- writing ------------------------------------------------------------------------------

    def record(
        self,
        record: StepRecord,
        *,
        experiments: tuple[Experiment, ...] | None = None,
        round_: ExpertRound | None = None,
        resolution: StudyResolution | None = None,
        report: Report | None = None,
    ) -> None:
        """Appends a step to the current phase, with what it changed. An Expert round whose
        answer needs no simulation moves the study to `closing`, in the same state."""
        phase = self.phase
        phase = replace(
            phase,
            steps=(*phase.steps, record),
            experiments=phase.experiments if experiments is None else experiments,
            round=phase.round if round_ is None else round_,
        )
        self._trace_step(record)
        answered = round_ is not None and not round_.answer.needs_simulation
        stage = StudyStage.CLOSING if answered else None
        self._set_phase(phase, stage=stage, resolution=resolution, report=report)

    def record_failure(
        self,
        tool: str,
        task: Mapping[str, Any],
        failure: StepFailed,
        *,
        phase: Phase | None = None,
        pending: Sequence[PlanStep] = (),
    ) -> None:
        """The failed step, the plan steps left unrun and the `failed` resolution, in one state;
        the study keeps the stage it failed in."""
        phase = phase or self.phase
        record = StepRecord(tool, StepStatus.FAILED, task, error=failure.error, usage=failure.usage)
        skipped = tuple(StepRecord(s.kind, StepStatus.SKIPPED) for s in pending)
        self._trace_step(record)
        self._set_phase(
            replace(phase, steps=(*phase.steps, record, *skipped)),
            resolution=StudyResolution.FAILED,
        )

    def record_needs_user(
        self,
        tool: str,
        task: Mapping[str, Any],
        needs: StepNeedsUser,
        *,
        pending: Sequence[PlanStep] = (),
    ) -> None:
        """The step that needed the user, the plan steps left unrun and the `awaiting_user`
        resolution, in one state."""
        record = StepRecord(tool, StepStatus.NEEDS_USER, task, usage=needs.usage)
        skipped = tuple(StepRecord(s.kind, StepStatus.SKIPPED) for s in pending)
        self._trace_step(record)
        phase = replace(
            self.phase, steps=(*self.phase.steps, record, *skipped), needs_user=needs.needs_user
        )
        self._set_phase(phase, resolution=StudyResolution.AWAITING_USER)

    def open_phase(self, question: Question) -> None:
        """Starts the next phase, on the experiment the Expert proposed, at `planning`."""
        self._set(phases=(*self._study.phases, Phase(question)), stage=StudyStage.PLANNING)
        self._emit(PhaseStarted(self.phase_index))

    def plan_made(self, plan: StudyPlan, record: StepRecord) -> None:
        """Stores the valid plan and its `plan` step in the current phase, at `running`."""
        phase = replace(self.phase, plan=plan, steps=(record,))
        self._set_phase(phase, stage=StudyStage.RUNNING)
        self._emit(PlanMade(self.phase_index, plan))

    def consulting_expert(self) -> None:
        """Every step of the current plan ran: the study is about to ask the Expert."""
        self._set(stage=StudyStage.CONSULTING_EXPERT)

    def add_networks(self, *network_ids: str) -> None:
        """Adds the networks the study has not used yet; stores and traces only if one is new."""
        merged = tuple(dict.fromkeys((*self._study.network_ids, *network_ids)))
        if merged == self._study.network_ids:
            return
        added = merged[len(self._study.network_ids) :]
        self._set(network_ids=merged)
        self._emit(NetworksAdded(added))

    def set_note_ids(self, note_ids: tuple[str, ...]) -> None:
        self._set(note_ids=note_ids)
        self._emit(NotesWritten(note_ids))

    def model_call(self, usage: Usage) -> None:
        """One agent call ended (ok or not): its tokens and cost."""
        self._emit(ModelCall(usage))

    def expert_round_held(self, round_no: int) -> None:
        """The Expert round of the current phase was recorded; `round_no` counts from 1."""
        self._emit(ExpertRoundHeld(self.phase_index, round_no))

    def report_composed(self) -> None:
        self._emit(ReportComposed())

    def note_status_changed(self, event: NoteStatusChanged) -> None:
        """A note settled by a result of this study (`ExpertNote.verify`)."""
        self._emit(event)

    def note_writer_failed(self, error: str) -> None:
        self._emit(NoteWriterFailed(error))

    # -- internals ----------------------------------------------------------------------------

    def _set_phase(
        self,
        phase: Phase,
        *,
        stage: StudyStage | None = None,
        resolution: StudyResolution | None = None,
        report: Report | None = None,
    ) -> None:
        self._set(
            phases=(*self._study.phases[:-1], phase),
            stage=stage or self._study.stage,
            resolution=resolution or self._study.resolution,
            report=report if report is not None else self._study.report,
        )

    def _set(self, **changes: Any) -> None:
        self._study = replace(self._study, **changes)
        self._studies.store(self._study)

    def _emit(self, event: TraceEvent) -> None:
        self._tracer.emit(self._study.study_id, event)

    def _trace_step(self, record: StepRecord) -> None:
        self._emit(
            StepTraced(
                phase=self.phase_index,
                tool=record.tool,
                status=record.status,
                produced_ids=record.produced_ids,
                usage=record.usage,
                error=record.error,
            )
        )
