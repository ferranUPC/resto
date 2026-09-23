from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from resto.domain.constants import DEFAULT_MAX_ROUNDS
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.study_plan import ClarificationRequest, StudyPlan


class StudyStatus(StrEnum):
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Phase:
    """One question planned and executed, then put to the Expert (ADR-0023 §4). `phases[0]` holds
    the Input Parser's question; each later phase the previous round's `proposed_experiment`.

    `clarification` is the Coordinator asking the user instead of planning (phase 0 only). A phase
    without a plan ran nothing: its only possible step is the failed planning itself."""

    question: Question
    plan: StudyPlan | None = None
    clarification: ClarificationRequest | None = None
    steps: tuple[StepRecord, ...] = ()
    experiments: tuple[Experiment, ...] = ()
    round: ExpertRound | None = None

    def __post_init__(self) -> None:
        if self.plan is not None and self.clarification is not None:
            raise ValueError("the Coordinator returns either a plan or a clarification")
        if self.plan is None:
            if len(self.steps) > 1 or any(s.status is not StepStatus.FAILED for s in self.steps):
                raise ValueError("a phase without a plan holds at most its failed planning step")
            if self.experiments or self.round is not None:
                raise ValueError("experiments and the Expert round need a plan")
        if self.clarification is not None and self.steps:
            raise ValueError("a clarification is not a failure: it records no step")
        failed = [i for i, s in enumerate(self.steps) if s.status is StepStatus.FAILED]
        if failed and any(s.status is not StepStatus.SKIPPED for s in self.steps[failed[0] + 1 :]):
            raise ValueError("the Executor stops at the first failure: later steps are skipped")

    @property
    def failed_step(self) -> StepRecord | None:
        return next((s for s in self.steps if s.status is StepStatus.FAILED), None)


@dataclass(frozen=True, slots=True)
class Study:
    """Root of one user request, stored in phases: the questions, the plans, every step taken, the
    experiments run, the Expert rounds and the final report. Framework run-time state, stored
    through StudyRepository (not part of the DatabaseMCP contract)."""

    study_id: str
    status: StudyStatus
    phases: tuple[Phase, ...]
    report: Report | None = None
    network_ids: tuple[str, ...] = ()
    note_ids: tuple[str, ...] = ()
    max_rounds: int = DEFAULT_MAX_ROUNDS

    def __post_init__(self) -> None:
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        if not self.phases:
            raise ValueError("a Study starts with the phase of the user's question")
        self._check_loop()
        self._check_status()

    def _check_loop(self) -> None:
        for k, (phase, following) in enumerate(pairwise(self.phases)):
            if phase.round is None or following.question != phase.round.answer.proposed_experiment:
                raise ValueError(f"phase {k + 1} must ask the experiment proposed in round {k + 1}")
        if len(self.rounds) > self.max_rounds:
            raise ValueError("the Expert loop exceeded max_rounds")
        free = self.question.mode is Mode.FREE
        asks = any(r.answer.needs_simulation for r in self.rounds)
        if not free and (len(self.phases) > 1 or asks):
            raise ValueError("forced mode has one phase and never asks for a simulation")
        for k, phase in enumerate(self.phases):
            if phase.round is None:
                continue
            last_allowed = free and k == self.max_rounds - 1
            if phase.round.forced_by_limit != last_allowed:
                raise ValueError(
                    "round max_rounds of a free study, and only that one, is forced by the limit"
                )
        if any(p.clarification is not None for p in self.phases[1:]):
            raise ValueError("only phase 0 has a user to ask: later clarifications fail the round")

    def _check_status(self) -> None:
        first, last = self.phases[0], self.phases[-1]
        if self.question.is_ambiguous and (
            len(self.phases) > 1
            or first.plan is not None
            or first.steps
            or self.status is not StudyStatus.AWAITING_USER
        ):
            raise ValueError("an ambiguous question puts the study in awaiting_user with no steps")
        if first.clarification is not None and self.status is not StudyStatus.AWAITING_USER:
            raise ValueError("a Coordinator clarification puts the study in awaiting_user")
        if self.status is StudyStatus.AWAITING_USER and not (
            self.question.is_ambiguous or first.clarification is not None
        ):
            raise ValueError("awaiting_user needs the ambiguities or the candidates to show")
        failures = [s for p in self.phases for s in p.steps if s.status is StepStatus.FAILED]
        if (self.status is StudyStatus.FAILED) != bool(failures):
            raise ValueError("a study is failed if and only if a step failed")
        if failures and (len(failures) > 1 or last.failed_step is None):
            raise ValueError("a failed study stops at its first failed step, in the last phase")
        if (self.status is StudyStatus.COMPLETED) != (self.report is not None):
            raise ValueError("a report is composed if and only if the study completed")
        if self.status is StudyStatus.COMPLETED and (
            last.round is None or last.round.answer.needs_simulation
        ):
            raise ValueError("a completed study ends on an Expert answer")

    @property
    def question(self) -> Question:
        return self.phases[0].question

    @property
    def rounds(self) -> tuple[ExpertRound, ...]:
        return tuple(p.round for p in self.phases if p.round is not None)

    @property
    def rounds_left(self) -> int:
        return self.max_rounds - len(self.rounds)
