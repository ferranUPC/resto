"""`write_note` promotion (E4.6; ADR-0001, ADR-0011): a note is accepted only if every evidence ref
resolves to the round's own ledger; `provenance`/`status`/`note_id` are always set by this code,
never by the agent."""

from __future__ import annotations

import pytest

from resto.adapters.persistence.memory import InMemoryNoteRepository
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.tools.expert import EvidenceLedger
from resto.application.use_cases.write_note import (
    ExpertNoteRejected,
    NoteWriterRunFailed,
    write_note,
)
from resto.domain.entities.expert_note import NoteStatus, Provenance
from resto.domain.value_objects.answer_value import Measure, Quantity
from resto.domain.value_objects.drafts import ExpertNoteDraft
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind
from resto.domain.value_objects.step_record import Usage

NETWORK = "abc123"
STUDY = "st-1"


def _draft(
    *, basis: Basis = Basis.OBSERVED, ref: str = "q1", values: tuple = ()
) -> ExpertNoteDraft:
    return ExpertNoteDraft(
        text="E12 saturates in the last 20 minutes of the peak",
        basis=basis,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref=ref),) if basis is Basis.OBSERVED else (),
        context_tags=frozenset({"peak"}),
        values=values,
    )


def _run(draft: ExpertNoteDraft | None, stop: StopReason = StopReason.OUTPUT) -> AgentRun:
    return AgentRun(output=draft, tool_calls=(), usage=Usage(), stop_reason=stop)


def _ledger() -> EvidenceLedger:
    ledger = EvidenceLedger()
    ledger.record("query_edgedata", {"result_id": "r1"}, {"E12": {"time_loss": 12.0}})
    return ledger


def test_a_resolvable_note_about_an_experiment_is_simulation_provenance() -> None:
    notes = InMemoryNoteRepository()
    note = write_note(
        _run(_draft()), _ledger(), network_id=NETWORK, study_id=STUDY, scenario_id="s1",
        notes=notes,
    )
    assert note.provenance is Provenance.SIMULATION
    assert note.scenario_id == "s1"
    assert note.status is NoteStatus.UNVERIFIED
    assert notes.search("saturates", NETWORK, {})[0][0].note_id == note.note_id


def test_a_note_written_without_an_experiment_is_opinion_provenance() -> None:
    notes = InMemoryNoteRepository()
    note = write_note(
        _run(_draft()), _ledger(), network_id=NETWORK, study_id=STUDY, scenario_id=None,
        notes=notes,
    )
    assert note.provenance is Provenance.OPINION
    assert note.scenario_id is None


def test_every_note_gets_a_fresh_id() -> None:
    notes = InMemoryNoteRepository()
    first = write_note(
        _run(_draft()), _ledger(), network_id=NETWORK, study_id=STUDY, scenario_id="s1",
        notes=notes,
    )
    second = write_note(
        _run(_draft()), _ledger(), network_id=NETWORK, study_id=STUDY, scenario_id="s1",
        notes=notes,
    )
    assert first.note_id != second.note_id


def test_a_typed_claim_passes_through_onto_the_stored_note() -> None:
    notes = InMemoryNoteRepository()
    claim = Quantity(measure=Measure.MEAN_DELAY, value=42.0)
    note = write_note(
        _run(_draft(values=(claim,))), _ledger(), network_id=NETWORK, study_id=STUDY,
        scenario_id="s1", notes=notes,
    )
    assert note.values == (claim,)


def test_a_run_that_stopped_without_a_draft_fails() -> None:
    with pytest.raises(NoteWriterRunFailed):
        write_note(
            _run(None, stop=StopReason.BUDGET), _ledger(), network_id=NETWORK, study_id=STUDY,
            scenario_id="s1", notes=InMemoryNoteRepository(),
        )


def test_a_query_ref_not_in_the_ledger_is_rejected() -> None:
    with pytest.raises(ExpertNoteRejected, match="q9"):
        write_note(
            _run(_draft(ref="q9")), _ledger(), network_id=NETWORK, study_id=STUDY,
            scenario_id="s1", notes=InMemoryNoteRepository(),
        )


def test_an_artifact_ref_not_returned_by_a_result_call_is_rejected() -> None:
    draft = ExpertNoteDraft(
        text="the closure reroutes traffic onto B2C2",
        basis=Basis.OBSERVED,
        evidence=(Evidence(kind=EvidenceKind.ARTIFACT, ref="missing.xml"),),
    )
    with pytest.raises(ExpertNoteRejected, match="missing.xml"):
        write_note(
            _run(draft), _ledger(), network_id=NETWORK, study_id=STUDY, scenario_id="s1",
            notes=InMemoryNoteRepository(),
        )
