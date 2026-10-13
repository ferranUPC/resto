from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import pairwise

from resto.domain.constants import DEFAULT_MAX_ROUNDS
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.outcomes import NeedsUser
from resto.domain.value_objects.question import Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.study_plan import StudyPlan


class StudyStage(StrEnum):
    """Where a study is in its lifecycle, or where it stopped (ADR-0041 §3). Planning, running and
    consulting the Expert repeat once per phase; closing writes the notes and the report."""

    PARSING = "parsing"
    PLANNING = "planning"
    RUNNING = "running"
    CONSULTING_EXPERT = "consulting_expert"
    CLOSING = "closing"


class StudyResolution(StrEnum):
    """How a study ended; a study without one is open. A failed study keeps its stage."""

    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_USER = "awaiting_user"


@dataclass(frozen=True, slots=True)
class Phase:
    """One question planned and executed, then put to the Expert (ADR-0023 §4). `phases[0]` holds
    the Input Parser's question; each later phase the previous round's `proposed_experiment`.

    A phase without a plan ran nothing: its only possible step is the failed planning itself. The
    planning is always the phase's first step: a plan whose first step failed was rejected.

    `needs_user` is a specialist asking the user to act (ADR-0037 §4): the step that returned it
    has status `needs_user` and the rest of the plan is skipped, as after a failure."""

    question: Question
    plan: StudyPlan | None = None
    needs_user: NeedsUser | None = None
    steps: tuple[StepRecord, ...] = ()
    experiments: tuple[Experiment, ...] = ()
    round: ExpertRound | None = None

    def __post_init__(self) -> None:
        if self.plan is None:
            if len(self.steps) > 1 or any(s.status is not StepStatus.FAILED for s in self.steps):
                raise ValueError("a phase without a plan holds at most its failed planning step")
            if self.experiments or self.round is not None:
                raise ValueError("experiments and the Expert round need a plan")
        waiting = [i for i, s in enumerate(self.steps) if s.status is StepStatus.NEEDS_USER]
        if (self.needs_user is not None) != bool(waiting):
            raise ValueError("a phase holds needs_user if and only if a step needed the user")
        stops = [
            i
            for i, s in enumerate(self.steps)
            if s.status in (StepStatus.FAILED, StepStatus.NEEDS_USER)
        ]
        if stops and any(s.status is not StepStatus.SKIPPED for s in self.steps[stops[0] + 1 :]):
            raise ValueError("the Executor stops at the first stop: later steps are skipped")

    @property
    def failed_step(self) -> StepRecord | None:
        return next((s for s in self.steps if s.status is StepStatus.FAILED), None)

    @property
    def planned(self) -> bool:
        """The phase has a plan and its planning, the first step, did not fail."""
        return self.plan is not None and not (
            self.steps and self.steps[0].status is StepStatus.FAILED
        )


@dataclass(frozen=True, slots=True)
class Study:
    """Root of one user request, stored in phases: the questions, the plans, every step taken, the
    experiments run, the Expert rounds and the final report. Framework run-time state, stored
    through StudyRepository (not part of the DatabaseMCP contract).

    `stage` and `resolution` are stored (ADR-0041 §3) and checked against the phases: `resolution`
    is `None` while the study is open, and a failed study keeps the stage it failed in."""

    study_id: str
    stage: StudyStage
    phases: tuple[Phase, ...]
    resolution: StudyResolution | None = None
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
        self._check_resolution()
        self._check_stage()

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

    def _check_resolution(self) -> None:
        first, last = self.phases[0], self.phases[-1]
        resolution = self.resolution
        if self.question.is_ambiguous and (
            len(self.phases) > 1
            or first.plan is not None
            or first.steps
            or resolution is not StudyResolution.AWAITING_USER
        ):
            raise ValueError("an ambiguous question puts the study in awaiting_user with no steps")
        if any(p.needs_user is not None for p in self.phases[:-1]):
            raise ValueError("a step that needed the user ends the study: only the last phase")
        if last.needs_user is not None and resolution is not StudyResolution.AWAITING_USER:
            raise ValueError("a step that needed the user puts the study in awaiting_user")
        if resolution is StudyResolution.AWAITING_USER and not (
            self.question.is_ambiguous or last.needs_user is not None
        ):
            raise ValueError("awaiting_user needs the ambiguities or a specialist's message")
        failures = [s for p in self.phases for s in p.steps if s.status is StepStatus.FAILED]
        if (resolution is StudyResolution.FAILED) != bool(failures):
            raise ValueError("a study is failed if and only if a step failed")
        if failures and (len(failures) > 1 or last.failed_step is None):
            raise ValueError("a failed study stops at its first failed step, in the last phase")
        if (resolution is StudyResolution.COMPLETED) != (self.report is not None):
            raise ValueError("a report is composed if and only if the study completed")

    def _check_stage(self) -> None:
        """The stage against the resolution and the last phase. Until the Input Parser runs inside
        the study (ADR-0041 §7), a study is at `parsing` only when the Parser left ambiguities."""
        stage, resolution, last = self.stage, self.resolution, self.phases[-1]
        if (stage is StudyStage.PARSING) != self.question.is_ambiguous:
            raise ValueError("a study stops at parsing if and only if its question is ambiguous")
        if resolution is StudyResolution.AWAITING_USER and stage not in (
            StudyStage.PARSING,
            StudyStage.RUNNING,
        ):
            raise ValueError("a study is awaiting_user only at parsing or while running")
        if resolution is StudyResolution.COMPLETED and stage is not StudyStage.CLOSING:
            raise ValueError("a completed study ends at closing")
        if stage is StudyStage.PARSING:
            return
        if stage is StudyStage.PLANNING:
            if last.planned or last.round is not None:
                raise ValueError("a study at planning has not accepted the plan of its last phase")
            return
        if not last.planned:
            raise ValueError(f"a study at {stage} has an accepted plan in its last phase")
        asks = last.round is not None and last.round.answer.needs_simulation
        if stage is StudyStage.RUNNING and last.round is not None:
            raise ValueError("a running study has not consulted the Expert in its last phase")
        if stage is StudyStage.CONSULTING_EXPERT:
            if any(s.status is StepStatus.SKIPPED for s in last.steps):
                raise ValueError("a study at consulting_expert ran every step of its plan")
            if last.round is not None and not asks:
                raise ValueError("an Expert answer that needs no simulation moves to closing")
        if stage is StudyStage.CLOSING and (last.round is None or asks):
            raise ValueError("a study at closing ends on an Expert answer")

    @property
    def question(self) -> Question:
        return self.phases[0].question

    @property
    def rounds(self) -> tuple[ExpertRound, ...]:
        return tuple(p.round for p in self.phases if p.round is not None)

    @property
    def rounds_left(self) -> int:
        return self.max_rounds - len(self.rounds)
