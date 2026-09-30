"""Which `NetworkQuery` belongs to a network id (ADR-0032, "One loader").

The Expert round and the Expert port both ask this module instead of reading the network
repository and calling the query factory themselves. A network is content-addressed, so the query
built for an id stays valid and is kept for the life of the resolver.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import NetworkRepository

NetworkQueryFactory = Callable[[Path], NetworkQuery]


class NetworkNotStored(LookupError):
    """The network id names no stored network. The Executor records it as `infrastructure`."""


class NetworkQueries:
    """Resolves a network id to its `NetworkQuery`, loading each id once."""

    def __init__(self, networks: NetworkRepository, factory: NetworkQueryFactory) -> None:
        self._networks = networks
        self._factory = factory
        self._loaded: dict[str, NetworkQuery] = {}

    def get(self, network_id: str) -> NetworkQuery:
        """Raises:
        NetworkNotStored: no network is stored under `network_id`.
        """
        loaded = self._loaded.get(network_id)
        if loaded is not None:
            return loaded
        network = self._networks.get(network_id)
        if network is None:
            raise NetworkNotStored(f"network {network_id!r} is not stored")
        query = self._factory(network.net_xml.path)
        self._loaded[network_id] = query
        return query
