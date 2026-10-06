"""Unit tests for the plan bank's rules script (eval/plan_bank/propose.py, work-plan E3.7).
Pure functions over `Question`s: no database, no LLM, no network."""

from __future__ import annotations

import pytest
from eval.plan_bank.propose import propose_plan
from eval.request_bank.concepts import CONCEPTS, concept_by_id

from resto.application.schemas import adapter_for
from resto.domain.services.experiment_design import needed_arms
from resto.domain.value_objects.arm import Arm, Contrast
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    RerouteDemandStep,
    StudyPlan,
)
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.topology_modification import RemoveEdge, SetLanes

GOLD_QUESTIONS = [c.gold for c in CONCEPTS if isinstance(c.gold, Question)]

_W = TimeWindow(8 * 3600.0, 8.5 * 3600.0)
_CLOSE = Intervention(InterventionType.EDGE_CLOSURE, EdgeTarget("E1"), window=_W)
_LIMIT = Intervention(
    InterventionType.SPEED_LIMIT, EdgeTarget("E2"), params={"speed": 8.0}, window=_W
)
_REMOVE = RemoveEdge("E3")
_WIDEN = SetLanes("E4", 3)


def _question(intent: Intent, **fields: object) -> Question:
    fields.setdefault("network_ref", "DEV-NET")
    return Question("text", intent, **fields)  # type: ignore[arg-type]


def _steps(plan: StudyPlan, kind: type) -> list:
    return [s for s in plan.steps if isinstance(s, kind)]


def _builds(plan: StudyPlan) -> dict[str, BuildScenarioStep]:
    return {s.arm: s for s in _steps(plan, BuildScenarioStep)}


class TestEveryGoldQuestion:
    def test_the_bank_has_54_questions(self) -> None:
        assert len(GOLD_QUESTIONS) == 54

    @pytest.mark.parametrize("question", GOLD_QUESTIONS, ids=lambda q: q.text[:30])
    def test_plan_is_valid_and_covers_exactly_the_needed_arms(self, question: Question) -> None:
        plan = propose_plan(question)

        adapter = adapter_for(StudyPlan)
        assert adapter.validate_python(adapter.dump_python(plan)) == plan
        assert plan.arms == needed_arms(question, 0)


class TestPlainExperiments:
    def test_a_change_question_builds_both_sides_in_phase_0(self) -> None:
        for intent in (Intent.COUNTERFACTUAL, Intent.COMPARE):
            plan = propose_plan(_question(intent, interventions=(_CLOSE,)))

            builds = _builds(plan)
            assert plan.arms == ("base", "treatment")
            assert builds["treatment"].role is ExperimentRole.TREATMENT
            assert builds["treatment"].interventions == (_CLOSE,)
            assert builds["base"].role is ExperimentRole.BASELINE
            assert builds["base"].interventions == ()

    def test_run_builds_the_declared_arms_and_no_base(self) -> None:
        plan = propose_plan(_question(Intent.RUN, interventions=(_CLOSE,)))

        assert plan.arms == ("treatment",)
        assert _builds(plan)["treatment"].interventions == (_CLOSE,)

    def test_run_builds_the_base_only_when_a_contrast_lists_it(self) -> None:
        question = _question(
            Intent.RUN,
            arms=(Arm("closure", interventions=(_CLOSE,)),),
            contrasts=(Contrast("closure"),),
        )

        assert propose_plan(question).arms == ("base", "closure")

    def test_describe_builds_the_base_arm_as_baseline(self) -> None:
        plan = propose_plan(_question(Intent.DESCRIBE, demand_ref="peak"))

        assert plan.arms == ("base",)
        assert _builds(plan)["base"].role is ExperimentRole.BASELINE

    def test_layout_is_network_demand_then_scenarios_on_the_base_network(self) -> None:
        plan = propose_plan(_question(Intent.COMPARE, interventions=(_CLOSE,)))

        assert [type(s) for s in plan.steps] == [
            ObtainNetworkStep,
            ObtainDemandStep,
            BuildScenarioStep,
            BuildScenarioStep,
        ]
        assert plan.network_id == FromStep(0)
        assert all(
            s.network_id == FromStep(0) and s.demand_id == FromStep(1)
            for s in _steps(plan, BuildScenarioStep)
        )

    def test_compare_alternatives_are_comparisons_and_base_stays_baseline(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("closure", interventions=(_CLOSE,)), Arm("limit", interventions=(_LIMIT,))),
            contrasts=(Contrast("closure"), Contrast("limit"), Contrast("closure", "limit")),
        )

        roles = {a: s.role for a, s in _builds(propose_plan(question)).items()}

        assert roles == {
            "base": ExperimentRole.BASELINE,
            "closure": ExperimentRole.COMPARISON,
            "limit": ExperimentRole.COMPARISON,
        }

    def test_compare_against_the_base_only_is_treatment(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("closure", interventions=(_CLOSE,)), Arm("limit", interventions=(_LIMIT,))),
        )

        roles = {a: s.role for a, s in _builds(propose_plan(question)).items()}

        assert roles["closure"] is roles["limit"] is ExperimentRole.TREATMENT


