"""One phase of a study (ADR-0023 §4): a question, its plan, the steps recorded and the Expert's
round. `Study.phases` holds them; each transition replaces the current one."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.outcomes import NeedsUser
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.study_plan import FromStep, PlanStep, Produces, StudyPlan


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
