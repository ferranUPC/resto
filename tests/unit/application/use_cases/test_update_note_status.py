"""`UpdateNoteStatus` (E4.6; ADR-0041 §9): the note decides (`tests/unit/domain/test_expert_note.py`
holds the rule's cases); the use case delegates, stores the settled note and returns its events."""

from __future__ import annotations

from resto.adapters.persistence.memory import InMemoryNoteRepository
from resto.application.use_cases.update_note_status import UpdateNoteStatus
from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.events import NoteStatusChanged
from resto.domain.value_objects.answer_value import Measure, Quantity
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.kpis import Kpis

NETWORK = "abc123"
SCENARIO = "s1"


def _note() -> ExpertNote:
    return ExpertNote(
        note_id="n1",
        network_id=NETWORK,
        study_id="st1",
        text="closing the lane roughly doubles mean delay",
        provenance=Provenance.SIMULATION,
        basis=Basis.EXTRAPOLATED,
        scenario_id=SCENARIO,
        values=(Quantity(measure=Measure.MEAN_DELAY, value=40.0),),
    )


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


def _stored_status(notes: InMemoryNoteRepository) -> NoteStatus:
    return notes.search("delay", NETWORK, {})[0][0].status


def test_a_settled_note_is_stored_and_its_event_returned() -> None:
    notes = InMemoryNoteRepository()
    notes.store(_note())

    events = UpdateNoteStatus(notes).execute(_note(), _result(mean_delay=90.0))

    assert events == (NoteStatusChanged("n1", "r1", NoteStatus.REFUTED),)
    assert _stored_status(notes) is NoteStatus.REFUTED


def test_a_note_the_result_does_not_settle_is_not_stored() -> None:
    notes = InMemoryNoteRepository()
    notes.store(_note())

    events = UpdateNoteStatus(notes).execute(_note(), _result(scenario_id="other"))

    assert events == ()
    assert _stored_status(notes) is NoteStatus.UNVERIFIED
