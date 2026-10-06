"""Unit tests for the planner (resto.domain.services.planner, refactor r13 ticket 04): a pure
function from a `Question` and a planning context to a `StudyPlan`. No database, no LLM, no
network. The expected plans written by hand are in `tests/unit/eval/frozen_plans.py`."""

from __future__ import annotations

import pytest
from eval.request_bank.concepts import CONCEPTS, concept_by_id

from resto.application.schemas import adapter_for
from resto.domain.services.experiment_design import needed_arms
from resto.domain.services.planner import PlanningContext, PlanningError, plan_study
from resto.domain.value_objects.arm import Arm, Contrast
from resto.domain.value_objects.condition import Condition, Metric, Operator
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
    RunSimulationStep,
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


def _plan(
    question: Question,
    phase: int = 0,
    realised: tuple[str, ...] = (),
    network_id: str | None = None,
) -> StudyPlan:
    return plan_study(question, PlanningContext(phase, network_id, tuple(realised)))


def _steps(plan: StudyPlan, kind: type) -> list:
    return [s for s in plan.steps if isinstance(s, kind)]


def _builds(plan: StudyPlan) -> dict[str, BuildScenarioStep]:
    return {s.arm: s for s in _steps(plan, BuildScenarioStep)}


class TestEveryGoldQuestion:
    def test_the_bank_has_54_questions(self) -> None:
        assert len(GOLD_QUESTIONS) == 54

    @pytest.mark.parametrize("question", GOLD_QUESTIONS, ids=lambda q: q.text[:30])
    def test_plan_is_valid_and_covers_exactly_the_needed_arms(self, question: Question) -> None:
        plan = _plan(question)

        adapter = adapter_for(StudyPlan)
        assert adapter.validate_python(adapter.dump_python(plan)) == plan
        assert plan.arms == needed_arms(question, 0)


class TestPlainExperiments:
    def test_a_change_question_builds_both_sides_in_phase_0(self) -> None:
        for intent in (Intent.COMPARE,):
            plan = _plan(_question(intent, interventions=(_CLOSE,)))

            builds = _builds(plan)
            assert plan.arms == ("base", "treatment")
            assert builds["treatment"].role is ExperimentRole.TREATMENT
            assert builds["treatment"].interventions == (_CLOSE,)
            assert builds["base"].role is ExperimentRole.BASELINE
            assert builds["base"].interventions == ()

    def test_run_builds_the_declared_arms_and_no_base(self) -> None:
        plan = _plan(_question(Intent.RUN, interventions=(_CLOSE,)))

        assert plan.arms == ("treatment",)
        assert _builds(plan)["treatment"].interventions == (_CLOSE,)

    def test_run_builds_the_base_only_when_a_contrast_lists_it(self) -> None:
        question = _question(
            Intent.RUN,
            arms=(Arm("closure", interventions=(_CLOSE,)),),
            contrasts=(Contrast("closure"),),
        )

        assert _plan(question).arms == ("base", "closure")

    def test_describe_builds_the_base_arm_as_baseline(self) -> None:
        plan = _plan(_question(Intent.DESCRIBE, demand_ref="peak"))

        assert plan.arms == ("base",)
        assert _builds(plan)["base"].role is ExperimentRole.BASELINE

    def test_layout_is_network_demand_then_scenarios_on_the_base_network(self) -> None:
        plan = _plan(_question(Intent.COMPARE, interventions=(_CLOSE,)))

        assert [type(s) for s in plan.steps] == [
            ObtainNetworkStep,
            ObtainDemandStep,
            BuildScenarioStep,
            BuildScenarioStep,
            RunSimulationStep,
            RunSimulationStep,
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

        roles = {a: s.role for a, s in _builds(_plan(question)).items()}

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

        roles = {a: s.role for a, s in _builds(_plan(question)).items()}

        assert roles["closure"] is roles["limit"] is ExperimentRole.TREATMENT


class TestRolesAndDependencies:
    def test_diagnose_builds_the_base_arm_as_baseline(self) -> None:
        plan = _plan(_question(Intent.DIAGNOSE))

        assert plan.arms == ("base",)
        assert _builds(plan)["base"].role is ExperimentRole.BASELINE

    def test_a_multi_arm_compare_makes_every_tested_arm_a_treatment(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("closure", interventions=(_CLOSE,)), Arm("limit", interventions=(_LIMIT,))),
        )

        roles = {a: s.role for a, s in _builds(_plan(question)).items()}

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

        roles = {a: s.role for a, s in _builds(_plan(question)).items()}

        assert roles == {
            "widened": ExperimentRole.TREATMENT,
            "widened_closure": ExperimentRole.TREATMENT,
        }

    def test_each_step_depends_on_the_steps_it_reads(self) -> None:
        plan = _plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))
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

        builds = _builds(_plan(question))

        assert builds["closure"].network_id == FromStep(0)
        assert builds["removed"].network_id != FromStep(0)


