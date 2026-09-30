"""One Expert round (ADR-0025 §4): ask the Network Expert about the study's results so far, with
the last round forced when the study is free and `max_rounds` is reached."""

from __future__ import annotations

from dataclasses import replace

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, draft_of, promote
from resto.application.executor.recorder import StudyRecorder, data
from resto.application.executor.spend import StudySpend
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.ask_expert import ask_expert
from resto.domain.services.experiment_design import mode_for
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.tasks import ExpertTask


def ask_expert_round(
    recorder: StudyRecorder,
    spend: StudySpend,
    deps: StudyDeps,
    *,
    max_rounds: int,
) -> tuple[ExpertRound, EvidenceLedger] | None:
    """The round recorded in the current phase and the evidence ledger the Expert filled; or
    nothing, once the failure was recorded and the study is `failed`."""
    round_no = recorder.phase_index + 1
    question = recorder.study.question
    # the scope as it stands now: a network derived in an earlier phase is in it (ADR-0032)
    task = ExpertTask(
        question=question.text,
        mode=mode_for(question, round_no, max_rounds),
        network_ids=recorder.study.network_ids,
        result_ids=recorder.result_ids(),
    )
    ledger = EvidenceLedger()
    try:
        run = spend.agent_call(lambda: deps.agents.expert.answer(task, ledger))
        draft_of(run, "expert")
        round_ = promote(
            lambda: ask_expert(task, run, ledger, loader=deps.network_query_loader), run.usage
        )
    except StepFailed as failed:
        recorder.record_failure("ask_expert", data(task), failed)
        return None
    except Exception as e:
        recorder.record_failure("ask_expert", data(task), crash(e))
        return None
    forced_by_limit = question.mode is Mode.FREE and round_no == max_rounds
    round_ = replace(round_, forced_by_limit=forced_by_limit)
    record = StepRecord("ask_expert", StepStatus.OK, data(task), usage=run.usage)
    recorder.record(record, round_=round_)
    recorder.expert_round_held(round_no)
    return round_, ledger
