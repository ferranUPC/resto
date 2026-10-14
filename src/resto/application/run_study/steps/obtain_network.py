"""`obtain_network`: the Network Author finds, asks for or creates the network (ADR-0037)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from resto.application.ports.agents.network_author import NetworkAuthorAgent
from resto.application.ports.llm import AgentRun
from resto.application.ports.repositories import NetworkRepository
from resto.application.promoters.network import NetworkPromoter
from resto.application.run_study.failures import StepNeedsUser, draft_of, fail, promote
from resto.application.run_study.steps import StepContext
from resto.domain.entities.study import Transition
from resto.domain.services.reuse import accepts_found_network
from resto.domain.value_objects.drafts import NetworkDraft
from resto.domain.value_objects.outcomes import Found, NeedsUser
from resto.domain.value_objects.step_record import StepErrorKind
from resto.domain.value_objects.study_plan import ObtainNetworkStep
from resto.domain.value_objects.tasks import ObtainNetworkTask


@dataclass(frozen=True, slots=True)
class ObtainNetworkExecutor:
    author: NetworkAuthorAgent
    networks: NetworkRepository
    promoter: NetworkPromoter
    max_rounds: int
    """Network Author rounds for a step that sets none (`RESTO_NETWORK_MAX_ROUNDS`)."""

    def execute(self, step: ObtainNetworkStep, ctx: StepContext) -> Transition:
        task = ObtainNetworkTask(
            network_ref=step.network_ref,
            goals=step.goals,
            min_scc_ratio=step.min_scc_ratio,
            probe_teleport_threshold=step.probe_teleport_threshold,
            max_rounds=self.max_rounds if step.max_rounds is None else step.max_rounds,
        )
        run = ctx.spend.agent_call(lambda: self.author.obtain(task))
        outcome = draft_of(run, "network_author")
        if isinstance(outcome, NeedsUser):
            raise StepNeedsUser(outcome, run.usage)
        if isinstance(outcome, Found):
            if not accepts_found_network(outcome, self.networks.get(outcome.id)):
                fail(
                    StepErrorKind.AGENT,
                    f"the Network Author found network {outcome.id!r}, which is not stored",
                    usage=run.usage,
                )
            network_id = outcome.id
        else:
            draft_run = cast("AgentRun[NetworkDraft]", run)
            network = promote(lambda: self.promoter.promote(draft_run, task), run.usage)
            self.networks.store(network)
            network_id = network.network_id
        return ctx.record(step, (network_id,), run.usage)
