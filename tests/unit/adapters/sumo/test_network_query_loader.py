"""`StoredNetworkQueryLoader` (ADR-0032, "One loader"). No SUMO process."""

from pathlib import Path

import pytest

from resto.adapters.persistence.memory import InMemoryNetworkRepository
from resto.adapters.sumo.network_query_loader import StoredNetworkQueryLoader
from resto.application.ports.network_query import NetworkNotStored, NetworkQuery
from tests.unit.application._world import QUERY, sample_network


def loader_over(
    networks: InMemoryNetworkRepository, opened: list[Path]
) -> StoredNetworkQueryLoader:
    def factory(path: Path) -> NetworkQuery:
        opened.append(path)
        return QUERY

    return StoredNetworkQueryLoader(networks, factory)


def test_a_stored_network_is_queried_through_its_net_xml() -> None:
    networks = InMemoryNetworkRepository()
    network = sample_network()
    networks.store(network)
    opened: list[Path] = []

    query = loader_over(networks, opened).load(network.network_id)

    assert query is QUERY
    assert opened == [network.net_xml.path]


def test_a_network_id_is_loaded_once_per_loader() -> None:
    networks = InMemoryNetworkRepository()
    network = sample_network()
    networks.store(network)
    opened: list[Path] = []
    loader = loader_over(networks, opened)

    first = loader.load(network.network_id)
    second = loader.load(network.network_id)

    assert first is second
    assert len(opened) == 1


def test_a_network_that_is_not_stored_is_reported_by_its_id() -> None:
    loader = loader_over(InMemoryNetworkRepository(), [])

    with pytest.raises(NetworkNotStored, match="'missing'"):
        loader.load("missing")


def test_a_network_stored_after_a_miss_is_found() -> None:
    networks = InMemoryNetworkRepository()
    network = sample_network()
    loader = loader_over(networks, [])
    with pytest.raises(NetworkNotStored):
        loader.load(network.network_id)

    networks.store(network)

    assert loader.load(network.network_id) is QUERY
