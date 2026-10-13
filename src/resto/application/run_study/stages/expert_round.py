"""One Expert round (ADR-0025 §4): ask the Network Expert about the study's results so far, with
the last round forced when the study is free and `max_rounds` is reached."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.agents.expert import ExpertAgent
from resto.application.ports.llm import AgentRun
from resto.application.ports.network_query import NetworkQueryLoader
from resto.application.promoters.expert_answer import ExpertAnswerContext, ExpertAnswerPromoter
from resto.application.run_study.failures import StepFailed, crash, draft_of, promote
from resto.application.run_study.spend import StudySpend
from resto.application.run_study.step_data import data
from resto.application.tools.expert import EvidenceLedger
from resto.domain.entities.study import Study, Transition
from resto.domain.services.experiment_design import mode_for
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.tasks import ExpertTask


@dataclass(frozen=True, slots=True)
class ExpertRoundStage:
    expert: ExpertAgent
    network_queries: NetworkQueryLoader
    """Loads the networks of the Expert's scope for `promoter`."""
    promoter: ExpertAnswerPromoter

    def execute(self, study: Study, spend: StudySpend) -> Transition:
        """Asks the Expert and records its round in the current phase, or the failure that leaves
        the study `failed`."""
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
            run = spend.agent_call(lambda: self.expert.answer(task, ledger))
            draft_of(run, "expert")
            round_ = promote(lambda: self._promote(run, task, ledger), run.usage)
        except StepFailed as failed:
            return study.record_failure(failed.record("ask_expert", data(task)))
        except Exception as e:
            return study.record_failure(crash(e).record("ask_expert", data(task)))
        record = StepRecord("ask_expert", StepStatus.OK, data(task), usage=run.usage)
        return study.record_expert_round(record, round_)

    def _promote(
        self, run: AgentRun[ExpertAnswer], task: ExpertTask, ledger: EvidenceLedger
    ) -> ExpertRound:
        """Loads every network of the task's scope, then promotes the answer against them. A
        network that is not stored fails here even when no value names an edge."""
        networks = {
            network_id: self.network_queries.load(network_id) for network_id in task.network_ids
        }
        context = ExpertAnswerContext(task=task, ledger=ledger, networks=networks)
        return self.promoter.promote(run, context)
