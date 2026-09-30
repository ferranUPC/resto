import dataclasses

import pytest

from resto.domain.entities.demand import Demand
from tests.unit.domain._fixtures import artifact, demand_spec
from tests.unit.domain._samples import demand


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_a_demand_rejects_a_blank_description(blank: str) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(demand(), description=blank)


def test_a_demand_has_no_labels_unless_given() -> None:
    d = Demand(
        demand_id="t1",
        network_id="abc123",
        spec=demand_spec(),
        trips=artifact("trips.xml", "t1", "trips"),
        routes=artifact("routes.xml", "r1", "routes"),
        description="Random trips over the whole network.",
    )

    assert d.labels == frozenset()


@pytest.mark.parametrize("blank", ["", "  "])
def test_a_demand_rejects_a_blank_label(blank: str) -> None:
    with pytest.raises(ValueError):
        dataclasses.replace(demand(), labels=frozenset({"peak", blank}))


def test_a_demand_keeps_its_labels_as_written() -> None:
    d = dataclasses.replace(demand(), labels=frozenset({"Peak", " weekday"}))

    assert d.labels == frozenset({"Peak", " weekday"})


def test_description_and_labels_stay_out_of_the_demand_id() -> None:
    d = dataclasses.replace(
        demand(), description="Something else entirely.", labels=frozenset({"other"})
    )

    assert d.demand_id == d.trips.content_hash == demand().demand_id
