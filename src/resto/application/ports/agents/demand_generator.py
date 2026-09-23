from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.drafts import DemandDraft
from resto.domain.value_objects.tasks import DemandTask


class DemandGeneratorAgent(Protocol):
    def generate(self, task: DemandTask) -> AgentRun[DemandDraft]: ...
