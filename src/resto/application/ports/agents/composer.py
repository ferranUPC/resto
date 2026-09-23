from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.entities.study import Study
from resto.domain.value_objects.report import Report


class ComposerAgent(Protocol):
    """The Study whose last round answered -> its `Report` (E5.4 may give it a draft type)."""

    def compose(self, study: Study) -> AgentRun[Report]: ...
