from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import pairwise
from typing import assert_never

from resto.domain.constants import DEFAULT_MAX_ROUNDS
from resto.domain.events import (
    ExpertRoundHeld,
    NetworksAdded,
    NotesWritten,
    PhaseStarted,
    PlanMade,
    ReportComposed,
    SimulationsRecorded,
    StepTraced,
    StudyCreated,
    StudyEvent,
)
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.outcomes import NeedsUser
from resto.domain.value_objects.question import Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepRecord, StepStatus, Usage
from resto.domain.value_objects.study_action import (
    AskExpert,
    Close,
    ConsultExpert,
    Finished,
    OpenPhase,
    PlanPhase,
    RunPlan,
    StudyAction,
)
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    FromStep,
    PlanStep,
    RunSimulationStep,
    StudyPlan,
)


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
    def pending_steps(self) -> tuple[PlanStep, ...]:
        """The steps of the plan not recorded yet. The planning is the phase's first step, so
        plan step `i` is recorded as step `i + 1`."""
        if self.plan is None:
            return ()
        return self.plan.steps[max(len(self.steps) - 1, 0) :]

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
    is `None` while the study is open, and a failed study keeps the stage it failed in.

    Every state after the first is made by a transition (ADR-0041 §4), from `open` on: each returns
    the next study and the domain events it produced (`Transition`), and only an open study takes
    one."""

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
    def current_phase(self) -> Phase:
        """The last phase: the one being planned, run or put to the Expert."""
        return self.phases[-1]

    @property
    def phase_index(self) -> int:
        """The index of the current phase; phase 0 holds the Input Parser's question."""
        return len(self.phases) - 1

    @property
    def rounds(self) -> tuple[ExpertRound, ...]:
        return tuple(p.round for p in self.phases if p.round is not None)

    @property
    def rounds_left(self) -> int:
        return self.max_rounds - len(self.rounds)

    @property
    def next_round_no(self) -> int:
        """The number of the next Expert round, counting from 1."""
        return len(self.rounds) + 1

    @property
    def next_round_forced_by_limit(self) -> bool:
        """The next round is round `max_rounds` of a free study, sent forced because the rounds
        run out (ADR-0025 §4)."""
        return self.question.mode is Mode.FREE and self.next_round_no == self.max_rounds

    @property
    def result_ids(self) -> tuple[str, ...]:
        """The result ids of every experiment of the study, in order, without repeats."""
        ids = (r for p in self.phases for e in p.experiments for r in e.result_ids)
        return tuple(dict.fromkeys(ids))

    @property
    def realised_arms(self) -> tuple[str, ...]:
        """The arms the phases before the current one realised, in order: they are not planned
        again."""
        return tuple(e.arm for p in self.phases[:-1] for e in p.experiments)

    def next_action(self) -> StudyAction:
        """What the study needs next (ADR-0041 §5), from its stage and its last phase. A resolved
        study needs nothing. The caller performs the action and applies its outcome."""
        last = self.current_phase
        if self.resolution is not None:
            return Finished()
        match self.stage:
            case StudyStage.PARSING:
                raise ValueError("an open study at parsing waits for the Input Parser (ADR-0041)")
            case StudyStage.PLANNING:
                return PlanPhase()
            case StudyStage.RUNNING:
                assert last.plan is not None  # a running study accepted its phase's plan
                return RunPlan(last.plan) if last.pending_steps else ConsultExpert()
            case StudyStage.CONSULTING_EXPERT:
                return OpenPhase() if last.round is not None else AskExpert()
            case StudyStage.CLOSING:
                assert last.round is not None  # a closing study ends on an Expert answer
                return Close(last.round)
            case _:
                assert_never(self.stage)

    # -- transitions (ADR-0041 §4): each returns the next study and the events it produced ------

    @classmethod
    def open(
        cls, study_id: str, question: Question, parse_usage: Usage, *, max_rounds: int
    ) -> Transition:
        """The study of the Input Parser's `question`, on phase 0 at `planning`; at `parsing`,
        awaiting the user, when the question is ambiguous. `parse_usage` is what the Parser spent,
        told by `StudyCreated` until the Parser runs inside the study (ADR-0041 §7)."""
        if question.is_ambiguous:
            stage, resolution = StudyStage.PARSING, StudyResolution.AWAITING_USER
        else:
            stage, resolution = StudyStage.PLANNING, None
        study = cls(
            study_id, stage, (Phase(question),), resolution=resolution, max_rounds=max_rounds
        )
        return study, (StudyCreated(question, parse_usage), PhaseStarted(0))

    def accept_plan(self, plan: StudyPlan, record: StepRecord) -> Transition:
        """The valid `plan` of the current phase and its `plan` step: the study starts running."""
        self._require(StudyStage.PLANNING)
        phase = replace(self.current_phase, plan=plan, steps=(record,))
        study = self._with_phase(phase, stage=StudyStage.RUNNING)
        return study, (PlanMade(self.phase_index, plan),)

    def reject_plan(self, plan: StudyPlan, record: StepRecord) -> Transition:
        """The planner's `plan` did not validate: the phase keeps it, its failed `plan` step
        first and every step of the plan skipped, and the study fails at `planning`."""
        self._require(StudyStage.PLANNING)
        skipped = tuple(StepRecord(s.kind, StepStatus.SKIPPED) for s in plan.steps)
        return self._fail(replace(self.current_phase, plan=plan), record, skipped)

    def record_step(
        self, record: StepRecord, *, reused_result_ids: tuple[str, ...] = ()
    ) -> Transition:
        """The ok `record` of the next step of the plan, with what it changed in the phase.

        `reused_result_ids` are results stored before the step: a `build_scenario` step that found
        its scenario stored with ok results reuses them, and a `run_simulation` step reuses the
        results of the seeds it did not run again. A built scenario becomes an `Experiment` of its
        arm; a run's results join the experiment of the step that built its scenario (none when
        the plan names a stored scenario) and produce `SimulationsRecorded`."""
        self._require(StudyStage.RUNNING)
        step = self._next_plan_step(record)
        reused = reused_result_ids
        phase = self.current_phase
        events: list[StudyEvent] = [self._traced(record)]
        match step:
            case BuildScenarioStep():
                if len(record.produced_ids) != 1:
                    raise ValueError("a build_scenario step produces one scenario")
                experiment = Experiment(
                    record.produced_ids[0],
                    step.arm,
                    step.role,
                    step.purpose,
                    result_ids=reused,
                    reused=bool(reused),
                )
                phase = replace(phase, experiments=(*phase.experiments, experiment))
            case RunSimulationStep():
                if not set(reused) <= set(record.produced_ids):
                    raise ValueError("a run can reuse only results it holds")
                phase, scenario_id = _join_run(phase, step, record.produced_ids)
                events.append(
                    SimulationsRecorded(
                        self.phase_index,
                        scenario_id,
                        new_result_ids=tuple(r for r in record.produced_ids if r not in reused),
                        reused_result_ids=tuple(r for r in record.produced_ids if r in reused),
                    )
                )
            case _ if reused:
                raise ValueError("only build_scenario and run_simulation steps reuse results")
        phase = replace(phase, steps=(*phase.steps, record))
        return self._with_phase(phase), tuple(events)

    def record_needs_user(self, record: StepRecord, needs_user: NeedsUser) -> Transition:
        """The step that needed the user, the steps of the plan left unrun skipped and the study
        `awaiting_user`, in one state."""
        self._require(StudyStage.RUNNING)
        self._next_plan_step(record)
        phase = self.current_phase
        phase = replace(
            phase,
            steps=(*phase.steps, record, *_pending_skipped(phase)),
            needs_user=needs_user,
        )
        study = self._with_phase(phase, resolution=StudyResolution.AWAITING_USER)
        return study, (self._traced(record),)

    def add_networks(self, *network_ids: str) -> Transition:
        """The networks among `network_ids` the study has not used yet, added in order; no change
        and no event when none is new."""
        self._require()
        merged = tuple(dict.fromkeys((*self.network_ids, *network_ids)))
        if merged == self.network_ids:
            return self, ()
        added = merged[len(self.network_ids) :]
        return replace(self, network_ids=merged), (NetworksAdded(added),)

    def consult_expert(self) -> Transition:
        """Every step of the plan is recorded: the study is about to ask the Expert."""
        self._require(StudyStage.RUNNING)
        if self.current_phase.pending_steps:
            raise ValueError("the Expert is consulted once every step of the plan is recorded")
        return replace(self, stage=StudyStage.CONSULTING_EXPERT), ()

    def record_expert_round(self, record: StepRecord, round_: ExpertRound) -> Transition:
        """The Expert's round of the current phase and its `ask_expert` step. The study marks the
        round `forced_by_limit` (`next_round_forced_by_limit`), whatever `round_` says. An answer
        that needs no simulation moves the study to `closing` in the same state."""
        self._require(StudyStage.CONSULTING_EXPERT)
        if self.current_phase.round is not None:
            raise ValueError("the current phase already holds its Expert round")
        round_ = replace(round_, forced_by_limit=self.next_round_forced_by_limit)
        phase = self.current_phase
        phase = replace(phase, steps=(*phase.steps, record), round=round_)
        answered = not round_.answer.needs_simulation
        study = self._with_phase(phase, stage=StudyStage.CLOSING if answered else None)
        return study, (self._traced(record), ExpertRoundHeld(self.phase_index, self.next_round_no))

    def open_phase(self) -> Transition:
        """The next phase, on the experiment the Expert proposed in the current one, at
        `planning`."""
        self._require(StudyStage.CONSULTING_EXPERT)
        round_ = self.current_phase.round
        proposed = None if round_ is None else round_.answer.proposed_experiment
        if proposed is None:
            raise ValueError("a phase opens only on an experiment the Expert proposed")
        study = replace(self, phases=(*self.phases, Phase(proposed)), stage=StudyStage.PLANNING)
        return study, (PhaseStarted(study.phase_index),)

    def record_notes(self, note_ids: tuple[str, ...]) -> Transition:
        """The ids of the Expert notes written after the final round."""
        self._require(StudyStage.CLOSING)
        return replace(self, note_ids=note_ids), (NotesWritten(note_ids),)

    def complete(self, record: StepRecord, report: Report) -> Transition:
        """The Output Composer's `report` and its `compose_report` step: the study `completed`."""
        self._require(StudyStage.CLOSING)
        phase = self.current_phase
        phase = replace(phase, steps=(*phase.steps, record))
        study = replace(
            self,
            phases=(*self.phases[:-1], phase),
            resolution=StudyResolution.COMPLETED,
            report=report,
        )
        return study, (self._traced(record), ReportComposed())

    def record_failure(self, record: StepRecord) -> Transition:
        """The failed step, the steps of the plan left unrun skipped and the study `failed`, in
        one state; the study keeps the stage it failed in."""
        self._require()
        return self._fail(self.current_phase, record, _pending_skipped(self.current_phase))

    # -- internals ----------------------------------------------------------------------------

    def _require(self, *stages: StudyStage) -> None:
        """The transition applies only to an open study, at one of `stages` when any is given."""
        if self.resolution is not None:
            raise ValueError(f"the study is {self.resolution}: it takes no more transitions")
        if stages and self.stage not in stages:
            raise ValueError(f"the study is at {self.stage}, not at {' or '.join(stages)}")

    def _with_phase(
        self,
        phase: Phase,
        *,
        stage: StudyStage | None = None,
        resolution: StudyResolution | None = None,
    ) -> Study:
        """This study with `phase` in place of the current one."""
        return replace(
            self,
            phases=(*self.phases[:-1], phase),
            stage=stage or self.stage,
            resolution=resolution or self.resolution,
        )

    def _next_plan_step(self, record: StepRecord) -> PlanStep:
        """The step of the plan `record` is the outcome of: the first one not recorded yet."""
        pending = self.current_phase.pending_steps
        if not pending:
            raise ValueError("every step of the plan is recorded")
        if record.tool != pending[0].kind:
            raise ValueError(f"the next step of the plan is {pending[0].kind}, not {record.tool}")
        return pending[0]

    def _fail(
        self, phase: Phase, record: StepRecord, skipped: tuple[StepRecord, ...]
    ) -> Transition:
        phase = replace(phase, steps=(*phase.steps, record, *skipped))
        study = self._with_phase(phase, resolution=StudyResolution.FAILED)
        return study, (self._traced(record),)

    def _traced(self, record: StepRecord) -> StepTraced:
        return StepTraced(
            phase=self.phase_index,
            tool=record.tool,
            status=record.status,
            produced_ids=record.produced_ids,
            usage=record.usage,
            error=record.error,
        )


