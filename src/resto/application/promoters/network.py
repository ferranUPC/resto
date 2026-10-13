"""Network Author promotion: an already-run `AgentRun[NetworkDraft]` -> a `Network` (DoD §2.2, §2.4;
ADR-0001, ADR-0042 §5). Pending until E6.1.

One promoter for a created and a derived network: the context says which (an `ObtainNetworkTask`,
or a `NetworkTask` with a `base_network_id`). The step executor that called the Network Author
stores what it returns.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun
from resto.domain.entities.network import Network
from resto.domain.value_objects.drafts import NetworkDraft
from resto.domain.value_objects.tasks import NetworkTask, ObtainNetworkTask


class NetworkPromoter:
    def promote(
        self, run: AgentRun[NetworkDraft], context: NetworkTask | ObtainNetworkTask
    ) -> Network:
        raise NotImplementedError("the network promotion is not implemented yet (E6.1)")
