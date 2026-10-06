"""The frozen oracle and the plan-validation property (refactor r13, ticket 03).

`frozen_plans.py` holds plans written by hand that no script regenerates. These tests run the
planner (`resto.domain.services.planner`) against them and check the properties every plan of the
bank must have. No database, no LLM, no network."""

from __future__ import annotations

from dataclasses import replace
from itertools import permutations

import pytest
from eval.plan_bank.bank import build_plans, planned_concepts
from eval.request_bank.concepts import concept_by_id

from resto.adapters.persistence.memory import (
    InMemoryDemandRepository,
    InMemoryNetworkRepository,
    InMemoryScenarioRepository,
)
from resto.application.executor.plan_validation import plan_problems
from resto.domain.services.planner import PlanningContext, plan_study
from resto.domain.value_objects.arm import Arm
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    StudyPlan,
)
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network
from tests.unit.eval.frozen_plans import FROZEN, HARD, PHASE1, SELECTED
from tests.unit.eval.test_plan_bank import _gold_of

BANK = {c.id: c.gold for c in planned_concepts() if isinstance(c.gold, Question)}


def _plan(
    question: Question,
    phase: int = 0,
    realised: tuple[str, ...] = (),
    network_id: str | None = None,
) -> StudyPlan:
    return plan_study(question, PlanningContext(phase, network_id, realised))


def _question(concept_id: str) -> Question:
    gold = concept_by_id(concept_id).gold
    assert isinstance(gold, Question)
    return gold


def _problems(
    plan: StudyPlan,
    question: Question,
    *,
    phase: int = 0,
    realised: tuple[str, ...] = (),
    network_id: str | None = None,
) -> list[str]:
    """What the Executor's plan validation finds, against the sample network and demand."""
    networks = InMemoryNetworkRepository()
    networks.store(sample_network())
    demands = InMemoryDemandRepository()
    demands.store(sample_demand())
    return plan_problems(
        plan,
        question,
        phase=phase,
        realised=realised,
        network_id=network_id,
        networks=networks,
        demands=demands,
        scenarios=InMemoryScenarioRepository(),
    )


class TestFrozenSelection:
    def test_between_12_and_15_bank_plans_are_frozen(self) -> None:
        assert 12 <= len(FROZEN) <= 15
        assert set(FROZEN) <= set(BANK)

    def test_the_selection_covers_the_cases_the_ticket_names(self) -> None:
        multi_arm = [c for c in FROZEN if len(_question(c).effective_arms) > 1]
        conditional = [
            c
            for c in FROZEN
            if any(i.condition for a in _question(c).effective_arms for i in a.interventions)
        ]
        network_only = [c for c in FROZEN if _question(c).network_only]
        seven_arms = [c for c in FROZEN if len(_question(c).arms) == 7]

        assert multi_arm
        assert len(conditional) == 2
        assert len(network_only) == 1
        assert seven_arms == ["R065"]

    def test_five_hard_plans_are_marked_for_the_external_reading(self) -> None:
        assert len(set(HARD)) == 5
        assert set(HARD) <= set(FROZEN)


class TestFrozenPlansAgainstThePlanner:
    @pytest.mark.parametrize("concept_id", SELECTED)
    def test_the_planner_reproduces_the_frozen_plan(self, concept_id: str) -> None:
        planned = _plan(_question(concept_id))

        assert _gold_of(planned) == _gold_of(FROZEN[concept_id])

    @pytest.mark.parametrize("concept_id", SELECTED)
    def test_each_frozen_plan_passes_the_executors_plan_validation(self, concept_id: str) -> None:
        assert _problems(FROZEN[concept_id], _question(concept_id)) == []

    def test_phase_1_reproduces_the_frozen_plan_from_the_context(self) -> None:
        planned = _plan(PHASE1.question, 1, PHASE1.realised, PHASE1.network_id)

        assert _gold_of(planned) == _gold_of(PHASE1.plan)
        assert planned.arms == ("treatment",)

    def test_the_frozen_phase_1_plan_passes_validation_on_the_study_network(self) -> None:
        assert _phase1_problems(PHASE1.plan) == []

    def test_the_planned_phase_1_plan_passes_validation_on_the_study_network(self) -> None:
        planned = _plan(PHASE1.question, 1, PHASE1.realised, PHASE1.network_id)

        assert _phase1_problems(planned) == []


