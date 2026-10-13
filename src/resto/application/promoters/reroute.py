"""Reroute promotion: a stored `Demand` and the `Network` to move it to -> the derived `Demand`
with the same trips routed on that network (DoD §2.2, §2.4; ADR-0042 §5). Pending until E7.1.

No agent produces it, so the demand takes the place of the agent run and the network is the
context. The step executor that asked for it stores what it returns.
"""

from __future__ import annotations

from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network


class ReroutePromoter:
    def promote(self, demand: Demand, network: Network) -> Demand:
        raise NotImplementedError("the reroute_demand is not implemented yet (E7.1)")
