"""A plan's semantics against stored state and the phase's question (ADR-0025); its syntax
already held when the plan was built. `plan_problems` reads, never writes: planning turns what it
finds into one `agent` failure."""

from __future__ import annotations

from collections.abc import Callable, Collection

from resto.application.ports.repositories import (
    DemandRepository,
    NetworkRepository,
    ScenarioRepository,
)
from resto.domain.services.experiment_design import needed_arms
from resto.domain.value_objects.arm import Arm
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    Produces,
    StudyPlan,
)
from resto.domain.value_objects.topology_modification import TopologyModification


def plan_problems(
    plan: StudyPlan,
    question: Question,
    *,
    phase: int,
    realised: Collection[str],
    network_id: str | None,
    networks: NetworkRepository,
    demands: DemandRepository,
    scenarios: ScenarioRepository,
) -> list[str]:
    """Every problem of `plan` for phase `phase`, in the order found; none means it may run.
    `realised` are the arms earlier phases realised, `network_id` the study's network (none
    before phase 0 ran)."""
    problems: list[str] = []
    if isinstance(plan.network_id, str) and networks.get(plan.network_id) is None:
        problems.append(f"unknown network {plan.network_id!r}")
    if network_id is not None and plan.network_id != network_id:
        problems.append(
            f"phase {phase} plans on network {plan.network_id!r}, the study is about {network_id!r}"
        )
    lookup: dict[Produces, Callable[[str], object]] = {
        "network": networks.get,
        "demand": demands.get,
    }
    run_targets: set[int] = set()
    for i, step in enumerate(plan.steps):
        for kind, ref in step.refs():
            if kind == "scenario":
                problems.append(
                    f"step {i}: {step.kind} must run a scenario built by this plan "
                    "(plan a build_scenario step: an existing scenario costs no agent call)"
                )
            elif lookup[kind](ref) is None:
                problems.append(f"step {i}: unknown {kind} {ref!r}")
        run_targets.update(ref.step for ref, kind in step.inputs if kind == "scenario")
    arms = {a.label: a for a in question.effective_arms}
    for i, step in enumerate(plan.steps):
        if isinstance(step, BuildScenarioStep):
            if i not in run_targets:
                problems.append(f"step {i}: arm {step.arm!r} is built but never run")
            problems += _arm_problems(
                f"step {i}",
                arms.get(step.arm),
                step.interventions,
                on_study_network=step.network_id == plan.network_id,
                derived_by=_derivation(plan, step.network_id),
            )
    problems += _coverage_problems(plan, question, phase, realised)
    return problems


def _derivation(
    plan: StudyPlan, network_ref: str | FromStep
) -> tuple[TopologyModification, ...] | None:
    if isinstance(network_ref, FromStep):
        step = plan.steps[network_ref.step]
        if isinstance(step, DeriveNetworkStep):
            return step.modifications
    return None


def _arm_problems(
    where: str,
    arm: Arm | None,
    interventions: tuple[Intervention, ...],
    *,
    on_study_network: bool,
    derived_by: tuple[TopologyModification, ...] | None = None,
) -> list[str]:
    """An arm is realised by its own interventions, on the study's network unless it changes
    the topology (then on the network deriving exactly its changes). Unknown labels are left
    to the coverage check."""
    expected = arm.interventions if arm is not None else ()
    topology = arm.topology_changes if arm is not None else ()
    problems = []
    if interventions != expected:
        problems.append(f"{where}: its interventions are not those of its arm")
    if topology and on_study_network:
        problems.append(f"{where}: its arm changes the topology, but runs on the study network")
    if not topology and not on_study_network:
        problems.append(f"{where}: its arm keeps the topology, but runs on another network")
    if topology and derived_by is not None and derived_by != topology:
        problems.append(f"{where}: its network is derived with other changes than its arm's")
    return problems


def _coverage_problems(
    plan: StudyPlan, question: Question, phase: int, realised: Collection[str]
) -> list[str]:
    """The plan realises exactly the arms the phase needs that no earlier phase realised
    (ADR-0027 §2, decided with the user for E5.10)."""
    expected = [a for a in needed_arms(question, phase) if a not in realised]
    actual = set(plan.arms)
    problems = [f"arm {a!r} is needed but not planned" for a in expected if a not in actual]
    for arm in sorted(actual - set(expected)):
        if arm in realised:
            problems.append(f"arm {arm!r} was already realised in an earlier phase")
        else:
            problems.append(f"arm {arm!r} is not needed by this phase")
    return problems
