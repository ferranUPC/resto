"""The study's first stage (ADR-0041 §7): the Input Parser turns the request into a `Question`."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.agents.input_parser import InputParserAgent
from resto.application.run_study.failures import StepFailed, crash, draft_of
from resto.application.run_study.spend import StudySpend
from resto.domain.entities.study import Study, Transition
from resto.domain.value_objects.step_record import StepRecord, StepStatus


@dataclass(frozen=True, slots=True)
class ParseStage:
    parser: InputParserAgent

    def execute(self, study: Study, spend: StudySpend) -> Transition:
        """Calls the Input Parser on the study's text, through the study's spend like any agent:
        the `Question` opens phase 0 (or leaves the study `awaiting_user` when it is ambiguous),
        a failure leaves the study `failed` at `parsing`."""
        text = study.text
        task = {"text": text}
        try:
            run = spend.agent_call(lambda: self.parser.parse(text))
            question = draft_of(run, "input parser")
        except StepFailed as failed:
            return study.record_failure(failed.record("parse", task))
        except Exception as e:
            return study.record_failure(crash(e).record("parse", task))
        record = StepRecord("parse", StepStatus.OK, task, usage=run.usage)
        return study.accept_question(record, question)
