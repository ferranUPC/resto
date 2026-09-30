"""`NetworkQueryLoader` over the network repository and a query factory (sumolib by default).

A network is content-addressed, so the query built for an id stays valid: each id is loaded once
per loader and kept.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.network_query import NetworkNotStored, NetworkQuery
from resto.application.ports.repositories import NetworkRepository


class StoredNetworkQueryLoader:
    def __init__(
        self,
        networks: NetworkRepository,
        factory: Callable[[Path], NetworkQuery] = SumolibNetworkQuery,
    ) -> None:
        self._networks = networks
        self._factory = factory
        self._loaded: dict[str, NetworkQuery] = {}

    def load(self, network_id: str) -> NetworkQuery:
        loaded = self._loaded.get(network_id)
        if loaded is not None:
            return loaded
        network = self._networks.get(network_id)
        if network is None:
            raise NetworkNotStored(f"network {network_id!r} is not stored")
        query = self._factory(network.net_xml.path)
        self._loaded[network_id] = query
        return query
