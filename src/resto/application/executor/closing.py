"""Closing a study: the Expert notes (ADR-0026: written once, after the final round; a failing note
writer never fails the study) and the report, which completes it."""

from __future__ import annotations

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, describe, draft_of, promote
from resto.application.executor.recorder import StudyRecorder
from resto.application.executor.spend import StudySpend
from resto.application.ports.repositories import NetworkRepository, ScenarioRepository
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.write_note import write_note
from resto.domain.entities.scenario import Scenario
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
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> None:
    """Asks the note writer about the final round and stores the notes' ids on the study; a
    failure is traced and leaves the study as it was."""
    try:
        study = recorder.study
        task = NoteTask(
            round=final,
            base_network_id=base_network_id(study, deps.networks),
            scenarios=allow_list(study, deps.scenarios),
        )
        run = spend.agent_call(lambda: deps.agents.note_writer.write(task))
        written = write_note(
            run,
            ledger,
            task,
            study_id=study.study_id,
            notes=deps.notes,
        )
    except Exception as e:
        recorder.note_writer_failed(describe(e))
        return
    recorder.set_note_ids(tuple(n.note_id for n in written))


def base_network_id(study: Study, networks: NetworkRepository) -> str:
    """The study's own network: the one of its networks that was not derived from another.
    `Study.network_ids` is in the order the study met its networks, so a derived network can come
    first: the position cannot say which one is the base."""
    for network_id in study.network_ids:
        network = networks.get(network_id)
        if network is not None and network.derived_from is None:
            return network_id
    raise ValueError("none of the study's networks is stored as a base network")


def _base_scenario(study: Study, scenarios: ScenarioRepository) -> Scenario | None:
    experiments = [e for p in study.phases for e in p.experiments]
    base = next((e for e in experiments if e.arm == BASE_ARM), None)
    return scenarios.get(base.scenario_id) if base is not None else None


def allow_list(study: Study, scenarios: ScenarioRepository) -> tuple[NoteScenario, ...]:
    """Every scenario of the study, plus the predicted id of each arm of the original question
    that was not realised and keeps the topology (ADR-0026)."""
    entries: dict[str, NoteScenario] = {}
    experiments = [e for p in study.phases for e in p.experiments]
    for e in experiments:
        scenario = scenarios.get(e.scenario_id)
        if scenario is None:
            raise ValueError(f"scenario {e.scenario_id!r} of the study is not stored")
        entries.setdefault(
            e.scenario_id,
            NoteScenario(
                e.scenario_id, e.arm, e.role, e.purpose, bool(e.result_ids), scenario.network_id
            ),
        )
    base_scenario = _base_scenario(study, scenarios)
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
                network_id=base_scenario.network_id,
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
