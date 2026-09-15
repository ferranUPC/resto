"""Scenario Builder promotion: an already-run `AgentRun[ScenarioDraft]` -> a `Scenario`
(DoD §2.2, §2.4, §4.5; ADR-0001, ADR-0007, ADR-0017). E2.2 Minimal scope: static `lane_closure`
and `speed_limit` on a single lane only — see `adapters/llm/agents/scenario_builder.py` for how
the draft actually gets produced.

This module only does *promotion* — it takes the agent's run as a finished fact, not a `ToolAgent`
to call: `application/` never imports `adapters/`, and running the Builder (assembling the
`AgentTask`/tools and calling `ToolAgent.run`, `adapters/llm/agents/scenario_builder.py`) is an
adapter-layer concern. Whatever wires the two together (today: a script or a test; later: the
Coordinator's `build_scenario` tool, work-plan E5.2) calls `run_scenario_builder` first and hands
its result here.

Promotion order (ADR-0001):
  1. syntactic  - the agent actually returned a `ScenarioDraft` (its dataclass invariants already
                  ran at construction; there is nothing further to re-validate here).
  2. semantic   - the demand belongs to the network, every intervention target the draft claims
                  to have implemented still exists on the network, and SUMO actually loads the
                  cfg it wrote.
  3. construct  - `scenario_id` from the *accepted* interventions (`draft.interventions`, not
                  whatever was in the original task - a rejected one changes the id, DoD §2.3).
  4. persist    - store and return; an existing scenario for that id is returned as-is, skipping
                  steps 2b/3/4 ("zero redundant simulations", architecture §1). This cannot dedupe
                  before the agent ran (the id depends on which interventions it accepted), so a
                  repeated request still costs one agent call even when the result turns out to
                  already exist — unlike `run_simulation`, which dedupes before spending compute.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    ScenarioRepository,
)
from resto.application.ports.sumo import SumoRunner
from resto.domain.entities.scenario import Scenario
from resto.domain.services.content_hash import compute_content_hash
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.tasks import ScenarioTask

NetworkQueryFactory = Callable[[Path], NetworkQuery]


class BuilderRunFailed(RuntimeError):
    """The Builder agent stopped (budget/error) without a usable `ScenarioDraft`."""


class ScenarioSemanticError(ValueError):
    """The draft references state that does not hold: an unknown id, a demand from the wrong
    network, or a cfg SUMO refuses to load."""


def build_scenario(
    task: ScenarioTask,
    run: AgentRun[ScenarioDraft],
    *,
    networks: NetworkRepository,
    demands: DemandRepository,
    scenarios: ScenarioRepository,
    network_query_factory: NetworkQueryFactory,
    runner: SumoRunner,
    out_dir: Path,
) -> Scenario:
    if run.stop_reason is not StopReason.OUTPUT or run.output is None:
        raise BuilderRunFailed(f"scenario_builder stopped on {run.stop_reason} without a draft")
    draft = run.output

    network = networks.get(task.network_id)
    if network is None:
        raise ScenarioSemanticError(f"unknown network_id {task.network_id!r}")
    demand = demands.get(task.demand_id)
    if demand is None:
        raise ScenarioSemanticError(f"unknown demand_id {task.demand_id!r}")
    if demand.network_id != task.network_id:
        raise ScenarioSemanticError(
            f"demand {task.demand_id!r} belongs to network {demand.network_id!r}, "
            f"not {task.network_id!r}"
        )

    query = network_query_factory(network.net_xml.path)
    _check_targets_exist(draft, query)

    scenario_id = scenario_id_for(
        task.network_id, task.demand_id, draft.interventions, task.context_tags
    )
    existing = scenarios.get(scenario_id)
    if existing is not None:
        return existing

    output = runner.run_batch(draft.sumocfg, seed=0, out_dir=out_dir / scenario_id / "load_check")
    if not output.ok:
        raise ScenarioSemanticError(f"SUMO rejected the scenario cfg: {output.error}")

    scenario = Scenario(
        scenario_id=scenario_id,
        network_id=task.network_id,
        demand_id=task.demand_id,
        interventions=draft.interventions,
        mechanisms=draft.mechanisms,
        sumocfg=draft.sumocfg,
        content_hash=_content_hash(draft),
        additional_files=draft.additional_files,
        context_tags=task.context_tags,
        traci_script=draft.script,
    )
    scenarios.store(scenario)
    return scenario


def _check_targets_exist(draft: ScenarioDraft, query: NetworkQuery) -> None:
    """Re-checks every implemented intervention's target against the network directly, rather
    than trusting the agent's own `edge_exists`/`lane_exists` calls (ADR-0001 step 2: semantic
    validation is promotion's job, not something an agent's tool trace can stand in for)."""
    for intervention in draft.interventions:
        target = intervention.target
        if isinstance(target, EdgeTarget) and not query.has_edge(target.edge_id):
            raise ScenarioSemanticError(f"unknown edge {target.edge_id!r}")
        if isinstance(target, LaneTarget) and not query.has_lane(
            target.edge_id, target.lane_index
        ):
            raise ScenarioSemanticError(f"unknown lane {target.lane_id!r}")
        if isinstance(target, TlsTarget) and not query.has_tls(target.tls_id):
            raise ScenarioSemanticError(f"unknown tls {target.tls_id!r}")


def _content_hash(draft: ScenarioDraft) -> str:
    """Fingerprint of the *authored files*, distinct from `scenario_id` (a request hash): lets
    two authoring runs of the same request be compared for "authoring determinism" (DoD §4.5)
    without re-reading every file by hand."""
    file_hashes = sorted(ref.content_hash for ref in draft.additional_files)
    script_hash = draft.script.artifact.content_hash if draft.script is not None else None
    return compute_content_hash("scenario", draft.sumocfg.content_hash, file_hashes, script_hash)
