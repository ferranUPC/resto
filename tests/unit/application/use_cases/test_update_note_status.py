"""`update_note_status` (E4.6; ADR-0011): deterministic confirm/refute, no LLM — only network-wide
`Quantity` claims are checkable against a single `SimulationResult`'s `Kpis` today."""

from __future__ import annotations

from resto.adapters.persistence.memory import InMemoryNoteRepository
from resto.application.use_cases.update_note_status import update_note_status
from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.value_objects.answer_value import Edges, Measure, Quantity
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.kpis import Kpis

NETWORK = "abc123"
SCENARIO = "s1"


def _note(**overrides: object) -> ExpertNote:
    kwargs: dict[str, object] = {
        "note_id": "n1",
        "network_id": NETWORK,
        "study_id": "st1",
        "text": "closing the lane roughly doubles mean delay",
        "provenance": Provenance.SIMULATION,
        "basis": Basis.EXTRAPOLATED,
        "scenario_id": SCENARIO,
        "values": (Quantity(measure=Measure.MEAN_DELAY, value=40.0),),
    }
    kwargs.update(overrides)
    return ExpertNote(**kwargs)  # type: ignore[arg-type]


def _result(*, scenario_id: str = SCENARIO, mean_delay: float = 40.0) -> SimulationResult:
    return SimulationResult(
        result_id="r1",
        scenario_id=scenario_id,
        seed=1,
        mode=RunMode.BATCH,
        status=RunStatus.OK,
        content_hash="c1",
        kpis=Kpis(
            mean_delay=mean_delay, mean_travel_time=100.0, teleports=0, departed=10, arrived=10
        ),
    )


def test_a_matching_measurement_confirms_the_note() -> None:
    notes = InMemoryNoteRepository()
    notes.store(_note())
    status = update_note_status(_note(), _result(mean_delay=41.0), notes=notes)
    assert status is NoteStatus.CONFIRMED
    assert notes.search("delay", NETWORK, {})[0][0].status is NoteStatus.CONFIRMED


def test_a_contradicting_measurement_refutes_the_note() -> None:
    notes = InMemoryNoteRepository()
    notes.store(_note())
    status = update_note_status(_note(), _result(mean_delay=90.0), notes=notes)
    assert status is NoteStatus.REFUTED


def test_a_result_of_a_different_scenario_is_ignored() -> None:
    status = update_note_status(
        _note(), _result(scenario_id="other"), notes=InMemoryNoteRepository()
    )
    assert status is None


def test_an_already_resolved_note_is_left_alone() -> None:
    status = update_note_status(
        _note(status=NoteStatus.CONFIRMED), _result(), notes=InMemoryNoteRepository()
    )
    assert status is None


def test_a_note_with_no_checkable_claim_stays_unverified() -> None:
    status = update_note_status(
        _note(values=(Edges(edge_ids=("E12",)),)), _result(), notes=InMemoryNoteRepository()
    )
    assert status is None


def test_a_per_edge_quantity_claim_is_not_checked_by_this_first_version() -> None:
    claim = Quantity(measure=Measure.TRAVEL_TIME, value=20.0, edge_id="E12")
    status = update_note_status(_note(values=(claim,)), _result(), notes=InMemoryNoteRepository())
    assert status is None


def test_a_result_without_kpis_is_ignored() -> None:
    failed = SimulationResult(
        result_id="r2", scenario_id=SCENARIO, seed=1, mode=RunMode.BATCH,
        status=RunStatus.FAILED, content_hash="c2", error="sumo crashed",
    )
    status = update_note_status(_note(), failed, notes=InMemoryNoteRepository())
    assert status is None
