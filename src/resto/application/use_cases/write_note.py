"""Network Expert note-writing promotion: an already-run `AgentRun[ExpertNoteDrafts]` -> the study's
`ExpertNote`s (DoD §2.2, §2.4; ADR-0001, ADR-0011, ADR-0026).

Like `ask_expert`/`build_scenario`, this takes the agent's run as a finished fact: writing the notes
is `adapters/llm/agents/expert.py::run_expert_note`, which must be given the SAME `EvidenceLedger`
the final round was promoted with — the note-writing call makes no tool calls of its own, so every
evidence ref it cites must already be there.

Promotion order (ADR-0001), all drafts checked before any is stored:
  1. syntactic - the run stopped with `ExpertNoteDrafts` (0 to MAX_NOTES_PER_STUDY; each draft's
                 own invariants already ran: text required, an observed note has evidence).
  2. semantic  - every evidence ref resolves to a tool call in the ledger (query) or to an artifact
                 a result tool call returned (artifact); every `scenario_ref` is in the task's
                 allow-list; a note about a scenario that was not simulated is not `observed`.
  3. construct - `note_id` (UUID, ADR-0002), `scenario_id = scenario_ref`, `provenance`
                 (`SIMULATION` only when that scenario has ok results in the study, `OPINION`
                 otherwise — a prediction keeps its predicted `scenario_id`), `status = UNVERIFIED`.
  4. persist   - `notes.store(note)` for each.
Attaching the notes to a `Study` is `run_study`'s job (E5.10), not this module's.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.repositories import NoteRepository
from resto.application.tools.expert import EvidenceLedger
from resto.domain.entities.expert_note import ExpertNote, Provenance
from resto.domain.services.ids import new_id
from resto.domain.value_objects.drafts import ExpertNoteDraft, ExpertNoteDrafts
from resto.domain.value_objects.expert_answer import Basis, EvidenceKind
from resto.domain.value_objects.tasks import NoteTask


class NoteWriterRunFailed(RuntimeError):
    """The note writer stopped (budget/error) without `ExpertNoteDrafts`."""


class ExpertNoteRejected(ValueError):
    """The note writer returned well-formed drafts, one of which breaks a semantic rule."""


def write_note(
    run: AgentRun[ExpertNoteDrafts],
    ledger: EvidenceLedger,
    task: NoteTask,
    *,
    network_id: str,
    study_id: str,
    notes: NoteRepository,
) -> tuple[ExpertNote, ...]:
    if run.stop_reason is not StopReason.OUTPUT or run.output is None:
        raise NoteWriterRunFailed(f"note writer stopped on {run.stop_reason} without drafts")
    drafts = run.output.notes
    for draft in drafts:
        _check_evidence(draft, ledger)
        _check_scenario(draft, task)
    written = tuple(_construct(d, task, network_id=network_id, study_id=study_id) for d in drafts)
    for note in written:
        notes.store(note)
    return written


def _construct(
    draft: ExpertNoteDraft, task: NoteTask, *, network_id: str, study_id: str
) -> ExpertNote:
    scenario = task.scenario(draft.scenario_ref) if draft.scenario_ref is not None else None
    simulated = scenario is not None and scenario.simulated
    return ExpertNote(
        note_id=new_id(),
        network_id=network_id,
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
        raise ExpertNoteRejected(
            f"scenario_ref {draft.scenario_ref!r} is not in the allow-list of this study"
        )
    if not scenario.simulated and draft.basis is Basis.OBSERVED:
        raise ExpertNoteRejected(
            f"scenario {draft.scenario_ref!r} was not simulated: a note about it cannot be observed"
        )


def _check_evidence(draft: ExpertNoteDraft, ledger: EvidenceLedger) -> None:
    artifact_ids = ledger.artifact_ids()
    for evidence in draft.evidence:
        if evidence.kind is EvidenceKind.QUERY and ledger.get(evidence.ref) is None:
            raise ExpertNoteRejected(
                f"evidence ref {evidence.ref!r} does not match any tool call of this run"
            )
        if evidence.kind is EvidenceKind.ARTIFACT and evidence.ref not in artifact_ids:
            raise ExpertNoteRejected(
                f"artifact {evidence.ref!r} was not returned by any result tool call of this run"
            )
