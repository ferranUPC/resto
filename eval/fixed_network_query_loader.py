"""A `NetworkQueryLoader` for eval runs that already hold the one network they ask about."""

from __future__ import annotations

from resto.application.ports.network_query import NetworkQuery


class FixedNetworkQueryLoader:
    """Answers every network id with the same query."""

    def __init__(self, query: NetworkQuery) -> None:
        self._query = query

    def load(self, network_id: str) -> NetworkQuery:
        return self._query
