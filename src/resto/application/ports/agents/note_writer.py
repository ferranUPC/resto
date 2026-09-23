from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.drafts import ExpertNoteDrafts
from resto.domain.value_objects.tasks import NoteTask


class NoteWriterAgent(Protocol):
    """0-3 notes after the final round, no tools (ADR-0026)."""

    def write(self, task: NoteTask) -> AgentRun[ExpertNoteDrafts]: ...
