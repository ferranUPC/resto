from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.entities.study import Study
from resto.domain.value_objects.drafts import ReportDraft


class ComposerAgent(Protocol):
    """The Study whose last round answered -> the Composer's prose, as a `ReportDraft`.
    `compose_report` promotes it to the `Report`."""

    def compose(self, study: Study) -> AgentRun[ReportDraft]: ...
