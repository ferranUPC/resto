"""The planner: a pure function from a `Question` and a planning context to a `StudyPlan`
(ADR-0039, which replaces the Coordinator agent; ADR-0025 §2, ADR-0027, ADR-0037, ADR-0038).

The arm set comes from `needed_arms`; the layout, the sharing of derived networks, the roles and the
texts are written here, in one place. Interventions are copied to the `build_scenario` of their arm
without interpretation: the Builder chooses the mechanism.

Layout of every plan:
    0  obtain_network
    1  obtain_demand                      (on step 0; always present)
    then, per distinct topology some planned arm uses:
       derive_network, reroute_demand
    then one build_scenario per planned arm, in the order `needed_arms` gives (the arms an earlier
       phase already realised, `PlanningContext.realised`, are left out, the rest keep their order),
    then one run_simulation per built arm, in the same order.
A network-only question stops at step 0.

Once the study's network is known (phase 1 on), the plan names it by id instead of by `FromStep(0)`,
because the Executor's plan validation compares the plan's network with the study's. Step 0 is still
an `obtain_network`, on that id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from resto.domain.services.experiment_design import needed_arms
from resto.domain.value_objects.arm import BASE_ARM, contains
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.intervention_target import (
    EdgeTarget,
    InterventionTarget,
    LaneTarget,
    TazTarget,
    TlsTarget,
)
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    PlanStep,
    RerouteDemandStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import (
    AddEdge,
    RemoveEdge,
    SetLanes,
    SetSpeed,
    TopologyModification,
)

DEMAND_SEED = 0
"""`ObtainDemandStep.seed` has no default in the type; the planner fixes one."""

_OBTAIN_NETWORK_AT = 0
_OBTAIN_DEMAND_AT = 1
_DEMAND = FromStep(_OBTAIN_DEMAND_AT)

Topology = tuple[TopologyModification, ...]


class PlanningError(ValueError):
    """The rules cannot plan this question in this context; the message names the cause."""


@dataclass(frozen=True, slots=True)
class PlanningContext:
    """What the planner is told besides the question. `network_id` is the study's network once an
    earlier phase fixed it (`None` while planning phase 0); `realised` are the arms earlier phases
    realised, which are not planned again."""

    phase: int
    network_id: str | None = None
    realised: tuple[str, ...] = ()


class _NeededArm(NamedTuple):
    """An arm a phase must build; the base arm has no changes and no interventions."""

    label: str
    topology: Topology
    interventions: tuple[Intervention, ...]


class _Placement(NamedTuple):
    """The network and demand steps an arm's scenario is built on."""

    network_id: str | FromStep
    demand_id: FromStep


def plan_study(question: Question, context: PlanningContext) -> StudyPlan:
    """The plan of phase `context.phase` for `question`. Raises `PlanningError` when the rules
    cannot plan it."""
    if question.is_ambiguous:
        raise PlanningError(
            "the question is ambiguous and awaits the user: " + "; ".join(question.ambiguities)
        )
    study_network = _study_network(question, context)
    network: str | FromStep = study_network if context.network_id is not None else FromStep(0)
    steps: list[PlanStep] = [ObtainNetworkStep(network_ref=study_network)]
    if question.network_only:
        return StudyPlan(
            network_id=network,
            rationale="The question is about the network alone: obtain it and stop.",
            steps=tuple(steps),
        )
    steps.append(
        ObtainDemandStep(
            network_id=FromStep(_OBTAIN_NETWORK_AT),
            seed=DEMAND_SEED,
            demand_ref=question.demand_ref,
            depends_on=(_OBTAIN_NETWORK_AT,),
        )
    )
    arms = _needed_arms(question, context)
    if not arms:
        raise PlanningError(
            f"nothing to plan in phase {context.phase}: every arm the question needs is "
            f"already realised ({', '.join(sorted(context.realised))})"
        )
    placement = _derive_topologies(steps, arms, network)
    for arm in arms:
        where = placement[arm.topology]
        role = _role(question, arm.label)
        steps.append(
            BuildScenarioStep(
                network_id=where.network_id,
                demand_id=where.demand_id,
                arm=arm.label,
                role=role,
                purpose=_purpose(arm, role),
                interventions=arm.interventions,
                context_tags=question.context_tags,
                depends_on=tuple(
                    sorted(
                        {
                            r.step
                            for r in (where.network_id, where.demand_id)
                            if isinstance(r, FromStep)
                        }
                    )
                ),
            )
        )
    built = [i for i, s in enumerate(steps) if isinstance(s, BuildScenarioStep)]
    steps += [RunSimulationStep(scenario_id=FromStep(i), depends_on=(i,)) for i in built]
    labels = ", ".join(arm.label for arm in arms)
    return StudyPlan(
        network_id=network,
        rationale=(
            f"Phase {context.phase} of a {question.intent.value} question, arms: {labels}. "
            "Each arm is built on the study's demand and run once."
        ),
        steps=tuple(steps),
    )


def _study_network(question: Question, context: PlanningContext) -> str:
    """The id the plan's `obtain_network` finds: the study's once known, else the question's."""
    if context.phase < 0:
        raise PlanningError(f"phase must be >= 0, got {context.phase}")
    found = context.network_id if context.network_id is not None else question.network_ref
    if found is None:
        raise PlanningError(
            f"the question names no network (network_ref) and phase {context.phase} has no "
            "study network to take it from"
        )
    return found


