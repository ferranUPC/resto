"""One Expert round (ADR-0025 §4): ask the Network Expert about the study's results so far, with
the last round forced when the study is free and `max_rounds` is reached."""

from __future__ import annotations

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, draft_of, promote
from resto.application.executor.recorder import StudyRecorder, data
from resto.application.executor.spend import StudySpend
from resto.application.ports.llm import AgentRun
from resto.application.promoters.expert_answer import ExpertAnswerContext
from resto.application.tools.expert import EvidenceLedger
from resto.domain.services.experiment_design import mode_for
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.tasks import ExpertTask


def ask_expert_round(
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> None:
    """Asks the Expert and records its round in the current phase, or the failure that leaves the
    study `failed`."""
    study = recorder.study
    question = study.question
    # the scope as it stands now: a network derived in an earlier phase is in it (ADR-0032)
    task = ExpertTask(
        question=question.text,
        mode=mode_for(question, study.next_round_no, study.max_rounds),
        network_ids=study.network_ids,
        result_ids=study.result_ids,
    )
    ledger = EvidenceLedger()
    try:
        run = spend.agent_call(lambda: deps.agents.expert.answer(task, ledger))
        draft_of(run, "expert")
        round_ = promote(lambda: _promote_answer(run, task, ledger, deps), run.usage)
    except StepFailed as failed:
        recorder.apply(study.record_failure(failed.record("ask_expert", data(task))))
        return
    except Exception as e:
        recorder.apply(study.record_failure(crash(e).record("ask_expert", data(task))))
        return
    record = StepRecord("ask_expert", StepStatus.OK, data(task), usage=run.usage)
    recorder.apply(study.record_expert_round(record, round_))


def _promote_answer(
    run: AgentRun[ExpertAnswer], task: ExpertTask, ledger: EvidenceLedger, deps: StudyDeps
) -> ExpertRound:
    """Loads every network of the task's scope, then promotes the answer against them. A network
    that is not stored fails here even when no value names an edge."""
    networks = {
        network_id: deps.network_queries.load(network_id) for network_id in task.network_ids
    }
    context = ExpertAnswerContext(task=task, ledger=ledger, networks=networks)
    return deps.expert_answer_promoter.promote(run, context)
