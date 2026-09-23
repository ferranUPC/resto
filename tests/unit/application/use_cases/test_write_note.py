"""`write_note` promotion (E4.6, E4.11; ADR-0001, ADR-0011, ADR-0026): notes are accepted only if
every evidence ref resolves to the round's own ledger and every scenario ref is in the study's
allow-list; `provenance`/`status`/`note_id` are always set by this code, never by the agent."""

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
from resto.domain.value_objects.drafts import ExpertNoteDraft, ExpertNoteDrafts
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import NoteScenario, NoteTask
from tests.unit.domain._samples import expert_answer

NETWORK = "abc123"
STUDY = "st-1"
TASK = NoteTask(
    round=ExpertRound(question="what if lane 0 of E12 closes?", answer=expert_answer()),
    scenarios=(
        NoteScenario("s-base", "base", ExperimentRole.BASELINE, "as it is", simulated=True),
        NoteScenario("s-pred", "treatment", ExperimentRole.TREATMENT, "closure", simulated=False),
    ),
)


def _draft(
    *,
    basis: Basis = Basis.OBSERVED,
    ref: str = "q1",
    values: tuple = (),
    scenario_ref: str | None = "s-base",
) -> ExpertNoteDraft:
    return ExpertNoteDraft(
        text="E12 saturates in the last 20 minutes of the peak",
        basis=basis,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref=ref),) if basis is Basis.OBSERVED else (),
        context_tags=frozenset({"peak"}),
        values=values,
        scenario_ref=scenario_ref,
    )


def _run(*drafts: ExpertNoteDraft, stop: StopReason = StopReason.OUTPUT) -> AgentRun:
    output = ExpertNoteDrafts(notes=drafts) if stop is StopReason.OUTPUT else None
    return AgentRun(output=output, tool_calls=(), usage=Usage(), stop_reason=stop)


def _ledger() -> EvidenceLedger:
    ledger = EvidenceLedger()
    ledger.record("query_edgedata", {"result_id": "r1"}, {"E12": {"time_loss": 12.0}})
    return ledger


def _write(run: AgentRun, notes: InMemoryNoteRepository | None = None):  # noqa: ANN202
    return write_note(
        run,
        _ledger(),
        TASK,
        network_id=NETWORK,
        study_id=STUDY,
        notes=notes if notes is not None else InMemoryNoteRepository(),
    )


def test_a_note_about_a_simulated_scenario_is_simulation_provenance() -> None:
    notes = InMemoryNoteRepository()
    (note,) = _write(_run(_draft()), notes)
    assert note.provenance is Provenance.SIMULATION
    assert note.scenario_id == "s-base"
    assert note.status is NoteStatus.UNVERIFIED
    assert notes.search("saturates", NETWORK, {})[0][0].note_id == note.note_id


def test_a_prediction_is_opinion_and_keeps_its_predicted_scenario() -> None:
    claim = Quantity(measure=Measure.MEAN_DELAY, value=95.0)
    (note,) = _write(
        _run(_draft(basis=Basis.EXTRAPOLATED, scenario_ref="s-pred", values=(claim,)))
    )
    assert note.provenance is Provenance.OPINION
    assert note.scenario_id == "s-pred"
    assert note.values == (claim,)


def test_a_note_about_the_network_in_general_is_opinion_without_a_scenario() -> None:
    (note,) = _write(_run(_draft(basis=Basis.INFERRED, scenario_ref=None)))
    assert note.provenance is Provenance.OPINION
    assert note.scenario_id is None


def test_several_notes_are_stored_each_with_a_fresh_id() -> None:
    notes = InMemoryNoteRepository()
    written = _write(
        _run(_draft(), _draft(basis=Basis.EXTRAPOLATED, scenario_ref="s-pred")), notes
    )
    assert len({n.note_id for n in written}) == 2
    assert {n.note_id for n, _ in notes.search("saturates", NETWORK, {})} == {
        n.note_id for n in written
    }


def test_zero_notes_is_a_valid_outcome() -> None:
    assert _write(_run()) == ()


def test_at_most_three_notes_per_study() -> None:
    with pytest.raises(ValueError, match="at most 3"):
        ExpertNoteDrafts(notes=(_draft(),) * 4)


def test_a_scenario_ref_outside_the_allow_list_is_rejected() -> None:
    with pytest.raises(ExpertNoteRejected, match="s-invented"):
        _write(_run(_draft(scenario_ref="s-invented")))


def test_a_note_about_an_unsimulated_scenario_cannot_be_observed() -> None:
    with pytest.raises(ExpertNoteRejected, match="not simulated"):
        _write(_run(_draft(scenario_ref="s-pred")))


def test_one_bad_draft_rejects_the_run_and_stores_nothing() -> None:
    notes = InMemoryNoteRepository()
    with pytest.raises(ExpertNoteRejected):
        _write(_run(_draft(), _draft(ref="q9")), notes)
    assert notes.search("saturates", NETWORK, {}) == []


def test_a_run_that_stopped_without_drafts_fails() -> None:
    with pytest.raises(NoteWriterRunFailed):
        _write(_run(stop=StopReason.BUDGET))


def test_a_query_ref_not_in_the_ledger_is_rejected() -> None:
    with pytest.raises(ExpertNoteRejected, match="q9"):
        _write(_run(_draft(ref="q9")))


def test_an_artifact_ref_not_returned_by_a_result_call_is_rejected() -> None:
    draft = ExpertNoteDraft(
        text="the closure reroutes traffic onto B2C2",
        basis=Basis.OBSERVED,
        evidence=(Evidence(kind=EvidenceKind.ARTIFACT, ref="missing.xml"),),
        scenario_ref="s-base",
    )
    with pytest.raises(ExpertNoteRejected, match="missing.xml"):
        _write(_run(draft))
