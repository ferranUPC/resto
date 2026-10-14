"""Demand Generator promotion: an already-run `AgentRun[DemandDraft]` -> a `Demand` (DoD §2.2, §2.4;
ADR-0001, ADR-0035, ADR-0042 §5). Pending until E7.1.

The step executor that called the Demand Generator stores what it returns.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun
from resto.domain.entities.demand import Demand
from resto.domain.value_objects.drafts import DemandDraft
from resto.domain.value_objects.tasks import ObtainDemandTask


class DemandPromoter:
    def promote(self, run: AgentRun[DemandDraft], context: ObtainDemandTask) -> Demand:
        raise NotImplementedError("the demand promotion is not implemented yet (E7.1)")
