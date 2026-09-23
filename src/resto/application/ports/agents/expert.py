from __future__ import annotations

from typing import Protocol

from resto.application.ports.llm import AgentRun
from resto.application.tools.expert import EvidenceLedger
from resto.domain.value_objects.expert_answer import ExpertAnswer
from resto.domain.value_objects.tasks import ExpertTask


class ExpertAgent(Protocol):
    """Every tool call of the run lands in `ledger`; `ask_expert` promotes the answer against the
    same ledger."""

    def answer(self, task: ExpertTask, ledger: EvidenceLedger) -> AgentRun[ExpertAnswer]: ...
