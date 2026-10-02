from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.drafts import NetworkDraft
from resto.domain.value_objects.outcomes import NetworkOutcome
from resto.domain.value_objects.tasks import NetworkTask, ObtainNetworkTask


class NetworkAuthorAgent(Protocol):
    """Resolves a referenced network (`obtain`: the id of a stored one, or a draft to promote,
    ADR-0037 §3) or derives one from a base network (`author`, `task.base_network_id`)."""

    def obtain(self, task: ObtainNetworkTask) -> AgentRun[NetworkOutcome]: ...

    def author(self, task: NetworkTask) -> AgentRun[NetworkDraft]: ...
