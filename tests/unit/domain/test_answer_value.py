from __future__ import annotations

import math

import pytest

from resto.domain.value_objects.answer_value import (
    Change,
    ChangeDirection,
    Edges,
    Measure,
    Quantity,
)


def test_edges_may_be_empty_but_never_repeat() -> None:
    assert Edges(edge_ids=()).edge_ids == ()
    with pytest.raises(ValueError, match="repeat"):
        Edges(edge_ids=("B2C2", "B2C2"))
    with pytest.raises(ValueError, match="non-empty"):
        Edges(edge_ids=("",))


def test_every_measure_has_a_unit() -> None:
    assert Measure.TRAVEL_TIME.unit == "s"
    assert Measure.OCCUPANCY.unit == "%"
    assert all(m.unit for m in Measure)


@pytest.mark.parametrize("measure", [Measure.TRAVEL_TIME, Measure.OCCUPANCY, Measure.TIME_LOSS])
def test_edge_measures_require_an_edge(measure: Measure) -> None:
    Quantity(measure=measure, value=1.0, edge_id="B2C2")
    with pytest.raises(ValueError, match="per edge"):
        Quantity(measure=measure, value=1.0)


@pytest.mark.parametrize("measure", [Measure.MEAN_DELAY, Measure.TELEPORTS])
def test_network_measures_forbid_an_edge(measure: Measure) -> None:
    Change(measure=measure, direction=ChangeDirection.UNCHANGED)
    with pytest.raises(ValueError, match="network-wide"):
        Change(measure=measure, direction=ChangeDirection.UNCHANGED, edge_id="B2C2")


def test_quantity_must_be_finite() -> None:
    with pytest.raises(ValueError, match="finite"):
        Quantity(measure=Measure.MEAN_DELAY, value=math.nan)


@pytest.mark.parametrize(
    ("direction", "pct"),
    [(ChangeDirection.INCREASE, -3.0), (ChangeDirection.DECREASE, 4.0)],
)
def test_change_percentage_cannot_contradict_its_direction(
    direction: ChangeDirection, pct: float
) -> None:
    with pytest.raises(ValueError, match="contradicts"):
        Change(measure=Measure.MEAN_DELAY, direction=direction, relative_change_pct=pct)


def test_change_percentage_is_optional_and_unchanged_accepts_either_sign() -> None:
    Change(measure=Measure.TIME_LOSS, direction=ChangeDirection.INCREASE, edge_id="B2C2")
    Change(measure=Measure.MEAN_DELAY, direction=ChangeDirection.UNCHANGED, relative_change_pct=-2)
    Change(measure=Measure.MEAN_DELAY, direction=ChangeDirection.UNCHANGED, relative_change_pct=3)
