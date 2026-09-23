from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.tasks import ScenarioTask


class ScenarioBuilderAgent(Protocol):
    def build(self, task: ScenarioTask) -> AgentRun[ScenarioDraft]: ...
