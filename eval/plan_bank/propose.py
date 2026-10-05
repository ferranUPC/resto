"""Rules that propose the phase-0 gold `StudyPlan` of a gold `Question` (E3.7, ADR-0025 §2,
ADR-0027, ADR-0037).

This is a tool for making the answer key, not a stand-in for the Coordinator: it imports nothing
from it. The arm set comes from `needed_arms`; the layout, the sharing of derived networks and the
roles are written here, and the maintainer reviews them.

Layout of every plan:
    0  obtain_network
    1  obtain_demand                      (on step 0; always present)
    then, per distinct topology some needed arm uses:
       derive_network, reroute_demand
    then one build_scenario per needed arm, in the order `needed_arms` gives.
A network-only question stops at step 0.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import NamedTuple

from resto.domain.services.experiment_design import needed_arms
from resto.domain.value_objects.arm import BASE_ARM, contains
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    PlanStep,
    RerouteDemandStep,
    StudyPlan,
)
from resto.domain.value_objects.topology_modification import TopologyModification

GOLD_SEED = 0
"""`ObtainDemandStep.seed` has no default in the type; the gold fixes one and never scores it."""

_OBTAIN_NETWORK_AT = 0
_OBTAIN_DEMAND_AT = 1
_NETWORK = FromStep(_OBTAIN_NETWORK_AT)
_DEMAND = FromStep(_OBTAIN_DEMAND_AT)

Topology = tuple[TopologyModification, ...]


class _NeededArm(NamedTuple):
    """An arm a phase must build; the base arm has no changes and no interventions."""

    label: str
    topology: Topology
    interventions: tuple[Intervention, ...]


class _Placement(NamedTuple):
    """The network and demand steps an arm's scenario is built on."""

    network_id: FromStep
    demand_id: FromStep


def propose_plan(question: Question, phase: int = 0, realised: Collection[str] = ()) -> StudyPlan:
    """The plan a correct Coordinator would write for `question` in `phase`: phase 0 by default.
    `realised` are the arms earlier phases realised; they are not planned again. A later phase
    keeps the phase-0 layout (obtain_network, obtain_demand, ...): both find what is stored."""
    if question.network_ref is None:
        raise ValueError("a gold plan needs the question's network_ref")
    steps: list[PlanStep] = [ObtainNetworkStep(network_ref=question.network_ref)]
    if question.network_only:
        return StudyPlan(
            network_id=_NETWORK,
            rationale="The question is about the network alone: obtain it and stop.",
            steps=tuple(steps),
        )
    steps.append(
        ObtainDemandStep(
            network_id=_NETWORK,
            seed=GOLD_SEED,
            demand_ref=question.demand_ref,
            depends_on=(_OBTAIN_NETWORK_AT,),
        )
    )
    arms = _needed_arms(question, phase, realised)
    placement = _derive_topologies(steps, arms)
    for arm in arms:
        where = placement[arm.topology]
        role = _role(question, arm.label)
        steps.append(
            BuildScenarioStep(
                network_id=where.network_id,
                demand_id=where.demand_id,
                arm=arm.label,
                role=role,
                purpose=_purpose(arm.label, role),
                interventions=arm.interventions,
                context_tags=question.context_tags,
                depends_on=tuple(sorted({where.network_id.step, where.demand_id.step})),
            )
        )
    labels = ", ".join(arm.label for arm in arms)
    return StudyPlan(
        network_id=_NETWORK,
        rationale=f"Phase {phase} of a {question.intent.value} question, arms: {labels}.",
        steps=tuple(steps),
    )


def _derive_topologies(steps: list[PlanStep], arms: list[_NeededArm]) -> dict[Topology, _Placement]:
    """Append one `derive_network` + `reroute_demand` per distinct non-empty topology, in the order
    the arms first use it, and say where each topology's scenarios are built."""
    placement: dict[Topology, _Placement] = {(): _Placement(_NETWORK, _DEMAND)}
    for arm in arms:
        if arm.topology in placement:
            continue
        derive_at = len(steps)
        steps.append(
            DeriveNetworkStep(
                base_network_id=_NETWORK,
                modifications=arm.topology,
                depends_on=(_OBTAIN_NETWORK_AT,),
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


def _needed_arms(question: Question, phase: int, realised: Collection[str]) -> list[_NeededArm]:
    by_label = {a.label: a for a in question.effective_arms}
    result = []
    for label in needed_arms(question, phase):
        if label in realised:
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


def _purpose(label: str, role: ExperimentRole) -> str:
    if label == BASE_ARM:
        return "The network and demand as they are, the reference for the contrasts."
    if role is ExperimentRole.COMPARISON:
        return f"Alternative '{label}', measured against the other alternatives."
    if role is ExperimentRole.BASELINE:
        return f"Arm '{label}' as asked, without a treatment to compare."
    return f"Arm '{label}', the change the question asks about."