class TestDemandReference:
    def test_a_concept_without_demand_gives_none(self) -> None:
        plan = _plan(concept_by_id("R013").gold)  # type: ignore[arg-type]

        assert _steps(plan, ObtainDemandStep)[0].demand_ref is None

    def test_a_named_demand_gives_a_reference(self) -> None:
        plan = _plan(concept_by_id("R001").gold)  # type: ignore[arg-type]

        assert _steps(plan, ObtainDemandStep)[0].demand_ref

    def test_obtain_steps_keep_the_option_defaults(self) -> None:
        plan = _plan(_question(Intent.DESCRIBE))
        network = _steps(plan, ObtainNetworkStep)[0]

        assert network.goals == ()
        assert network.min_scc_ratio == ObtainNetworkStep(network_ref="x").min_scc_ratio
        assert network.network_ref == "DEV-NET"


class TestTopologyModifications:
    def test_one_derive_network_with_its_modifications_feeds_the_arm(self) -> None:
        plan = _plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))

        derive = _steps(plan, DeriveNetworkStep)
        assert len(derive) == 1
        assert derive[0].modifications == (_REMOVE,)
        assert derive[0].base_network_id == FromStep(0)

    def test_reroute_demand_follows_the_derived_network(self) -> None:
        plan = _plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))
        derive_at = next(i for i, s in enumerate(plan.steps) if isinstance(s, DeriveNetworkStep))

        reroute = _steps(plan, RerouteDemandStep)[0]
        treatment = _builds(plan)["treatment"]
        assert reroute.network_id == FromStep(derive_at)
        assert reroute.demand_id == FromStep(1)
        assert treatment.network_id == FromStep(derive_at)
        assert treatment.demand_id == FromStep(derive_at + 1)

    def test_the_base_arm_stays_on_the_original_network_and_demand(self) -> None:
        plan = _plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,)))

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

        plan = _plan(question)

        builds = _builds(plan)
        assert len(_steps(plan, DeriveNetworkStep)) == 1
        assert len({b.network_id for b in builds.values()}) == 1
        assert plan.arms == ("widened", "widened_closure", "widened_limit")

    def test_distinct_topologies_get_their_own_derive_network(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("removed", topology_changes=(_REMOVE,)), Arm("widened", (_WIDEN,))),
        )

        plan = _plan(question)

        assert len(_steps(plan, DeriveNetworkStep)) == 2
        builds = _builds(plan)
        assert builds["removed"].network_id != builds["widened"].network_id

    def test_a_change_question_with_nested_arms_plans_both_and_derives_one_network(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(
                Arm("widened", topology_changes=(_WIDEN,)),
                Arm("widened_closure", (_WIDEN,), (_CLOSE,)),
            ),
            contrasts=(Contrast("widened_closure", "widened"),),
        )

        plan = _plan(question)

        assert plan.arms == ("widened", "widened_closure")
        assert len(_steps(plan, DeriveNetworkStep)) == 1

    def test_an_arm_unused_in_phase_0_derives_nothing(self) -> None:
        plan = _plan(_question(Intent.DESCRIBE, topology_changes=(_REMOVE,)))

        assert plan.arms == ("base",)
        assert not _steps(plan, DeriveNetworkStep)


