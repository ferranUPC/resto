"""Scenario Builder use case: an already-run `AgentRun[ScenarioDraft]` -> a stored `Scenario`
(DoD §2.2, §2.4, §4.5; ADR-0001, ADR-0007, ADR-0017, ADR-0042 §5).

It takes the agent's run as a finished fact, not a `ToolAgent` to call: `application/` never imports
`adapters/`, and running the Builder (assembling the `AgentTask`/tools and calling `ToolAgent.run`,
`adapters/llm/agents/scenario_builder.py`) is an adapter-layer concern. Whatever wires the two
together (the Executor's `build_scenario` step, `eval/`) calls the Builder first and hands its
result to `BuildScenario.execute`.

Order:
  1. load    - the network (an unknown one is rejected), the demands the draft names and the
               network's query, for the `ScenarioPromoter`, which checks the draft and builds the
               `Scenario` (`resto.application.promoters.scenario`).
  2. dedupe  - an existing scenario for that id is returned as-is, skipping steps 3 and 4 ("zero
               redundant simulations", architecture §1). This cannot dedupe before the agent ran
               (the id depends on which interventions it accepted), so a repeated request still
               costs one agent call even when the result turns out to already exist, unlike
               `RunSimulation`, which dedupes before spending compute.
  3. check   - SUMO loads the cfg the draft wrote; a refusal rejects the draft.
  4. persist - store and return.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resto.application.ports.llm import AgentRun
from resto.application.ports.network_query import NetworkQueryLoader
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    ScenarioRepository,
)
from resto.application.ports.sumo import SumoRunner
from resto.application.promoters.scenario import (
    ScenarioContext,
    ScenarioPromoter,
    effective_demand_id,
)
from resto.application.promotion import DraftRejected, require_draft
from resto.domain.entities.demand import Demand
from resto.domain.entities.scenario import Scenario
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.tasks import ScenarioTask


@dataclass(frozen=True, slots=True)
class BuildScenario:
    """Promotes the Scenario Builder's run into a stored `Scenario`. `out_dir` is where the SUMO
    load check of each scenario writes (`<out_dir>/<scenario_id>/load_check`)."""

    networks: NetworkRepository
    demands: DemandRepository
    scenarios: ScenarioRepository
    network_query_loader: NetworkQueryLoader
    runner: SumoRunner
    promoter: ScenarioPromoter
    out_dir: Path

    def execute(self, task: ScenarioTask, run: AgentRun[ScenarioDraft]) -> Scenario:
        # The draft names the derived demand to load, so a run without one stops here, first.
        draft = require_draft(run, "scenario_builder")
        network = self.networks.get(task.network_id)
        if network is None:
            raise DraftRejected(f"unknown network_id {task.network_id!r}")
        context = ScenarioContext(
            task=task,
            network=network,
            demands=self._load_demands(task.demand_id, effective_demand_id(draft, task.demand_id)),
            query=self.network_query_loader.load(task.network_id),
        )
        scenario = self.promoter.promote(run, context)

        existing = self.scenarios.get(scenario.scenario_id)
        if existing is not None:
            return existing

        output = self.runner.run_batch(
            draft.sumocfg, seed=0, out_dir=self.out_dir / scenario.scenario_id / "load_check"
        )
        if not output.ok:
            raise DraftRejected(f"SUMO rejected the scenario cfg: {output.error}")
        self.scenarios.store(scenario)
        return scenario

    def _load_demands(self, *demand_ids: str) -> dict[str, Demand]:
        """The stored ones among `demand_ids`; the promoter rejects a missing one."""
        loaded = {demand_id: self.demands.get(demand_id) for demand_id in demand_ids}
        return {demand_id: d for demand_id, d in loaded.items() if d is not None}
