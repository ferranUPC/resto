"""Configuration of the scenario_builder agent: system prompt, tool list, output draft type,
budget (DoD §2.2). E2.2 Minimal scope only: static `lane_closure` and `speed_limit` on a single
lane (`LaneTarget`), fixed `window`. Anything else — an `EdgeTarget`, a `condition`, any other
`InterventionType` — has no tool that can implement it yet and must land in `rejected[]`
(ADR-0007: no silent coercion), not a best-effort file.

This module has no logic of its own: the loop lives in the `ToolAgent` implementation
(`adapters/llm/anthropic_client.py`), tool behavior lives in `application/tools/scenario_builder`
and the writers. It only assembles the `AgentTask`/tools/budget for one `ScenarioTask` and calls
the agent.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from resto.application.ports.llm import AgentRun, AgentTask, Budget, ToolAgent
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import DemandRepository, NetworkRepository
from resto.application.ports.sumo import DemandScaler, DemandTools
from resto.application.ports.writers import AdditionalFileWriter, SumocfgWriter
from resto.application.tools.scenario_builder import build_scenario_builder_tools
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.tasks import ScenarioTask

SYSTEM_PROMPT = """\
You are the Scenario Builder of a SUMO traffic-simulation framework. You turn a fixed list of
interventions into runnable SUMO files on an unchanged network - you never change the network
itself and you never invent interventions that were not given to you.

In this version you can implement four intervention types, only with a fixed time window (never a
runtime condition) and, for lane_closure/speed_limit, only a single-lane target:
  - lane_closure    -> call write_rerouter(intervention_index)   (target is a single lane)
  - edge_closure    -> call write_rerouter(intervention_index)   (target is a whole edge; same
                        tool - it looks at the intervention's target itself)
  - speed_limit     -> call write_vss(intervention_index)   (params already carry
                        speed/revert_speed)
  - signal_program  -> call write_tls_program(intervention_index)   (params already carry
                        program_id, optionally original_program_id; target is a tls)
  - demand_scale    -> call scale_demand(intervention_index)   (params already carry scale; no
                        target - it is network-wide, and at most one per scenario makes sense)

For every intervention in the task's `interventions` list (0-based index):
  1. Check its target exists: edge_exists / lane_exists (demand_scale has no target - skip this
     check for it). If it does not, reject it.
  2. If its type/target/strategy is not one of the five supported cases above, reject it - do not
     approximate it with a different mechanism.
  3. Otherwise call the matching tool from the list above.

Once every intervention has been either implemented or rejected, call write_sumocfg() (it takes
no arguments - it already knows the network, demand and every file you wrote, including the
routes of a scale_demand call) and then submit your final ScenarioDraft with submit_output:
  - interventions: only the ones you implemented, in the same order as their mechanisms
  - mechanisms: one mechanism per implemented intervention, same order/length -
    StaticFileMechanism(file_kind, path) for write_rerouter/write_vss/write_tls_program results,
    RegenerateDemandMechanism(demand_id) for a scale_demand result (its "demand_id" field)
  - additional_files: the ArtifactRef your write_rerouter/write_vss/write_tls_program calls
    returned for each (scale_demand does not produce one - it is not an additional file)
  - sumocfg: the ArtifactRef write_sumocfg returned
  - rejected: the interventions you could not implement, each with a concrete reason
  - rationale: what you decided and why, in one or two sentences

Never guess a file's path, hash or demand_id yourself - always use exactly what a tool call
returned.
"""


def build_task(task: ScenarioTask) -> AgentTask:
    return AgentTask(
        system_prompt=SYSTEM_PROMPT,
        input={
            "network_id": task.network_id,
            "demand_id": task.demand_id,
            "interventions": [asdict(i) for i in task.interventions],
            "context_tags": sorted(task.context_tags),
        },
    )


def run_scenario_builder(
    task: ScenarioTask,
    agent: ToolAgent,
    budget: Budget,
    *,
    query: NetworkQuery,
    net_file: Path,
    route_files: Sequence[Path],
    begin: float,
    end: float | None,
    rerouter_writer: AdditionalFileWriter,
    vss_writer: AdditionalFileWriter,
    tls_program_writer: AdditionalFileWriter,
    sumocfg_writer: SumocfgWriter,
    demand: Demand,
    network: Network,
    demand_scaler: DemandScaler,
    duarouter: DemandTools,
    demands: DemandRepository,
    out_dir: Path,
) -> AgentRun[ScenarioDraft]:
    """Runs the Builder on `task` and returns its `AgentRun[ScenarioDraft]` — still a draft;
    promotion (id checks, SUMO load check, `scenario_id` construction, persistence) is
    `application/use_cases/build_scenario.py`'s job, not this module's."""
    tools = build_scenario_builder_tools(
        query=query,
        interventions=task.interventions,
        net_file=net_file,
        route_files=route_files,
        begin=begin,
        end=end,
        rerouter_writer=rerouter_writer,
        vss_writer=vss_writer,
        tls_program_writer=tls_program_writer,
        sumocfg_writer=sumocfg_writer,
        demand=demand,
        network=network,
        demand_scaler=demand_scaler,
        duarouter=duarouter,
        demands=demands,
        out_dir=out_dir,
    )
    return agent.run(build_task(task), tools, ScenarioDraft, budget)


@dataclass(frozen=True, slots=True)
class ScenarioBuilderPort:
    """`ScenarioBuilderAgent` port (ADR-0025 §6) over `run_scenario_builder`, with the writers and
    SUMO tools bound. The simulated interval is the demand's window; each request writes into its
    own directory, named after the scenario id it asks for."""

    agent: ToolAgent
    budget: Budget
    networks: NetworkRepository
    demands: DemandRepository
    network_query_factory: Callable[[Path], NetworkQuery]
    rerouter_writer: AdditionalFileWriter
    vss_writer: AdditionalFileWriter
    tls_program_writer: AdditionalFileWriter
    sumocfg_writer: SumocfgWriter
    demand_scaler: DemandScaler
    duarouter: DemandTools
    out_dir: Path

    def build(self, task: ScenarioTask) -> AgentRun[ScenarioDraft]:
        network = self.networks.get(task.network_id)
        demand = self.demands.get(task.demand_id)
        if network is None or demand is None:
            raise LookupError(f"network {task.network_id!r} or demand {task.demand_id!r} missing")
        requested = scenario_id_for(
            task.network_id, task.demand_id, task.interventions, task.context_tags
        )
        return run_scenario_builder(
            task,
            self.agent,
            self.budget,
            query=self.network_query_factory(network.net_xml.path),
            net_file=network.net_xml.path,
            route_files=(demand.routes.path,),
            begin=demand.spec.window.start,
            end=demand.spec.window.end,
            rerouter_writer=self.rerouter_writer,
            vss_writer=self.vss_writer,
            tls_program_writer=self.tls_program_writer,
            sumocfg_writer=self.sumocfg_writer,
            demand=demand,
            network=network,
            demand_scaler=self.demand_scaler,
            duarouter=self.duarouter,
            demands=self.demands,
            out_dir=self.out_dir / requested,
        )
