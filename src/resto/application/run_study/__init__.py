"""`RunStudy` (ADR-0023, ADR-0025, ADR-0026, ADR-0027, ADR-0042): user text -> a closed `Study`,
by deterministic code. It decides nothing about the domain: agents decide, promoters certify, the
`Study` makes its own transitions, and the loop of `RunStudy.execute` chains them.

    Study (at the request) -> parse -> [plan -> validate -> execute steps -> ask the Expert]*
    -> notes -> report

- **Stages** (`stages/`): parse, plan, Expert round, notes and compose, each with its
  collaborators in the constructor and one `execute(study, spend)` that returns the study's
  `Transition`. Only the notes stage stores: the notes are an aggregate of their own. Plan steps
  run through `steps`.
- **Agents** are reached through their ports (`application/ports/agents/`), their drafts promoted
  by the promoters (`application/promoters/`; network, demand and reroute pending until E6.1 and
  E7.1); both are bound in the composition root (`interface/dependencies.py`).
- **Persistence.** Every change is a transition of the `Study` (ADR-0041 §4), which returns the
  next `Study` and the domain events it produced. `RunStudy` stores the new study when it changed,
  then publishes its events on the event bus (`resto.application.event_bus`), whose handlers are
  the trace and note verification (`resto.application.event_handlers`). Telemetry (`ModelCall`,
  `NoteWriterFailed`) goes straight to the `Tracer` port.
- **Spend.** `StudySpend` starts at zero, counts tokens, agent calls (the Input Parser's included)
  and simulations, checks the `StudyBudget` before each agent call and each batch of new
  simulations, and emits each call's `ModelCall`.
- **Failures.** The first failure becomes a failed `StepRecord` with a `StepError` (ADR-0025 §3,
  classified in `failures`), the pending plan steps are recorded as skipped and the study is
  `failed` - all in one state. No re-ask: the only retry is inside `ToolAgent`.
- **Guards in code.** No re-run of an existing ok `result_id` (checked before the Runner), no
  Builder call for a scenario already stored under the requested id, a per-`Study` budget
  (`StudyBudget`) checked before every agent call and simulation, `max_rounds` with the last round
  forced (ADR-0025 §4).
- **Notes** (ADR-0026) are written once, after the final round; a failing note writer is traced and
  never fails the study. Unverified notes are checked against every *new* ok result only, once
  the study recorded the run step (`NoteVerificationHandler`, a bus handler: its failure is traced
  and never fails the study either).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from resto.application.event_bus import EventBus
from resto.application.ports.repositories import StudyRepository
from resto.application.ports.tracing import Tracer
from resto.application.run_study.deps import StepDeps, StudySettings
from resto.application.run_study.spend import StudySpend
from resto.application.run_study.stages.closing import ComposeStage, NotesStage
from resto.application.run_study.stages.expert_round import ExpertRoundStage
from resto.application.run_study.stages.parse import ParseStage
from resto.application.run_study.stages.plan import PlanStage
from resto.application.run_study.steps import execute_step
from resto.domain.constants import DEFAULT_MAX_ROUNDS
from resto.domain.entities.study import Study, Transition
from resto.domain.services.ids import new_id
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.study_action import (
    AskExpert,
    Close,
    ConsultExpert,
    Finished,
    OpenPhase,
    ParseRequest,
    PlanPhase,
    RunStep,
)


@dataclass(frozen=True, slots=True)
class RunStudy:
    parse: ParseStage
    plan: PlanStage
    expert_round: ExpertRoundStage
    notes: NotesStage
    compose: ComposeStage
    steps: StepDeps
    settings: StudySettings
    studies: StudyRepository
    events: EventBus
    tracer: Tracer

    def execute(
        self, text: str, *, mode: Mode | None = None, max_rounds: int = DEFAULT_MAX_ROUNDS
    ) -> Study:
        """Runs the user's request until the `Study` has a resolution (`completed`, `failed` or
        `awaiting_user`) and returns it. The study is created at the request, with parsing as its
        first stage; `mode`, when given, is the user's choice and overrides the Input Parser's."""
        study = self._record(None, Study.open(new_id(), text, mode, max_rounds=max_rounds))
        spend = StudySpend(self.settings.budget, self.tracer, study.study_id)
        while True:
            match study.next_action():
                case Finished():
                    return study
                case ParseRequest():
                    transition = self.parse.execute(study, spend)
                case PlanPhase():
                    transition = self.plan.execute(study, spend)
                case RunStep(step):
                    transition = execute_step(step, study, spend, self.steps, self.settings)
                case ConsultExpert():
                    transition = study.consult_expert()
                case AskExpert():
                    transition = self.expert_round.execute(study, spend)
                case OpenPhase():
                    transition = study.open_phase()
                case Close():
                    study = self._record(study, self.notes.execute(study, spend))
                    transition = self.compose.execute(study, spend)
                case action:
                    assert_never(action)
            study = self._record(study, transition)

    def _record(self, previous: Study | None, transition: Transition) -> Study:
        """Stores the next study when the transition changed it, then publishes its events."""
        study, events = transition
        if study is not previous:
            self.studies.store(study)
        self.events.publish(study.study_id, events)
        return study