class TestBankShapes:
    def test_a_bank_concept_whose_arms_share_a_topology_gets_one_derive_network(self) -> None:
        question = concept_by_id("R027").gold
        assert isinstance(question, Question)
        topologies = {a.topology_changes for a in question.arms}
        assert len(topologies) == 1

        plan = _plan(question)

        assert len(_steps(plan, DeriveNetworkStep)) == 1

    @pytest.mark.parametrize("question", GOLD_QUESTIONS, ids=lambda q: q.text[:30])
    def test_derive_networks_match_the_distinct_topologies_of_the_needed_arms(
        self, question: Question
    ) -> None:
        plan = _plan(question)
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
        assert all(_plan(c.gold).arms for c in concepts)  # type: ignore[arg-type]


class TestNetworkOnly:
    def test_the_only_step_is_obtain_network_and_the_plan_points_at_it(self) -> None:
        plan = _plan(_question(Intent.DESCRIBE, network_only=True))

        assert [type(s) for s in plan.steps] == [ObtainNetworkStep]
        assert plan.network_id == FromStep(0)
        assert plan.arms == ()

    @pytest.mark.parametrize("concept_id", ["R074", "R075", "R076"])
    def test_the_bank_concepts_are_network_only(self, concept_id: str) -> None:
        plan = _plan(concept_by_id(concept_id).gold)  # type: ignore[arg-type]

        assert len(plan.steps) == 1
        assert isinstance(plan.steps[0], ObtainNetworkStep)


class TestRunSteps:
    def test_one_run_per_built_arm_after_all_the_builds_in_build_order(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("closure", interventions=(_CLOSE,)), Arm("removed", (_REMOVE,))),
        )

        plan = _plan(question)

        builds = [i for i, s in enumerate(plan.steps) if isinstance(s, BuildScenarioStep)]
        runs = [(i, s) for i, s in enumerate(plan.steps) if isinstance(s, RunSimulationStep)]
        assert [i for i, _ in runs] == list(range(builds[-1] + 1, builds[-1] + 1 + len(builds)))
        assert [s.scenario_id for _, s in runs] == [FromStep(b) for b in builds]
        assert [s.depends_on for _, s in runs] == [(b,) for b in builds]
        assert all(s.seeds is None for _, s in runs)

    def test_the_build_order_follows_needed_arms_without_the_realised_arms(self) -> None:
        question = _question(
            Intent.RUN,
            arms=(
                Arm("closure", interventions=(_CLOSE,)),
                Arm("limit", interventions=(_LIMIT,)),
                Arm("removed", (_REMOVE,)),
            ),
            contrasts=(Contrast("closure"), Contrast("limit"), Contrast("removed")),
        )
        order = needed_arms(question, 1)

        plan = _plan(question, 1, ("limit",), "abc123")

        assert plan.arms == tuple(a for a in order if a != "limit")
        assert len(plan.arms) == len(order) - 1

    def test_a_network_only_question_plans_no_run(self) -> None:
        plan = _plan(_question(Intent.DESCRIBE, network_only=True))

        assert not _steps(plan, RunSimulationStep)


class TestPhase1:
    NETWORK = "abc123"

    def _proposed(self) -> Question:
        return Question("text", Intent.RUN, demand_ref="peak", interventions=(_CLOSE,))

    def test_a_missing_network_ref_is_replaced_by_the_contexts_network_id(self) -> None:
        plan = _plan(self._proposed(), 1, ("base",), self.NETWORK)

        assert plan.network_id == self.NETWORK
        assert _steps(plan, ObtainNetworkStep)[0].network_ref == self.NETWORK
        assert _builds(plan)["treatment"].network_id == self.NETWORK
        assert _builds(plan)["treatment"].depends_on == (1,)

    def test_a_proposed_experiment_plans_as_a_run_of_its_arm(self) -> None:
        plan = _plan(self._proposed(), 1, ("base",), self.NETWORK)

        assert plan.arms == ("treatment",)
        assert [type(s) for s in plan.steps] == [
            ObtainNetworkStep,
            ObtainDemandStep,
            BuildScenarioStep,
            RunSimulationStep,
        ]

    def test_an_arm_realised_earlier_is_not_planned_again(self) -> None:
        question = _question(Intent.COMPARE, interventions=(_CLOSE,))

        plan = _plan(question, 1, ("base",), self.NETWORK)

        assert plan.arms == ("treatment",)

    def test_the_contexts_id_wins_over_the_questions_network_ref(self) -> None:
        question = _question(Intent.COMPARE, interventions=(_CLOSE,))

        plan = _plan(question, 1, ("base",), self.NETWORK)

        assert plan.network_id == self.NETWORK

    def test_one_derive_network_per_topology_in_phase_1_reads_the_study_network(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(
                Arm("widened", topology_changes=(_WIDEN,)),
                Arm("widened_closure", (_WIDEN,), (_CLOSE,)),
            ),
            contrasts=(Contrast("widened_closure", "widened"),),
        )

        plan = _plan(question, 1, (), self.NETWORK)

        derive = _steps(plan, DeriveNetworkStep)
        assert len(derive) == 1
        assert derive[0].base_network_id == self.NETWORK
        assert derive[0].depends_on == ()


