from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.drafts import NetworkDraft
from resto.domain.value_objects.tasks import NetworkTask


class NetworkAuthorAgent(Protocol):
    """Creates (`task.source`) or derives (`task.base_network_id`) a network."""

    def author(self, task: NetworkTask) -> AgentRun[NetworkDraft]: ...
