"""One Expert round (ADR-0025 §4): ask the Network Expert about the study's results so far, with
the last round forced when the study is free and `max_rounds` is reached."""

from __future__ import annotations

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, draft_of, promote
from resto.application.executor.recorder import StudyRecorder, data
from resto.application.executor.spend import StudySpend
from resto.application.tools.expert import EvidenceLedger
from resto.domain.services.experiment_design import mode_for
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.tasks import ExpertTask


def ask_expert_round(
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
) -> EvidenceLedger:
    """Asks the Expert and records its round in the current phase, or the failure that leaves the
    study `failed`. Returns the evidence ledger the Expert filled."""
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
        round_ = promote(lambda: deps.ask_expert.execute(task, run, ledger), run.usage)
    except StepFailed as failed:
        recorder.apply(study.record_failure(failed.record("ask_expert", data(task))))
        return ledger
    except Exception as e:
        recorder.apply(study.record_failure(crash(e).record("ask_expert", data(task))))
        return ledger
    record = StepRecord("ask_expert", StepStatus.OK, data(task), usage=run.usage)
    recorder.apply(study.record_expert_round(record, round_))
    return ledger
