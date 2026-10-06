"""Unit tests for the phase-1 section of the plan bank (E3.7 ticket 04).
No database, no LLM, no network."""

from __future__ import annotations

import pytest
from eval.plan_bank.bank import load_corrected, load_plans, planned_concepts
from eval.plan_bank.phase1 import (
    PHASE1_IDS,
    PHASE1_PATH,
    build_phase1,
    dump_phase1,
    load_phase1,
    phase1_concepts,
)
from eval.request_bank.concepts import concept_by_id

from resto.application.executor.plan_validation import _coverage_problems
from resto.domain.services.experiment_design import needed_arms
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import BuildScenarioStep, ObtainNetworkStep

CASES = load_phase1()
COUNTERFACTUAL_IDS = sorted(
    c.id
    for c in planned_concepts()
    if c.id in PHASE1_IDS and isinstance(c.gold, Question) and c.gold.intent is Intent.COMPARE
)


def _question(concept_id: str) -> Question:
    gold = concept_by_id(concept_id).gold
    assert isinstance(gold, Question)
    return gold


def test_one_case_per_counterfactual_concept() -> None:
    assert sorted(CASES) == COUNTERFACTUAL_IDS
    assert sorted(c.id for c in phase1_concepts()) == COUNTERFACTUAL_IDS
    assert len(CASES) == len(COUNTERFACTUAL_IDS)


@pytest.mark.parametrize("concept_id", COUNTERFACTUAL_IDS)
def test_gold_passes_the_plan_validations_coverage_check(concept_id: str) -> None:
    case = CASES[concept_id]
    realised = {e.arm for e in case.context.experiments}
    assert case.context.phase == 1
    assert _coverage_problems(case.plan, _question(concept_id), 1, realised) == []


@pytest.mark.parametrize("concept_id", COUNTERFACTUAL_IDS)
def test_gold_holds_only_treatment_arms_and_repeats_no_realised_arm(concept_id: str) -> None:
    case = CASES[concept_id]
    realised = {e.arm for e in case.context.experiments}
    builds = [s for s in case.plan.steps if isinstance(s, BuildScenarioStep)]
    assert builds
    assert not realised & set(case.plan.arms)
    assert all(b.role is not ExperimentRole.BASELINE for b in builds)
    assert isinstance(case.plan.steps[0], ObtainNetworkStep)


@pytest.mark.parametrize("concept_id", COUNTERFACTUAL_IDS)
def test_context_is_what_phase_0_realised(concept_id: str) -> None:
    question = _question(concept_id)
    realised = [e.arm for e in CASES[concept_id].context.experiments]
    phase0 = [s.arm for s in load_plans()[concept_id].steps if isinstance(s, BuildScenarioStep)]
    assert realised == [arm for arm in phase0 if arm in realised]  # a prefix-ordered subset
    assert set(realised) < set(phase0) == set(needed_arms(question, 0))  # the treatments are left
    assert set(realised) | set(CASES[concept_id].plan.arms) == set(needed_arms(question, 1))


def test_stored_file_is_what_the_rules_script_builds_and_round_trips() -> None:
    built = build_phase1()
    corrected = set(load_corrected()["phase1"])  # the maintainer's gold, not the proposal
    assert {c: v.context for c, v in built.items()} == {c: v.context for c, v in CASES.items()}
    assert {c: v for c, v in built.items() if c not in corrected} == {
        c: v for c, v in CASES.items() if c not in corrected
    }
    assert PHASE1_PATH.read_text(encoding="utf-8") == dump_phase1(CASES)
