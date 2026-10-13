from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, replace
from enum import StrEnum
from itertools import pairwise
from typing import Any, assert_never

from resto.domain.constants import DEFAULT_MAX_ROUNDS
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
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
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.outcomes import NeedsUser
from resto.domain.value_objects.question import Mode, Question
from resto.domain.value_objects.report import Report
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.study_action import (
    AskExpert,
    Close,
    ConsultExpert,
    Finished,
    OpenPhase,
    ParseRequest,
    PlanPhase,
    RunStep,
    StudyAction,
)
from resto.domain.value_objects.study_plan import FromStep, PlanStep, Produces, StudyPlan
from resto.domain.value_objects.tasks import NoteScenario, NoteTask


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
    def next_plan_index(self) -> int:
        """The index in the plan of the first step not recorded yet. The planning is the phase's
        first step, so plan step `i` is recorded as step `i + 1`."""
        return max(len(self.steps) - 1, 0)

    @property
    def pending_steps(self) -> tuple[PlanStep, ...]:
        """The steps of the plan not recorded yet, in plan order. Steps run one at a time in the
        order the plan lists them, so the next step to run is the first one and, after a stop,
        every one of them is skipped."""
        # TODO(dag): steps whose `depends_on` do not join could run in parallel; the next and the
        # skipped steps would then come from the dependency graph, not from the plan order.
        if self.plan is None:
            return ()
        return self.plan.steps[self.next_plan_index :]

    @property
    def network_id(self) -> str | None:
        """The network this phase's plan is about: the id the plan names, or the one its step
        produced. None without a plan, or while that step is not recorded ok."""
        if self.plan is None:
            return None
        ref = self.plan.network_id
        if isinstance(ref, str):
            return ref
        recorded = ref.step + 1 < len(self.steps)
        if not recorded or self.steps[ref.step + 1].status is not StepStatus.OK:
            return None
        return self._produced(ref)

    def resolved(self, step: PlanStep) -> PlanStep:
        """`step` with every `FromStep` replaced by the id the step it points to produced. The
        steps it points to come earlier in the plan, so this phase recorded them."""
        changes: dict[str, Any] = {
            f.name: self._produced(ref)
            for f in fields(step)
            if isinstance(ref := getattr(step, f.name), FromStep)
        }
        return replace(step, **changes)

    def named_ids(self, step: PlanStep, kind: Produces) -> tuple[str, ...]:
        """The ids of `kind` that `step` names: directly, or through a `FromStep` to a step this
        phase recorded."""
        direct = tuple(ref for k, ref in step.refs() if k == kind)
        built = tuple(self._produced(ref) for ref, k in step.inputs if k == kind)
        return direct + built

    def _produced(self, ref: FromStep) -> str:
        """The id plan step `ref.step` produced: the last of its ids."""
        return self.steps[ref.step + 1].produced_ids[-1]

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
    one.

    A study starts at the request (ADR-0041 §2): `text` and, when the user chose one, `mode`, with
    no phases at `parsing`. The Input Parser's call is the `parse` step, kept outside the phases:
    ok once its `Question` opened phase 0 (which is also the study's state when the question is
    ambiguous), failed when the study failed at `parsing`, and absent while the study waits for
    the Parser."""

    study_id: str
    stage: StudyStage
    phases: tuple[Phase, ...]
    text: str
    mode: Mode | None = None
    parse: StepRecord | None = None
    resolution: StudyResolution | None = None
    report: Report | None = None
    network_ids: tuple[str, ...] = ()
    note_ids: tuple[str, ...] = ()
    max_rounds: int = DEFAULT_MAX_ROUNDS

    def __post_init__(self) -> None:
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        self._check_parse()
        if not self.phases:
            return
        self._check_loop()
        self._check_resolution()
        self._check_stage()

    def _check_parse(self) -> None:
        """The request and the `parse` step against the phases: a study with phases has an ok
        `parse` step; one failed at `parsing` has a failed one and no phases; an open one at
        `parsing` has none. A study is failed if and only if a step failed, the `parse` step
        included."""
        if not self.text.strip():
            raise ValueError("a Study requires the text of the request")
        parse, resolution = self.parse, self.resolution
        if parse is not None and parse.tool != "parse":
            raise ValueError("the parse step is the Input Parser's call")
        if self.phases:
            if parse is None or parse.status is not StepStatus.OK:
                raise ValueError("a study with phases has an ok parse step")
            if self.mode is not None and self.question.mode is not self.mode:
                raise ValueError("the question keeps the mode the user chose")
            return
        if self.stage is not StudyStage.PARSING:
            raise ValueError("a study without phases is at parsing")
        if (resolution is StudyResolution.FAILED) != (
            parse is not None and parse.status is StepStatus.FAILED
        ):
            raise ValueError("a study is failed if and only if a step failed")
        if resolution is None and parse is not None:
            raise ValueError("an open study at parsing has no parse step")
        if resolution not in (None, StudyResolution.FAILED):
            raise ValueError("a study without phases is open or failed at parsing")
        if resolution is StudyResolution.FAILED and parse is None:
            raise ValueError("a study failed at parsing has a failed parse step")

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
        """The stage against the resolution and the last phase. A study with phases is at `parsing`
        only when the Parser left ambiguities."""
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
            raise ValueError(f"a study at {stage} has no accepted plan in its last phase")
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
        """The Input Parser's question, once it is parsed (it is `phases[0].question`)."""
        if not self.phases:
            raise ValueError("the study has no question until the Input Parser has run")
        return self.phases[0].question

    @property
    def failed_step(self) -> StepRecord | None:
        """The step that failed the study: the `parse` step when it failed at `parsing`, else the
        failed step of its last phase."""
        if not self.phases:
            return self.parse
        return self.phases[-1].failed_step

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

    @property
    def network_id(self) -> str | None:
        """The network the study is about, as the plan of its latest phase that knows it says
        (`Phase.network_id`); the planner of a later phase is told it. None until a plan fixes
        it. Not to be confused with `network_ids`, every network the study used."""
        return next((n for p in reversed(self.phases) if (n := p.network_id) is not None), None)

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        """The scenario of every experiment of the study, in order, without repeats."""
        return tuple(dict.fromkeys(e.scenario_id for p in self.phases for e in p.experiments))

    def note_task(
        self, *, scenarios: Mapping[str, Scenario], networks: Mapping[str, Network]
    ) -> NoteTask:
        """The note writer's task about the final Expert round, at closing (ADR-0026).
        `scenarios` and `networks` are the study's own, as the caller loaded them by
        `scenario_ids` and `network_ids`: an id missing from them is not stored."""
        self._require(StudyStage.CLOSING)
        final = self.current_phase.round
        assert final is not None  # a closing study ends on an Expert answer
        return NoteTask(final, self._base_network_id(networks), self._allow_list(scenarios))

    def _allow_list(self, scenarios: Mapping[str, Scenario]) -> tuple[NoteScenario, ...]:
        """Every scenario of the study, plus the predicted id of each arm of the original question
        that was not realised and keeps the topology (ADR-0026)."""
        entries: dict[str, NoteScenario] = {}
        experiments = [e for p in self.phases for e in p.experiments]
        for e in experiments:
            scenario = scenarios.get(e.scenario_id)
            if scenario is None:
                raise ValueError(f"scenario {e.scenario_id!r} of the study is not stored")
            entries.setdefault(
                e.scenario_id,
                NoteScenario(
                    e.scenario_id, e.arm, e.role, e.purpose, bool(e.result_ids), scenario.network_id
                ),
            )
        base = next((e for e in experiments if e.arm == BASE_ARM), None)
        if base is None:
            return tuple(entries.values())
        base_scenario = scenarios[base.scenario_id]
        realised = {e.arm for e in experiments}
        question = self.question
        for arm in question.effective_arms:
            if arm.label in realised or arm.topology_changes:
                continue
            predicted = scenario_id_for(
                base_scenario.network_id,
                base_scenario.demand_id,
                arm.interventions,
                question.context_tags,
            )
            entries.setdefault(
                predicted,
                NoteScenario(
                    predicted,
                    arm.label,
                    ExperimentRole.TREATMENT,
                    f"arm {arm.label!r} as asked, not simulated in this study",
                    simulated=False,
                    network_id=base_scenario.network_id,
                ),
            )
        return tuple(entries.values())

    def _base_network_id(self, networks: Mapping[str, Network]) -> str:
        """The study's own network: the one of its networks that was not derived from another.
        `network_ids` is in the order the study met its networks, so a derived network can come
        first: the position cannot say which one is the base."""
        for network_id in self.network_ids:
            network = networks.get(network_id)
            if network is not None and network.derived_from is None:
                return network_id
        raise ValueError("none of the study's networks is stored as a base network")

    def next_action(self) -> StudyAction:
        """What the study needs next (ADR-0041 §5), from its stage and its last phase. A resolved
        study needs nothing. The caller performs the action and applies its outcome."""
        if self.resolution is not None:
            return Finished()
        if self.stage is StudyStage.PARSING:  # an open study at parsing has no phase yet
            return ParseRequest(self.text)
        last = self.current_phase
        match self.stage:
            case StudyStage.PLANNING:
                return PlanPhase()
            case StudyStage.RUNNING:
                pending = last.pending_steps
                return RunStep(last.resolved(pending[0])) if pending else ConsultExpert()
            case StudyStage.CONSULTING_EXPERT:
                return OpenPhase() if last.round is not None else AskExpert()
            case StudyStage.CLOSING:
                return Close()
            case _:
                assert_never(self.stage)

    # -- transitions (ADR-0041 §4): each returns the next study and the events it produced ------

    @classmethod
    def open(
        cls, study_id: str, text: str, mode: Mode | None = None, *, max_rounds: int
    ) -> Transition:
        """The study of a request, with no phases, at `parsing`. `mode` is the user's choice, if
        any: it overrides the Input Parser's."""
        study = cls(study_id, StudyStage.PARSING, (), text, mode, max_rounds=max_rounds)
        return study, (StudyCreated(text, mode),)

    def accept_question(self, record: StepRecord, question: Question) -> Transition:
        """The Input Parser's `question` and its ok `parse` step: the question opens phase 0 and
        the study moves to `planning`; when the question is ambiguous the study stays at `parsing`,
        `awaiting_user`. The user's `mode`, when given, replaces the question's."""
        self._require(StudyStage.PARSING)
        if record.status is not StepStatus.OK:
            raise ValueError("a question comes with an ok parse step")
        if self.mode is not None:
            question = replace(question, mode=self.mode)
        if question.is_ambiguous:
            stage, resolution = StudyStage.PARSING, StudyResolution.AWAITING_USER
        else:
            stage, resolution = StudyStage.PLANNING, None
        study = replace(
            self, phases=(Phase(question),), parse=record, stage=stage, resolution=resolution
        )
        return study, (study._traced(record), PhaseStarted(0))

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
        results of the seeds it did not run again. The step applies its own effect on the phase
        (`apply`). A step that produces networks adds those the study does not have yet
        (`NetworksAdded`, before the step's trace); one that produces results records the runs of
        the scenario it names (`SimulationsRecorded`)."""
        self._require(StudyStage.RUNNING)
        step = self._next_plan_step(record)
        reused = reused_result_ids
        phase = step.apply(self.current_phase, record, reused)
        phase = replace(phase, steps=(*phase.steps, record))
        networks = record.produced_ids if step.produces == "network" else ()
        study, events = self._with_phase(phase)._with_networks(networks)
        events.append(self._traced(record))
        if step.produces == "result":
            (scenario_id,) = self.current_phase.named_ids(step, "scenario")
            events.append(
                SimulationsRecorded(
                    self.phase_index,
                    scenario_id,
                    new_result_ids=tuple(r for r in record.produced_ids if r not in reused),
                    reused_result_ids=tuple(r for r in record.produced_ids if r in reused),
                )
            )
        return study, tuple(events)

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
        one state; the study keeps the stage it failed in. At `parsing` the failed step is the
        `parse` step and the study has no phase to hold it."""
        self._require()
        if not self.phases:
            study = replace(self, parse=record, resolution=StudyResolution.FAILED)
            return study, (study._traced(record),)
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

    def _with_networks(self, network_ids: tuple[str, ...]) -> tuple[Study, list[StudyEvent]]:
        """This study with the networks among `network_ids` it has not used yet, added in order,
        and their `NetworksAdded`; no event when none is new."""
        merged = tuple(dict.fromkeys((*self.network_ids, *network_ids)))
        added = merged[len(self.network_ids) :]
        if not added:
            return self, []
        return replace(self, network_ids=merged), [NetworksAdded(added)]

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
            phase=max(self.phase_index, 0),
            tool=record.tool,
            status=record.status,
            produced_ids=record.produced_ids,
            usage=record.usage,
            error=record.error,
        )


def _pending_skipped(phase: Phase) -> tuple[StepRecord, ...]:
    """The plan steps of `phase` after the pending one that stopped it, as skipped steps."""
    return tuple(StepRecord(s.kind, StepStatus.SKIPPED) for s in phase.pending_steps[1:])


Transition = tuple[Study, tuple[StudyEvent, ...]]
"""The next study and the events its transition produced, in the order they happened."""
