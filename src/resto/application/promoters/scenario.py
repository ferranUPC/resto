"""Scenario Builder promotion: an already-run `AgentRun[ScenarioDraft]` -> a `Scenario` (DoD §2.2,
§2.4, §4.5; ADR-0001, ADR-0007, ADR-0017, ADR-0042 §5). E2.2 Minimal scope: static `lane_closure`
and `speed_limit` on a single lane only; see `adapters/llm/agents/scenario_builder.py` for how the
draft gets produced.

Promotion order (ADR-0001):
  1. syntactic - the agent returned a `ScenarioDraft` (its dataclass invariants already ran at
                 construction; there is nothing further to re-validate here).
  2. semantic  - the demand belongs to the network and every intervention target the draft
                 claims to have implemented exists on it. A `demand_scale` intervention
                 (E2.3) is also re-checked against its own derived `Demand`
                 (`effective_demand_id`), which becomes the promoted `Scenario`'s `demand_id`: what
                 was simulated, not necessarily the task's own demand.
  3. construct - `scenario_id` from the *accepted* interventions (`draft.interventions`, not
                 whatever was in the original task: a rejected one changes the id, DoD §2.3) and
                 from `task.demand_id` (the request's own demand, unaffected by which derived
                 demand a demand_scale mechanism produced, architecture §1's identity policy).

`BuildScenario` loads the context, checks that SUMO loads the cfg and stores the scenario.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from resto.application.ports.llm import AgentRun
from resto.application.ports.network_query import NetworkQuery
from resto.application.promotion import Blame, DraftRejected, require_draft
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.services.content_hash import compute_content_hash
from resto.domain.services.ids import scenario_id_for
from resto.domain.services.ownership import ensure_demand_on_network
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.mechanism import RegenerateDemandMechanism
from resto.domain.value_objects.tasks import ScenarioTask
from resto.domain.value_objects.traci_script import CloseLane, OpenLane, SetSpeed, When


@dataclass(frozen=True, slots=True)
class ScenarioContext:
    """What the Scenario Builder was given (`task`), loaded: its network, the demands the draft
    names that are stored (by id; a missing one is rejected) and the network's query."""

    task: ScenarioTask
    network: Network
    demands: Mapping[str, Demand]
    query: NetworkQuery

    def __post_init__(self) -> None:
        if self.network.network_id != self.task.network_id:
            raise ValueError(
                f"network {self.network.network_id!r} is not the task's {self.task.network_id!r}"
            )


@dataclass(frozen=True, slots=True)
class ScenarioPromoter:
    def promote(self, run: AgentRun[ScenarioDraft], context: ScenarioContext) -> Scenario:
        task = context.task
        draft = require_draft(run, "scenario_builder")
        _check_demand_on_network(context.demands, task.demand_id, task.network_id, "demand")
        demand_id = effective_demand_id(draft, task.demand_id)
        if demand_id != task.demand_id:
            _check_demand_on_network(context.demands, demand_id, task.network_id, "derived demand")
        _check_targets_exist(draft, context.query)
        _check_script_ids_exist(draft, context.query)
        return Scenario(
            scenario_id=scenario_id_for(
                task.network_id, task.demand_id, draft.interventions, task.context_tags
            ),
            network_id=task.network_id,
            demand_id=demand_id,
            interventions=draft.interventions,
            mechanisms=draft.mechanisms,
            sumocfg=draft.sumocfg,
            content_hash=_content_hash(draft),
            additional_files=draft.additional_files,
            context_tags=task.context_tags,
            traci_script=draft.script,
        )


def effective_demand_id(draft: ScenarioDraft, task_demand_id: str) -> str:
    """The demand `draft.sumocfg`'s routes reference: `task_demand_id` unless a `demand_scale`
    intervention was accepted, in which case it is that mechanism's derived
    `RegenerateDemandMechanism.demand_id` (work-plan E2.3), the last one if more than one demand
    scale mechanism is present, since only the last write_sumocfg-time route set can have won."""
    regenerated = [m for m in draft.mechanisms if isinstance(m, RegenerateDemandMechanism)]
    return regenerated[-1].demand_id if regenerated else task_demand_id


def _check_demand_on_network(
    demands: Mapping[str, Demand], demand_id: str, network_id: str, label: str
) -> None:
    demand = demands.get(demand_id)
    if demand is None:
        raise DraftRejected(f"unknown {label}_id {demand_id!r}")
    try:
        ensure_demand_on_network(demand, network_id, label=label)
    except ValueError as e:
        raise DraftRejected(str(e)) from e


def _unknown_target(what: str) -> DraftRejected:
    """The user's question named it (`StepError(user_input)`), unlike the other rejections, which
    point at a wrong plan or draft."""
    return DraftRejected(what, blame=Blame.USER)


def _check_targets_exist(draft: ScenarioDraft, query: NetworkQuery) -> None:
    """Re-checks every implemented intervention's target against the network directly, rather
    than trusting the agent's own `edge_exists`/`lane_exists` calls (ADR-0001 step 2: semantic
    validation is promotion's job, not something an agent's tool trace can stand in for)."""
    for intervention in draft.interventions:
        target = intervention.target
        if isinstance(target, EdgeTarget) and not query.has_edge(target.edge_id):
            raise _unknown_target(f"unknown edge {target.edge_id!r}")
        if isinstance(target, LaneTarget) and not query.has_lane(target.edge_id, target.lane_index):
            raise _unknown_target(f"unknown lane {target.lane_id!r}")
        if isinstance(target, TlsTarget) and not query.has_tls(target.tls_id):
            raise _unknown_target(f"unknown tls {target.tls_id!r}")


def _check_script_ids_exist(draft: ScenarioDraft, query: NetworkQuery) -> None:
    """Every id a rule names, trigger and action, against the network. A TLS program id cannot be
    checked here; the dry run does."""
    if draft.script is None:
        return
    for rule in draft.script.rules:
        if isinstance(rule.trigger, When):
            target = rule.trigger.condition.target
            if not query.has_edge(target):
                raise _unknown_target(f"unknown edge {target!r} in a rule condition")
        action = rule.action
        if isinstance(action, CloseLane | OpenLane):
            if not query.has_lane(action.edge_id, action.lane_index):
                raise _unknown_target(f"unknown lane {action.lane_id!r}")
        elif isinstance(action, SetSpeed):
            if not query.has_edge(action.edge_id):
                raise _unknown_target(f"unknown edge {action.edge_id!r}")
        elif not query.has_tls(action.tls_id):
            raise _unknown_target(f"unknown tls {action.tls_id!r}")


def _content_hash(draft: ScenarioDraft) -> str:
    """Fingerprint of the *authored files* and the script's rules, distinct from `scenario_id` (a
    request hash): lets two authoring runs of the same request be compared for "authoring
    determinism" (DoD §4.5) without re-reading every file by hand."""
    file_hashes = sorted(ref.content_hash for ref in draft.additional_files)
    script_hash = asdict(draft.script) if draft.script is not None else None
    return compute_content_hash("scenario", draft.sumocfg.content_hash, file_hashes, script_hash)
