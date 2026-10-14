"""`reroute_demand`: the same trips routed on another network (deterministic, no agent)."""

from __future__ import annotations

from dataclasses import dataclass

from resto.application.ports.repositories import DemandRepository, NetworkRepository
from resto.application.promoters.reroute import ReroutePromoter
from resto.application.run_study.failures import fail, promote
from resto.application.run_study.steps import StepContext
from resto.domain.entities.study import Transition
from resto.domain.value_objects.step_record import StepErrorKind, Usage
from resto.domain.value_objects.study_plan import RerouteDemandStep


@dataclass(frozen=True, slots=True)
class RerouteDemandExecutor:
    networks: NetworkRepository
    demands: DemandRepository
    promoter: ReroutePromoter

    def execute(self, step: RerouteDemandStep, ctx: StepContext) -> Transition:
        ids = dict(step.refs())
        demand = self.demands.get(ids["demand"])
        network = self.networks.get(ids["network"])
        if demand is None or network is None:
            fail(StepErrorKind.AGENT, "reroute_demand names a demand or network not stored")
        rerouted = promote(lambda: self.promoter.promote(demand, network), Usage())
        self.demands.store(rerouted)
        return ctx.record(step, (rerouted.demand_id,))
