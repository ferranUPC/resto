"""The rule that a `Demand` is only usable on the `Network` it was built for."""

from dataclasses import replace

import pytest

from resto.domain.services.ownership import ensure_demand_on_network
from tests.unit.domain._samples import demand as sample_demand


def test_a_demand_on_its_own_network_passes() -> None:
    demand = sample_demand()

    ensure_demand_on_network(demand, demand.network_id)


def test_a_demand_of_another_network_is_rejected_naming_both() -> None:
    demand = replace(sample_demand(), network_id="other-network")

    with pytest.raises(ValueError, match=f"{demand.demand_id!r}.*'other-network'.*'abc123'"):
        ensure_demand_on_network(demand, "abc123")


def test_the_label_names_what_kind_of_demand_was_rejected() -> None:
    demand = replace(sample_demand(), network_id="other-network")

    with pytest.raises(ValueError, match="^derived demand"):
        ensure_demand_on_network(demand, "abc123", label="derived demand")
