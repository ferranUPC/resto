"""The study's first stage (ADR-0041 §7): the Input Parser turns the request into a `Question`."""

from __future__ import annotations

from resto.application.executor.deps import StudyDeps
from resto.application.executor.failures import StepFailed, crash, draft_of
from resto.application.executor.recorder import StudyRecorder
from resto.application.executor.spend import StudySpend
from resto.domain.value_objects.step_record import StepRecord, StepStatus


def parse_request(recorder: StudyRecorder, spend: StudySpend, deps: StudyDeps) -> None:
    """Calls the Input Parser on the study's text, through the study's spend like any agent, and
    records the `parse` step: the `Question` opens phase 0 (or leaves the study `awaiting_user`
    when it is ambiguous), a failure leaves the study `failed` at `parsing`."""
    study = recorder.study
    text = study.text
    task = {"text": text}
    try:
        run = spend.agent_call(lambda: deps.agents.parser.parse(text))
        question = draft_of(run, "input parser")
    except StepFailed as failed:
        recorder.apply(study.record_failure(failed.record("parse", task)))
        return
    except Exception as e:
        recorder.apply(study.record_failure(crash(e).record("parse", task)))
        return
    record = StepRecord("parse", StepStatus.OK, task, usage=run.usage)
    recorder.apply(study.accept_question(record, question))