class TestRolesAndDependencies:
    def test_diagnose_builds_the_base_arm_as_baseline(self) -> None:
        plan = propose_plan(_question(Intent.DIAGNOSE))

        assert plan.arms == ("base",)
        assert _builds(plan)["base"].role is ExperimentRole.BASELINE

    def test_a_multi_arm_compare_makes_every_tested_arm_a_treatment(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("closure", interventions=(_CLOSE,)), Arm("limit", interventions=(_LIMIT,))),
        )

        roles = {a: s.role for a, s in _builds(propose_plan(question)).items()}

        assert roles == {
            "base": ExperimentRole.BASELINE,
            "closure": ExperimentRole.TREATMENT,
            "limit": ExperimentRole.TREATMENT,
        }

    def test_a_compare_of_nested_arms_is_not_a_set_of_alternatives(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(
                Arm("widened", topology_changes=(_WIDEN,)),
                Arm("widened_closure", (_WIDEN,), (_CLOSE,)),
            ),
            contrasts=(Contrast("widened_closure", "widened"),),
        )

        roles = {a: s.role for a, s in _builds(propose_plan(question)).items()}

        assert roles == {
            "widened": ExperimentRole.TREATMENT,
            "widened_closure": ExperimentRole.TREATMENT,
        }

    def test_each_step_depends_on_the_steps_it_reads(self) -> None:
        plan = propose_plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))
        derive_at = next(i for i, s in enumerate(plan.steps) if isinstance(s, DeriveNetworkStep))

        assert _steps(plan, ObtainDemandStep)[0].depends_on == (0,)
        assert plan.steps[derive_at].depends_on == (0,)
        assert plan.steps[derive_at + 1].depends_on == (1, derive_at)
        builds = _builds(plan)
        assert builds["base"].depends_on == (0, 1)
        assert builds["treatment"].depends_on == (derive_at, derive_at + 1)

    def test_an_arm_with_only_interventions_stays_on_the_original_network(self) -> None:
        question = _question(
            Intent.RUN,
            arms=(Arm("closure", interventions=(_CLOSE,)), Arm("removed", (_REMOVE,))),
        )

        builds = _builds(propose_plan(question))

        assert builds["closure"].network_id == FromStep(0)
        assert builds["removed"].network_id != FromStep(0)


class TestDemandReference:
    def test_a_concept_without_demand_gives_none(self) -> None:
        plan = propose_plan(concept_by_id("R013").gold)  # type: ignore[arg-type]

        assert _steps(plan, ObtainDemandStep)[0].demand_ref is None

    def test_a_named_demand_gives_a_reference(self) -> None:
        plan = propose_plan(concept_by_id("R001").gold)  # type: ignore[arg-type]

        assert _steps(plan, ObtainDemandStep)[0].demand_ref

    def test_obtain_steps_keep_the_option_defaults(self) -> None:
        plan = propose_plan(_question(Intent.DESCRIBE))
        network = _steps(plan, ObtainNetworkStep)[0]

        assert network.goals == ()
        assert network.min_scc_ratio == ObtainNetworkStep(network_ref="x").min_scc_ratio
        assert network.network_ref == "DEV-NET"


