"""`ExpertNote.verify` (E4.6; ADR-0011, ADR-0024, ADR-0026, ADR-0041 §9): a later
`SimulationResult` confirms or refutes a note, deterministically. Only network-wide `Quantity`
claims are checkable against one result's `Kpis` today."""

from __future__ import annotations

import pytest

from resto.domain.entities.expert_note import ExpertNote, NoteStatus, Provenance
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.events import NoteStatusChanged
from resto.domain.value_objects.answer_value import (
    AnswerValue,
    BottleneckCause,
    BottleneckCauses,
    EdgeCause,
    Edges,
    Measure,
    Quantity,
)
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.kpis import Kpis

SCENARIO = "s1"


def _note(**overrides: object) -> ExpertNote:
    kwargs: dict[str, object] = {
        "note_id": "n1",
        "network_id": "abc123",
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
    verified, events = _note().verify(_result(mean_delay=41.0))

    assert verified.status is NoteStatus.CONFIRMED
    assert events == (NoteStatusChanged("n1", "r1", NoteStatus.CONFIRMED),)


def test_a_contradicting_measurement_refutes_the_note() -> None:
    verified, events = _note().verify(_result(mean_delay=90.0))

    assert verified.status is NoteStatus.REFUTED
    assert events == (NoteStatusChanged("n1", "r1", NoteStatus.REFUTED),)


def test_every_network_wide_claim_must_agree_to_confirm() -> None:
    note = _note(
        values=(
            Quantity(measure=Measure.MEAN_DELAY, value=40.0),
            Quantity(measure=Measure.ARRIVED, value=20.0),
        )
    )

    verified, _ = note.verify(_result(mean_delay=40.0))

    assert verified.status is NoteStatus.REFUTED


def _assert_unsettled(note: ExpertNote, result: SimulationResult) -> None:
    verified, events = note.verify(result)
    assert verified is note
    assert events == ()


def test_a_result_of_a_different_scenario_settles_nothing() -> None:
    _assert_unsettled(_note(), _result(scenario_id="other"))


@pytest.mark.parametrize("status", [NoteStatus.CONFIRMED, NoteStatus.REFUTED])
def test_an_already_resolved_note_is_left_alone(status: NoteStatus) -> None:
    _assert_unsettled(_note(status=status), _result(mean_delay=90.0))


@pytest.mark.parametrize(
    "value",
    [
        Edges(edge_ids=("E12",), network_id="abc123"),
        BottleneckCauses(
            causes=(EdgeCause(edge_id="E12", network_id="abc123", cause=BottleneckCause.SIGNAL),)
        ),
    ],
)
def test_a_note_with_no_checkable_claim_stays_unverified(value: AnswerValue) -> None:
    _assert_unsettled(_note(values=(value,)), _result())


def test_a_per_edge_quantity_claim_is_not_checked_by_this_first_version() -> None:
    claim = Quantity(measure=Measure.TRAVEL_TIME, value=20.0, edge_id="E12", network_id="abc123")
    _assert_unsettled(_note(values=(claim,)), _result())


def test_a_result_without_kpis_settles_nothing() -> None:
    failed = SimulationResult(
        result_id="r2",
        scenario_id=SCENARIO,
        seed=1,
        mode=RunMode.BATCH,
        status=RunStatus.FAILED,
        content_hash="c2",
        error="sumo crashed",
    )
    _assert_unsettled(_note(), failed)
