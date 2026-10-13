"""Step executors (ADR-0042 §7), one per `PlanStep` variant, registered by step type in the
composition root. A step comes resolved, so `step.refs()` holds every id it names. A failure raises
`StepFailed` or `StepNeedsUser` (`failures`), which `RunStudy` records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

from resto.application.run_study.spend import StudySpend
from resto.application.run_study.step_data import data
from resto.domain.entities.study import Study, Transition
from resto.domain.value_objects.step_record import StepRecord, StepStatus, Usage
from resto.domain.value_objects.study_plan import PlanStep

S_contra = TypeVar("S_contra", contravariant=True)


@dataclass(frozen=True, slots=True)
class StepContext:
    study: Study
    spend: StudySpend

    def record(
        self,
        step: PlanStep,
        produced_ids: tuple[str, ...],
        usage: Usage | None = None,
        reused: tuple[str, ...] = (),
    ) -> Transition:
        """The study's transition with `step` recorded ok, and the stored results it reused."""
        record = StepRecord(
            step.kind, StepStatus.OK, data(step), produced_ids, usage=usage or Usage()
        )
        return self.study.record_step(record, reused_result_ids=reused)


class StepExecutor(Protocol[S_contra]):
    def execute(self, step: S_contra, ctx: StepContext) -> Transition: ...