class TestTopologyModifications:
    def test_one_derive_network_with_its_modifications_feeds_the_arm(self) -> None:
        plan = propose_plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))

        derive = _steps(plan, DeriveNetworkStep)
        assert len(derive) == 1
        assert derive[0].modifications == (_REMOVE,)
        assert derive[0].base_network_id == FromStep(0)

    def test_reroute_demand_follows_the_derived_network(self) -> None:
        plan = propose_plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))
        derive_at = next(i for i, s in enumerate(plan.steps) if isinstance(s, DeriveNetworkStep))

        reroute = _steps(plan, RerouteDemandStep)[0]
        treatment = _builds(plan)["treatment"]
        assert reroute.network_id == FromStep(derive_at)
        assert reroute.demand_id == FromStep(1)
        assert treatment.network_id == FromStep(derive_at)
        assert treatment.demand_id == FromStep(derive_at + 1)

    def test_the_base_arm_stays_on_the_original_network_and_demand(self) -> None:
        plan = propose_plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))

        base = _builds(plan)["base"]
        assert (base.network_id, base.demand_id) == (FromStep(0), FromStep(1))

    def test_arms_sharing_a_topology_share_one_derive_network(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(
                Arm("widened", topology_changes=(_WIDEN,)),
                Arm("widened_closure", (_WIDEN,), (_CLOSE,)),
                Arm("widened_limit", (_WIDEN,), (_LIMIT,)),
            ),
            contrasts=(
                Contrast("widened_closure", "widened"),
                Contrast("widened_limit", "widened"),
            ),
        )

        plan = propose_plan(question)

        builds = _builds(plan)
        assert len(_steps(plan, DeriveNetworkStep)) == 1
        assert len({b.network_id for b in builds.values()}) == 1
        assert plan.arms == ("widened", "widened_closure", "widened_limit")

    def test_distinct_topologies_get_their_own_derive_network(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("removed", topology_changes=(_REMOVE,)), Arm("widened", (_WIDEN,))),
        )

        plan = propose_plan(question)

        assert len(_steps(plan, DeriveNetworkStep)) == 2
        builds = _builds(plan)
        assert builds["removed"].network_id != builds["widened"].network_id

    def test_a_change_question_with_nested_arms_plans_both_and_derives_one_network(self) -> None:
        question = _question(
            Intent.COUNTERFACTUAL,
            arms=(
                Arm("widened", topology_changes=(_WIDEN,)),
                Arm("widened_closure", (_WIDEN,), (_CLOSE,)),
            ),
            contrasts=(Contrast("widened_closure", "widened"),),
        )

        plan = propose_plan(question)

        assert plan.arms == ("widened", "widened_closure")
        assert len(_steps(plan, DeriveNetworkStep)) == 1

    def test_an_arm_unused_in_phase_0_derives_nothing(self) -> None:
        plan = propose_plan(_question(Intent.DESCRIBE, topology_changes=(_REMOVE,)))

        assert plan.arms == ("base",)
        assert not _steps(plan, DeriveNetworkStep)


class TestBankShapes:
    def test_a_bank_concept_whose_arms_share_a_topology_gets_one_derive_network(self) -> None:
        question = concept_by_id("R027").gold
        assert isinstance(question, Question)
        topologies = {a.topology_changes for a in question.arms}
        assert len(topologies) == 1

        plan = propose_plan(question)

        assert len(_steps(plan, DeriveNetworkStep)) == 1

    @pytest.mark.parametrize("question", GOLD_QUESTIONS, ids=lambda q: q.text[:30])
    def test_derive_networks_match_the_distinct_topologies_of_the_needed_arms(
        self, question: Question
    ) -> None:
        plan = propose_plan(question)
        by_label = {a.label: a for a in question.effective_arms}
        distinct = {by_label[a].topology_changes for a in plan.arms if a in by_label} - {()}

        assert {s.modifications for s in _steps(plan, DeriveNetworkStep)} == distinct
        assert len(_steps(plan, RerouteDemandStep)) == len(distinct)

    @pytest.mark.parametrize("category", ["combined", "adversarial"])
    def test_combined_and_adversarial_concepts_each_have_a_plan(self, category: str) -> None:
        concepts = [
            c for c in CONCEPTS if c.category.value == category and isinstance(c.gold, Question)
        ]

        assert concepts
        assert all(propose_plan(c.gold).arms for c in concepts)  # type: ignore[arg-type]


class TestNetworkOnly:
    def test_the_only_step_is_obtain_network_and_the_plan_points_at_it(self) -> None:
        plan = propose_plan(_question(Intent.DESCRIBE, network_only=True))

        assert [type(s) for s in plan.steps] == [ObtainNetworkStep]
        assert plan.network_id == FromStep(0)
        assert plan.arms == ()

    @pytest.mark.parametrize("concept_id", ["R074", "R075", "R076"])
    def test_the_bank_concepts_are_network_only(self, concept_id: str) -> None:
        plan = propose_plan(concept_by_id(concept_id).gold)  # type: ignore[arg-type]

        assert len(plan.steps) == 1
        assert isinstance(plan.steps[0], ObtainNetworkStep)


def test_a_question_without_network_ref_is_rejected() -> None:
    with pytest.raises(ValueError, match="network_ref"):
        propose_plan(Question("text", Intent.DESCRIBE))
