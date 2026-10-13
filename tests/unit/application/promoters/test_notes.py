"""`NotePromoter` (E4.6, E4.11; ADR-0001, ADR-0011, ADR-0026, ADR-0042 §10): notes are accepted only
if every evidence ref is evidence of the final Expert answer and every scenario ref is in the
study's allow-list; `provenance`/`status`/`note_id` are always set by this code, never by the
agent. The promoter stores nothing: the stored notes are checked at the `World` seam."""

from __future__ import annotations

from dataclasses import replace

import pytest

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promoters.notes import NoteContext, NotePromoter
from resto.application.promotion import DraftRejected, RunWithoutDraft
from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
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
FINAL_ANSWER = replace(
    expert_answer(),
    evidence=(
        Evidence(kind=EvidenceKind.QUERY, ref="q1", excerpt="E12 0.91"),
        Evidence(kind=EvidenceKind.ARTIFACT, ref="/runs/r1/edgedata.xml"),
    ),
)
TASK = NoteTask(
    round=ExpertRound(question="what if lane 0 of E12 closes?", answer=FINAL_ANSWER),
    base_network_id=NETWORK,
    scenarios=(
        NoteScenario(
            "s-base",
            "base",
            ExperimentRole.BASELINE,
            "as it is",
            simulated=True,
            network_id="abc123",
        ),
        NoteScenario(
            "s-pred",
            "treatment",
            ExperimentRole.TREATMENT,
            "closure",
            simulated=False,
            network_id="abc123",
        ),
        NoteScenario(
            "s-derived",
            "edge",
            ExperimentRole.TREATMENT,
            "new edge",
            simulated=True,
            network_id="derived-1",
        ),
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


def _promote(run: AgentRun) -> tuple[ExpertNote, ...]:
    return NotePromoter().promote(run, NoteContext(task=TASK, study_id=STUDY))


def test_a_note_about_a_simulated_scenario_is_simulation_provenance() -> None:
    (note,) = _promote(_run(_draft()))
    assert note.provenance is Provenance.SIMULATION
    assert note.scenario_id == "s-base"
    assert note.status is NoteStatus.UNVERIFIED
    assert note.study_id == STUDY


def test_a_prediction_is_opinion_and_keeps_its_predicted_scenario() -> None:
    claim = Quantity(measure=Measure.MEAN_DELAY, value=95.0)
    (note,) = _promote(
        _run(_draft(basis=Basis.EXTRAPOLATED, scenario_ref="s-pred", values=(claim,)))
    )
    assert note.provenance is Provenance.OPINION
    assert note.scenario_id == "s-pred"
    assert note.values == (claim,)


def test_a_note_about_the_network_in_general_is_opinion_without_a_scenario() -> None:
    (note,) = _promote(_run(_draft(basis=Basis.INFERRED, scenario_ref=None)))
    assert note.provenance is Provenance.OPINION
    assert note.scenario_id is None


def test_several_notes_each_get_a_fresh_id() -> None:
    written = _promote(_run(_draft(), _draft(basis=Basis.EXTRAPOLATED, scenario_ref="s-pred")))
    assert len({n.note_id for n in written}) == 2


def test_zero_notes_is_a_valid_outcome() -> None:
    assert _promote(_run()) == ()


def test_at_most_three_notes_per_study() -> None:
    with pytest.raises(ValueError, match="at most 3"):
        ExpertNoteDrafts(notes=(_draft(),) * 4)


def test_a_scenario_ref_outside_the_allow_list_is_rejected() -> None:
    with pytest.raises(DraftRejected, match="s-invented"):
        _promote(_run(_draft(scenario_ref="s-invented")))


def test_a_note_about_an_unsimulated_scenario_cannot_be_observed() -> None:
    with pytest.raises(DraftRejected, match="not simulated"):
        _promote(_run(_draft(scenario_ref="s-pred")))


def test_one_bad_draft_rejects_the_whole_run() -> None:
    with pytest.raises(DraftRejected):
        _promote(_run(_draft(), _draft(ref="q9")))


def test_a_run_that_stopped_without_drafts_fails() -> None:
    with pytest.raises(RunWithoutDraft):
        _promote(_run(stop=StopReason.BUDGET))


def test_a_query_ref_the_final_answer_does_not_hold_is_rejected() -> None:
    with pytest.raises(DraftRejected, match="q9"):
        _promote(_run(_draft(ref="q9")))


def test_a_tool_call_of_the_final_round_that_the_answer_did_not_cite_is_rejected() -> None:
    # "q2" is a tool call the Expert made in its final round (it is in the round's ledger), but the
    # answer does not cite it: the note writer never saw it, so no note may cite it (ADR-0042 §10).
    with pytest.raises(DraftRejected, match="q2"):
        _promote(_run(_draft(ref="q2")))


def test_an_artifact_the_final_answer_cites_is_accepted() -> None:
    draft = ExpertNoteDraft(
        text="the closure reroutes traffic onto B2C2",
        basis=Basis.OBSERVED,
        evidence=(Evidence(kind=EvidenceKind.ARTIFACT, ref="/runs/r1/edgedata.xml"),),
        scenario_ref="s-base",
    )
    (note,) = _promote(_run(draft))
    assert note.provenance is Provenance.SIMULATION


def test_an_artifact_ref_the_final_answer_does_not_hold_is_rejected() -> None:
    draft = ExpertNoteDraft(
        text="the closure reroutes traffic onto B2C2",
        basis=Basis.OBSERVED,
        evidence=(Evidence(kind=EvidenceKind.ARTIFACT, ref="missing.xml"),),
        scenario_ref="s-base",
    )
    with pytest.raises(DraftRejected, match="missing.xml"):
        _promote(_run(draft))


def test_a_note_takes_the_network_of_its_scenario() -> None:
    (note,) = _promote(_run(_draft(scenario_ref="s-derived")))
    assert note.network_id == "derived-1"


def test_a_note_without_a_scenario_takes_the_base_network() -> None:
    (note,) = _promote(_run(_draft(basis=Basis.INFERRED, scenario_ref=None)))
    assert note.network_id == NETWORK


def test_a_prediction_takes_the_network_its_allow_list_entry_names() -> None:
    (note,) = _promote(_run(_draft(basis=Basis.EXTRAPOLATED, scenario_ref="s-pred")))
    assert note.network_id == NETWORK


def test_the_note_draft_has_no_network_field() -> None:
    assert not any("network" in f for f in ExpertNoteDraft.__dataclass_fields__)