class TestPlanningError:
    def test_phase_0_without_a_network_ref_names_the_cause(self) -> None:
        with pytest.raises(PlanningError, match="network"):
            _plan(Question("text", Intent.DESCRIBE))

    def test_an_ambiguous_question_is_not_planned(self) -> None:
        with pytest.raises(PlanningError, match="ambigu"):
            _plan(_question(Intent.DESCRIBE, ambiguities=("which street?",)))

    def test_a_phase_with_every_arm_realised_has_nothing_to_plan(self) -> None:
        question = _question(Intent.COMPARE, interventions=(_CLOSE,))

        with pytest.raises(PlanningError, match="realised"):
            _plan(question, 1, ("base", "treatment"), "abc123")

    def test_the_error_is_a_value_error_so_a_caller_can_catch_the_family(self) -> None:
        assert issubclass(PlanningError, ValueError)


class TestPurposeAndRationale:
    """The Expert's note writer reads `arm`, `role` and `purpose` of every scenario and nothing
    else of the plan (`build_note_task`), so `purpose` is where it learns what an arm changes."""

    def test_purpose_names_the_arm_its_role_and_each_intervention(self) -> None:
        plan = _plan(_question(Intent.COMPARE, interventions=(_CLOSE, _LIMIT)))

        purpose = _builds(plan)["treatment"].purpose

        assert "treatment" in purpose
        assert "E1" in purpose and "E2" in purpose
        assert "edge_closure" in purpose and "speed_limit" in purpose
        assert "08:00" in purpose and "08:30" in purpose

    def test_purpose_names_a_topology_change_and_a_condition(self) -> None:
        condition = Condition(Metric.OCCUPANCY, "E4", Operator.GT, 0.8)
        gated = Intervention(
            InterventionType.SPEED_LIMIT,
            EdgeTarget("E2"),
            params={"speed": 8.0},
            condition=condition,
        )
        plan = _plan(_question(Intent.COMPARE, topology_changes=(_REMOVE,), interventions=(gated,)))

        purpose = _builds(plan)["treatment"].purpose

        assert "remove edge E3" in purpose
        assert "occupancy" in purpose and "E4" in purpose and "0.8" in purpose

    def test_purposes_of_two_arms_differ_so_a_note_can_pick_one(self) -> None:
        question = _question(
            Intent.COMPARE,
            arms=(Arm("closure", interventions=(_CLOSE,)), Arm("limit", interventions=(_LIMIT,))),
        )

        purposes = [b.purpose for b in _builds(_plan(question)).values()]

        assert len(set(purposes)) == len(purposes)

    def test_the_base_arm_is_the_unchanged_network(self) -> None:
        plan = _plan(_question(Intent.COMPARE, interventions=(_CLOSE,)))

        assert "unchanged" in _builds(plan)["base"].purpose

    def test_the_rationale_names_the_phase_intent_and_arms(self) -> None:
        plan = _plan(_question(Intent.COMPARE, interventions=(_CLOSE,)))

        assert "Phase 0" in plan.rationale
        assert "compare" in plan.rationale
        assert "base, treatment" in plan.rationale
