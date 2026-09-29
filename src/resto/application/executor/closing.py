"""Closing a study: the Expert notes (ADR-0026: written once, after the final round; a failing note
writer never fails the study) and the report, which completes it."""

from __future__ import annotations

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, describe, draft_of, promote
from resto.application.executor.recorder import StudyRecorder
from resto.application.executor.spend import StudySpend
from resto.application.ports.repositories import ScenarioRepository
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.write_note import write_note
from resto.domain.entities.study import Study, StudyStatus
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.tasks import NoteScenario, NoteTask


def write_notes(
    final: ExpertRound,
    ledger: EvidenceLedger,
    network_id: str,
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> None:
    """Asks the note writer about the final round and stores the notes' ids on the study; a
    failure is traced and leaves the study as it was."""
    try:
        task = NoteTask(round=final, scenarios=allow_list(recorder.study, deps.scenarios))
        run = spend.agent_call(lambda: deps.agents.note_writer.write(task))
        written = write_note(
            run,
            ledger,
            task,
            network_id=network_id,
            study_id=recorder.study.study_id,
            notes=deps.notes,
        )
    except Exception as e:
        recorder.note_writer_failed(describe(e))
        return
    recorder.set_note_ids(tuple(n.note_id for n in written))


def allow_list(study: Study, scenarios: ScenarioRepository) -> tuple[NoteScenario, ...]:
    """Every scenario of the study, plus the predicted id of each arm of the original question
    that was not realised and keeps the topology (ADR-0026)."""
    entries: dict[str, NoteScenario] = {}
    experiments = [e for p in study.phases for e in p.experiments]
    for e in experiments:
        entries.setdefault(
            e.scenario_id,
            NoteScenario(e.scenario_id, e.arm, e.role, e.purpose, bool(e.result_ids)),
        )
    base = next((e for e in experiments if e.arm == BASE_ARM), None)
    base_scenario = scenarios.get(base.scenario_id) if base is not None else None
    if base_scenario is None:
        return tuple(entries.values())
    realised = {e.arm for e in experiments}
    question = study.question
    for arm in question.effective_arms:
        if arm.label in realised or arm.topology_changes:
            continue
        predicted = scenario_id_for(
            base_scenario.network_id,
            base_scenario.demand_id,
            arm.interventions,
            question.context_tags,
        )
        entries.setdefault(
            predicted,
            NoteScenario(
                predicted,
                arm.label,
                ExperimentRole.TREATMENT,
                f"arm {arm.label!r} as asked, not simulated in this study",
                simulated=False,
            ),
        )
    return tuple(entries.values())


def compose(recorder: StudyRecorder, spend: StudySpend, deps: StudyDeps) -> None:
    """Asks the Output Composer for the report and closes the study as `completed`, or records
    the failure."""
    study = recorder.study
    task = {"study_id": study.study_id}
    try:
        run = spend.agent_call(lambda: deps.agents.composer.compose(study))
        draft_of(run, "composer")
        report = promote(lambda: deps.promotions.report(study, run), run.usage)
    except StepFailed as failed:
        recorder.record_failure("compose_report", task, failed)
        return
    except Exception as e:
        recorder.record_failure("compose_report", task, crash(e))
        return
    record = StepRecord("compose_report", StepStatus.OK, task, usage=run.usage)
    recorder.record(record, status=StudyStatus.COMPLETED, report=report)
    recorder.report_composed()
