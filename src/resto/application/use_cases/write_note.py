"""Network Expert note-writing promotion: an already-run `AgentRun[ExpertNoteDraft]` -> an
`ExpertNote` (DoD §2.2, §2.4; ADR-0001, ADR-0011).

Like `ask_expert`/`build_scenario`, this takes the agent's run as a finished fact: writing the note
is `adapters/llm/agents/expert.py::run_expert_note`, which must be given the SAME `EvidenceLedger`
the round it is writing about was promoted with — the note-writing call makes no tool calls of its
own, so every evidence ref it cites must already be there.

Promotion order (ADR-0001):
  1. syntactic - the run stopped with an `ExpertNoteDraft` (its own invariants already ran: text
                 required, an observed note has evidence).
  2. semantic  - every evidence ref resolves to a tool call in the ledger (query) or to an artifact
                 a result tool call returned (artifact).
  3. construct - `note_id` (UUID, ADR-0002), `provenance` (`SIMULATION` when `scenario_id` is
                 given, `OPINION` otherwise), `status = UNVERIFIED`.
  4. persist   - `notes.store(note)`.
Attaching the note to a `Study` is `run_study`'s job (E5), not this module's.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.repositories import NoteRepository
from resto.application.tools.expert import EvidenceLedger
from resto.domain.entities.expert_note import ExpertNote, Provenance
from resto.domain.services.ids import new_id
from resto.domain.value_objects.drafts import ExpertNoteDraft
from resto.domain.value_objects.expert_answer import EvidenceKind


class NoteWriterRunFailed(RuntimeError):
    """The note writer stopped (budget/error) without an `ExpertNoteDraft`."""


class ExpertNoteRejected(ValueError):
    """The note writer returned a well-formed draft that breaks a semantic rule."""


def write_note(
    run: AgentRun[ExpertNoteDraft],
    ledger: EvidenceLedger,
    *,
    network_id: str,
    study_id: str,
    scenario_id: str | None,
    notes: NoteRepository,
) -> ExpertNote:
    if run.stop_reason is not StopReason.OUTPUT or run.output is None:
        raise NoteWriterRunFailed(f"note writer stopped on {run.stop_reason} without a draft")
    draft = run.output
    _check_evidence(draft, ledger)
    note = ExpertNote(
        note_id=new_id(),
        network_id=network_id,
        study_id=study_id,
        text=draft.text,
        provenance=Provenance.SIMULATION if scenario_id is not None else Provenance.OPINION,
        basis=draft.basis,
        scenario_id=scenario_id,
        context_tags=draft.context_tags,
        values=draft.values,
    )
    notes.store(note)
    return note


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
