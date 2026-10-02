from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.outcomes import DemandOutcome
from resto.domain.value_objects.tasks import ObtainDemandTask


class DemandGeneratorAgent(Protocol):
    """Resolves the demand of a network already resolved: the id of a stored one, or a draft to
    promote (ADR-0037 §3)."""

    def obtain(self, task: ObtainDemandTask) -> AgentRun[DemandOutcome]: ...
