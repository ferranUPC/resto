"""`NetworkQueries` (ADR-0032, "One loader"): the one place that turns a network id into the
`NetworkQuery` over its `.net.xml`. No network."""

from pathlib import Path

import pytest

from resto.adapters.persistence.memory import InMemoryNetworkRepository
from resto.application.network_queries import NetworkNotStored, NetworkQueries
from resto.application.ports.network_query import NetworkQuery
from tests.unit.application._world import QUERY, sample_network


def queries_over(
    networks: InMemoryNetworkRepository, opened: list[Path]
) -> NetworkQueries:
    def factory(path: Path) -> NetworkQuery:
        opened.append(path)
        return QUERY

    return NetworkQueries(networks, factory)


def test_a_stored_network_is_queried_through_its_net_xml() -> None:
    networks = InMemoryNetworkRepository()
    network = sample_network()
    networks.store(network)
    opened: list[Path] = []

    query = queries_over(networks, opened).get(network.network_id)

    assert query is QUERY
    assert opened == [network.net_xml.path]


def test_a_network_id_is_loaded_once_per_resolver() -> None:
    networks = InMemoryNetworkRepository()
    network = sample_network()
    networks.store(network)
    opened: list[Path] = []
    resolver = queries_over(networks, opened)

    first = resolver.get(network.network_id)
    second = resolver.get(network.network_id)

    assert first is second
    assert len(opened) == 1


def test_a_network_that_is_not_stored_is_reported_by_its_id() -> None:
    resolver = queries_over(InMemoryNetworkRepository(), [])

    with pytest.raises(NetworkNotStored, match="'missing'"):
        resolver.get("missing")


def test_a_network_stored_after_a_miss_is_found() -> None:
    networks = InMemoryNetworkRepository()
    network = sample_network()
    resolver = queries_over(networks, [])
    with pytest.raises(NetworkNotStored):
        resolver.get(network.network_id)

    networks.store(network)

    assert resolver.get(network.network_id) is QUERY