def _pending_skipped(phase: Phase) -> tuple[StepRecord, ...]:
    """The plan steps of `phase` not recorded yet, as skipped steps. The planning is the phase's
    first step, so plan step `i` is recorded as step `i + 1`."""
    if phase.plan is None:
        return ()
    return tuple(
        StepRecord(s.kind, StepStatus.SKIPPED) for s in phase.plan.steps[len(phase.steps) :]
    )


def _join_run(
    phase: Phase, step: RunSimulationStep, result_ids: tuple[str, ...]
) -> tuple[Phase, str]:
    """`phase` with the run's results joined, without repeats, to the experiment of the build
    step its scenario comes from, and that scenario's id. Each build step adds one experiment, so
    build step `j` made the experiment after those of the build steps before it. A run on a
    stored scenario (an id in the plan) joins no experiment."""
    if not isinstance(step.scenario_id, FromStep):
        return phase, step.scenario_id
    assert phase.plan is not None  # a phase that ran a step has a plan
    built = phase.plan.steps[: step.scenario_id.step]
    j = sum(isinstance(s, BuildScenarioStep) for s in built)
    target = phase.experiments[j]
    target = replace(target, result_ids=tuple(dict.fromkeys((*target.result_ids, *result_ids))))
    experiments = (*phase.experiments[:j], target, *phase.experiments[j + 1 :])
    return replace(phase, experiments=experiments), target.scenario_id


Transition = tuple[Study, tuple[StudyEvent, ...]]
"""The next study and the events its transition produced, in the order they happened."""
