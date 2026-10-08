"""The phases of a run: the tracer's events grouped by `PhaseStarted`, plus what only the
`Study` holds (`basis`, `forced_by_limit`, `reused`)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from resto.application.ports.tracing import (
    ExpertRoundHeld,
    PhaseStarted,
    PlanMade,
    StepTraced,
    TraceEvent,
)
from resto.domain.entities.study import Study
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.step_record import StepStatus


@dataclass(frozen=True, slots=True)
class ObservedPhase:
    steps: tuple[tuple[str, StepStatus], ...]
    arms: tuple[str, ...]
    reused: tuple[bool, ...]
    basis: Basis | None
    forced_by_limit: bool | None
    round: int | None


def observe(study: Study, events: Sequence[TraceEvent]) -> tuple[ObservedPhase, ...]:
    """One `ObservedPhase` per `PhaseStarted`. Events before the first one (`StudyCreated`) belong
    to no phase. Phase `k` of the events is read against `study.phases[k]`."""
    steps: list[list[tuple[str, StepStatus]]] = []
    arms: list[tuple[str, ...]] = []
    rounds: list[int | None] = []
    for event in events:
        if isinstance(event, PhaseStarted):
            steps.append([])
            arms.append(())
            rounds.append(None)
        elif not steps:
            continue
        elif isinstance(event, StepTraced):
            steps[-1].append((event.tool, event.status))
        elif isinstance(event, PlanMade):
            arms[-1] = event.plan.arms
        elif isinstance(event, ExpertRoundHeld):
            rounds[-1] = event.round
    observed: list[ObservedPhase] = []
    for k, phase_steps in enumerate(steps):
        phase = study.phases[k] if k < len(study.phases) else None
        held = phase.round if phase is not None else None
        observed.append(
            ObservedPhase(
                steps=tuple(phase_steps),
                arms=arms[k],
                reused=tuple(e.reused for e in phase.experiments) if phase else (),
                basis=held.answer.basis if held else None,
                forced_by_limit=held.forced_by_limit if held else None,
                round=rounds[k],
            )
        )
    return tuple(observed)