def _phase1_problems(plan: StudyPlan) -> list[str]:
    return _problems(
        plan, PHASE1.question, phase=1, realised=PHASE1.realised, network_id=PHASE1.network_id
    )


class TestPlanValidationOverTheBank:
    """For every question of the bank, the plan the planner returns has no problems under the
    Executor's plan validation."""

    PLANS = build_plans()

    @pytest.mark.parametrize("concept_id", sorted(BANK))
    def test_the_plan_has_no_problems(self, concept_id: str) -> None:
        assert _problems(self.PLANS[concept_id], BANK[concept_id]) == []


class TestPlanProperties:
    PLANS = build_plans()

    @pytest.mark.parametrize("concept_id", sorted(BANK))
    def test_step_ids_are_unique(self, concept_id: str) -> None:
        """Step ids are the indexes of `steps`; each build step names its arm once."""
        plan = self.PLANS[concept_id]
        arms = [s.arm for s in plan.steps if isinstance(s, BuildScenarioStep)]

        assert len(set(arms)) == len(arms)
        assert len({id(s) for s in plan.steps}) == len(plan.steps)

    @pytest.mark.parametrize("concept_id", sorted(BANK))
    def test_every_from_step_is_in_the_depends_on_of_its_step(self, concept_id: str) -> None:
        for i, step in enumerate(self.PLANS[concept_id].steps):
            referred = {ref.step for ref, _ in step.inputs}
            assert referred <= set(step.depends_on), f"step {i}"
            assert all(d < i for d in step.depends_on), f"step {i}"

    @pytest.mark.parametrize("concept_id", sorted(FROZEN))
    def test_the_same_holds_for_the_frozen_plans(self, concept_id: str) -> None:
        for step in FROZEN[concept_id].steps:
            assert {ref.step for ref, _ in step.inputs} <= set(step.depends_on)

    @pytest.mark.parametrize("concept_id", sorted(BANK))
    def test_one_derive_network_per_distinct_topology(self, concept_id: str) -> None:
        question = BANK[concept_id]
        topologies = {a.topology_changes for a in question.effective_arms if a.topology_changes}
        derives = [
            s.modifications
            for s in self.PLANS[concept_id].steps
            if isinstance(s, DeriveNetworkStep)
        ]

        assert sorted(map(repr, derives)) == sorted(map(repr, topologies))


def _arms_permuted(question: Question, order: tuple[int, ...]) -> Question:
    arms = question.effective_arms
    permuted: tuple[Arm, ...] = tuple(arms[i] for i in order)
    return replace(
        question,
        interventions=(),
        topology_changes=(),
        arms=permuted,
        contrasts=question.effective_contrasts,
    )


def _experiments(plan: StudyPlan) -> set[str]:
    """What each build step realises, whatever its position: the arm, role, interventions and the
    topology its network is derived with."""
    found = set()
    for step in plan.steps:
        if isinstance(step, BuildScenarioStep):
            network = (
                plan.steps[step.network_id.step] if not isinstance(step.network_id, str) else None
            )
            topology = network.modifications if isinstance(network, DeriveNetworkStep) else ()
            found.add(repr((step.arm, step.role, step.interventions, topology)))
    return found


class TestMetamorphic:
    @pytest.mark.parametrize("concept_id", ["R003", "R022", "R024", "R031", "R020"])
    def test_permuting_the_arms_changes_the_order_of_steps_not_the_set_of_experiments(
        self, concept_id: str
    ) -> None:
        question = _question(concept_id)
        original = _plan(question)
        n = len(question.effective_arms)
        reordered = [
            _plan(_arms_permuted(question, order))
            for order in permutations(range(n))
            if order != tuple(range(n))
        ]

        assert reordered
        assert any(r.arms != original.arms for r in reordered)
        for plan in reordered:
            assert set(plan.arms) == set(original.arms)
            assert _experiments(plan) == _experiments(original)
