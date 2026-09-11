from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepRecord
from resto.domain.value_objects.study_plan import StudyPlan

DEFAULT_MAX_ROUNDS = 3


class StudyStatus(StrEnum):
    PLANNING = "planning"
    RUNNING = "running"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Study:
    """Root of one user request: the question, the plan, every step taken, the experiments
    run, the Expert rounds and the final report. Framework run-time state, stored through
    StudyRepository (not part of the DatabaseMCP contract)."""

    study_id: str
    question: Question
    status: StudyStatus = StudyStatus.PLANNING
    plan: StudyPlan | None = None
    steps: tuple[StepRecord, ...] = ()
    experiments: tuple[Experiment, ...] = ()
    rounds: tuple[ExpertRound, ...] = ()
    report: Report | None = None
    network_ids: tuple[str, ...] = ()
    note_ids: tuple[str, ...] = ()
    max_rounds: int = DEFAULT_MAX_ROUNDS

    def __post_init__(self) -> None:
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        if self.steps and self.plan is None:
            raise ValueError("a StudyPlan must exist before the first step")
        if len(self.rounds) > self.max_rounds:
            raise ValueError("the Expert loop exceeded max_rounds")
        if self.question.mode is Mode.FORCED and any(r.triggered_experiments for r in self.rounds):
            raise ValueError("forced mode never triggers experiments")
        if self.question.is_ambiguous and (
            self.steps or self.status is not StudyStatus.AWAITING_USER
        ):
            raise ValueError("an ambiguous question puts the study in awaiting_user with no steps")
        if self.status is StudyStatus.COMPLETED and self.report is None:
            raise ValueError("a completed study must carry a report")
        for r in self.rounds:
            if any(i >= len(self.experiments) for i in r.triggered_experiments):
                raise ValueError("a round references an experiment that does not exist")

    @property
    def rounds_left(self) -> int:
        return self.max_rounds - len(self.rounds)
