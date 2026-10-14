"""`derive_network`: the Network Author derives a network with the step's modifications."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.agents.network_author import NetworkAuthorAgent
from resto.application.ports.repositories import NetworkRepository
from resto.application.promoters.network import NetworkPromoter
from resto.application.run_study.failures import draft_of, promote
from resto.application.run_study.steps import StepContext
from resto.domain.entities.study import Transition
from resto.domain.value_objects.study_plan import DeriveNetworkStep
from resto.domain.value_objects.tasks import NetworkTask


@dataclass(frozen=True, slots=True)
class DeriveNetworkExecutor:
    author: NetworkAuthorAgent
    networks: NetworkRepository
    promoter: NetworkPromoter
    max_rounds: int
    """Network Author rounds for a step that sets none (`RESTO_NETWORK_MAX_ROUNDS`)."""

    def execute(self, step: DeriveNetworkStep, ctx: StepContext) -> Transition:
        task = NetworkTask(
            base_network_id=dict(step.refs())["network"],
            goals=step.goals,
            modifications=step.modifications,
            min_scc_ratio=step.min_scc_ratio,
            probe_teleport_threshold=step.probe_teleport_threshold,
            max_rounds=self.max_rounds if step.max_rounds is None else step.max_rounds,
        )
        run = ctx.spend.agent_call(lambda: self.author.author(task))
        draft_of(run, "network_author")
        network = promote(lambda: self.promoter.promote(run, task), run.usage)
        self.networks.store(network)
        return ctx.record(step, (network.network_id,), run.usage)
