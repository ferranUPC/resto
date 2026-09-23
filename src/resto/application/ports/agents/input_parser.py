from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.domain.value_objects.question import Question


class InputParserAgent(Protocol):
    """User text -> `Question`, no tools (ADR-0023). Textual ambiguity goes in
    `Question.ambiguities`, never into a guess."""

    def parse(self, text: str) -> AgentRun[Question]: ...
