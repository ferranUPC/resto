"""Domain events: what a transition of an aggregate produced (ADR-0041 §10).

A transition returns its next value and the events it produced; the use case stores the value, then
publishes the events. Event types import value objects only, never the entities that return them.

The events carry no `study_id`: whoever publishes a study's events passes its id along, as
`Tracer.emit` takes it. Most of them are also trace events and keep the names and fields the trace
has always had (ADR-0041 Consequences), so a trace reads the same as before they moved here.
"""

from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.note_status import NoteStatus
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.step_record import StepError, StepStatus, Usage
from resto.domain.value_objects.study_plan import StudyPlan


@dataclass(frozen=True, slots=True)
class StudyCreated:
    """A study opened on a request: its `text` and the `mode` the user chose, if any."""

    text: str
    mode: Mode | None


@dataclass(frozen=True, slots=True)
class PhaseStarted:
    phase: int


@dataclass(frozen=True, slots=True)
class PlanMade:
    """The valid plan of a phase. A rejected plan produces no `PlanMade`, only its failed step."""

    phase: int
    plan: StudyPlan


@dataclass(frozen=True, slots=True)
class StepTraced:
    """A step was recorded in `phase`: ok, failed or needing the user. The accepted plan's own
    step is told by `PlanMade` instead, and skipped steps produce no event."""

    phase: int
    tool: str
    status: StepStatus
    produced_ids: tuple[str, ...]
    usage: Usage
    error: StepError | None


@dataclass(frozen=True, slots=True)
class SimulationsRecorded:
    """An ok `run_simulation` step of `phase` recorded the results of `scenario_id`, in seed
    order: `new_result_ids` were simulated by the step, `reused_result_ids` were stored before it.
    Only new ok results verify notes (ADR-0026)."""

    phase: int
    scenario_id: str
    new_result_ids: tuple[str, ...]
    reused_result_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class NetworksAdded:
    network_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExpertRoundHeld:
    """The Expert round of `phase` was recorded; `round` counts from 1."""

    phase: int
    round: int


@dataclass(frozen=True, slots=True)
class NotesWritten:
    note_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportComposed:
    pass


@dataclass(frozen=True, slots=True)
class NoteStatusChanged:
    """`result_id` settled the note `note_id` as `status` (`ExpertNote.verify`)."""

    note_id: str
    result_id: str
    status: NoteStatus


StudyEvent = (
    StudyCreated
    | PhaseStarted
    | PlanMade
    | StepTraced
    | SimulationsRecorded
    | NetworksAdded
    | ExpertRoundHeld
    | NotesWritten
    | ReportComposed
)
"""What a transition of `Study` produces."""

DomainEvent = StudyEvent | NoteStatusChanged