def _derive_topologies(
    steps: list[PlanStep], arms: list[_NeededArm], network: str | FromStep
) -> dict[Topology, _Placement]:
    """Append one `derive_network` + `reroute_demand` per distinct non-empty topology, in the order
    the arms first use it, and say where each topology's scenarios are built. `steps` is the list
    `plan_study` is building for this one call, so the planner as a whole stays pure."""
    placement: dict[Topology, _Placement] = {(): _Placement(network, _DEMAND)}
    for arm in arms:
        if arm.topology in placement:
            continue
        derive_at = len(steps)
        steps.append(
            DeriveNetworkStep(
                base_network_id=network,
                modifications=arm.topology,
                depends_on=(_OBTAIN_NETWORK_AT,) if isinstance(network, FromStep) else (),
            )
        )
        steps.append(
            RerouteDemandStep(
                demand_id=_DEMAND,
                network_id=FromStep(derive_at),
                depends_on=(_OBTAIN_DEMAND_AT, derive_at),
            )
        )
        placement[arm.topology] = _Placement(FromStep(derive_at), FromStep(derive_at + 1))
    return placement


def _needed_arms(question: Question, context: PlanningContext) -> list[_NeededArm]:
    by_label = {a.label: a for a in question.effective_arms}
    result = []
    for label in needed_arms(question, context.phase):
        if label in context.realised:
            continue
        arm = by_label.get(label)
        result.append(
            _NeededArm(label, arm.topology_changes, arm.interventions)
            if arm
            else _NeededArm(label, (), ())
        )
    return result


def _role(question: Question, label: str) -> ExperimentRole:
    if label == BASE_ARM or question.intent in (Intent.DESCRIBE, Intent.DIAGNOSE):
        return ExperimentRole.BASELINE
    if question.intent is Intent.COMPARE and _is_alternative(question, label):
        return ExperimentRole.COMPARISON
    return ExperimentRole.TREATMENT


def _is_alternative(question: Question, label: str) -> bool:
    """An arm contrasted with another non-base arm that it neither contains nor is contained in."""
    arms = {a.label: a for a in question.effective_arms}
    for c in question.effective_contrasts:
        if label not in (c.treatment, c.reference):
            continue
        other = c.reference if label == c.treatment else c.treatment
        if other == BASE_ARM:
            continue
        mine, theirs = arms[label], arms[other]
        if not contains(mine, theirs) and not contains(theirs, mine):
            return True
    return False


_ROLE_SENTENCE = {
    ExperimentRole.BASELINE: "as asked, without a treatment to compare",
    ExperimentRole.TREATMENT: "the change the question asks about",
    ExperimentRole.COMPARISON: "an alternative, measured against the other alternatives",
}


def _purpose(arm: _NeededArm, role: ExperimentRole) -> str:
    """What the scenario is for, naming its arm, its role and every change it carries. The
    Expert's note writer reads this text and no other field of the plan to tell scenarios apart."""
    if arm.label == BASE_ARM:
        return (
            "Baseline arm 'base': the network and demand unchanged, the reference for the "
            "contrasts."
        )
    changes = [*map(_modification, arm.topology), *map(_intervention, arm.interventions)]
    return (
        f"{role.value.capitalize()} arm '{arm.label}': {_ROLE_SENTENCE[role]}. "
        f"Changes: {'; '.join(changes)}."
    )


def _modification(change: TopologyModification) -> str:
    match change:
        case RemoveEdge():
            return f"remove edge {change.edge_id}"
        case AddEdge():
            name = f" {change.edge_id}" if change.edge_id else ""
            return (
                f"add edge{name} from {change.from_junction} to {change.to_junction} "
                f"({change.lanes} lanes, {change.speed:g} m/s)"
            )
        case SetLanes():
            return f"set edge {change.edge_id} to {change.lanes} lanes"
        case SetSpeed():
            return f"set edge {change.edge_id} speed to {change.speed:g} m/s"


def _intervention(i: Intervention) -> str:
    parts = [i.type.value]
    if i.target is not None:
        parts.append(f"on {_target(i.target)}")
    if i.params:
        parts.append("(" + ", ".join(f"{k}={v}" for k, v in sorted(i.params.items())) + ")")
    if i.window is not None:
        parts.append(f"from {_clock(i.window)}")
    if i.condition is not None:
        c = i.condition
        parts.append(f"when {c.metric.value} of {c.target} {c.op.value} {c.value:g}")
    if i.description:
        parts.append(f"[{i.description}]")
    return " ".join(parts)


def _target(target: InterventionTarget) -> str:
    match target:
        case EdgeTarget():
            return f"edge {target.edge_id}"
        case LaneTarget():
            return f"lane {target.lane_id}"
        case TlsTarget():
            return f"traffic light {target.tls_id}"
        case TazTarget():
            return f"zone {target.taz_id}"


def _clock(window: TimeWindow) -> str:
    return f"{_hhmm(window.start)} to {_hhmm(window.end)}"


def _hhmm(seconds: float) -> str:
    minutes = round(seconds / 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
