"""Network Expert note-writing promotion: an already-run `AgentRun[ExpertNoteDrafts]` -> the study's
`ExpertNote`s (DoD §2.2, §2.4; ADR-0001, ADR-0011, ADR-0026, ADR-0042 §5, §10).

Writing the notes is `adapters/llm/agents/expert.py::run_expert_note`. That call has no tools and
sees only the final round's answer, so a note may cite only evidence of that answer.

Promotion order (ADR-0001), all drafts checked before any note is built:
  1. syntactic - the run stopped with `ExpertNoteDrafts` (0 to MAX_NOTES_PER_STUDY; each draft's
                 own invariants already ran: text required, an observed note has evidence).
  2. semantic  - every evidence ref is a ref of the final answer's evidence
                 (`task.round.answer.evidence`); every `scenario_ref` is in the task's allow-list;
                 a note about a scenario that was not simulated is not `observed`.
  3. construct - `note_id` (UUID, ADR-0002), `scenario_id = scenario_ref`, `network_id` = the
                 scenario's network (the base scenario's for a prediction) or, with no scenario,
                 the study's base network (ADR-0032), `provenance`
                 (`SIMULATION` only when that scenario has ok results in the study, `OPINION`
                 otherwise; a prediction keeps its predicted `scenario_id`), `status = UNVERIFIED`.
Storing the notes and attaching their ids to the `Study` is the study flow's job
(`application/run_study/`).
"""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.llm import AgentRun
from resto.application.promotion import DraftRejected, require_draft
from resto.domain.entities.expert_note import ExpertNote, Provenance
from resto.domain.services.ids import new_id
from resto.domain.value_objects.drafts import ExpertNoteDraft, ExpertNoteDrafts
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.tasks import NoteTask


@dataclass(frozen=True, slots=True)
class NoteContext:
    """What the note writer was given (`task`) and the study its notes belong to."""

    task: NoteTask
    study_id: str


@dataclass(frozen=True, slots=True)
class NotePromoter:
    def promote(
        self, run: AgentRun[ExpertNoteDrafts], context: NoteContext
    ) -> tuple[ExpertNote, ...]:
        task = context.task
        drafts = require_draft(run, "note_writer").notes
        cited = {e.ref for e in task.round.answer.evidence}
        for draft in drafts:
            _check_evidence(draft, cited)
            _check_scenario(draft, task)
        return tuple(_construct(d, task, study_id=context.study_id) for d in drafts)


def _check_evidence(draft: ExpertNoteDraft, cited: set[str]) -> None:
    for item in draft.evidence:
        if item.ref not in cited:
            raise DraftRejected(
                f"evidence ref {item.ref!r} is not evidence of the final Expert answer"
            )


def _construct(draft: ExpertNoteDraft, task: NoteTask, *, study_id: str) -> ExpertNote:
    scenario = task.scenario(draft.scenario_ref) if draft.scenario_ref is not None else None
    simulated = scenario is not None and scenario.simulated
    return ExpertNote(
        note_id=new_id(),
        network_id=scenario.network_id if scenario is not None else task.base_network_id,
        study_id=study_id,
        text=draft.text,
        provenance=Provenance.SIMULATION if simulated else Provenance.OPINION,
        basis=draft.basis,
        scenario_id=draft.scenario_ref,
        context_tags=draft.context_tags,
        values=draft.values,
    )


def _check_scenario(draft: ExpertNoteDraft, task: NoteTask) -> None:
    if draft.scenario_ref is None:
        return
    scenario = task.scenario(draft.scenario_ref)
    if scenario is None:
        raise DraftRejected(
            f"scenario_ref {draft.scenario_ref!r} is not in the allow-list of this study"
        )
    if not scenario.simulated and draft.basis is Basis.OBSERVED:
        raise DraftRejected(
            f"scenario {draft.scenario_ref!r} was not simulated: a note about it cannot be observed"
        )
