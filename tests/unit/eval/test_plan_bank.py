"""Unit tests for the frozen plan bank (eval/plan_bank/bank.py, work-plan E3.7).
No database, no LLM, no network."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from eval.plan_bank.bank import (
    PLANS_PATH,
    basis_drift,
    build_plans,
    concept_id_of,
    dump_plans,
    gold_plan_of,
    load_corrected,
    load_corrected_basis,
    load_plans,
    planned_concepts,
    question_basis,
    save_corrected,
    split_of,
    window_for,
)
from eval.request_bank.concepts import CONCEPTS, SPLITS, Category, Concept, concept_by_id

from resto.domain.services.experiment_design import needed_arms, study_window
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    PlanStep,
    StudyPlan,
)
from resto.domain.value_objects.time_window import TimeWindow

PLANS = load_plans()
QUESTION_IDS = {c.id for c in CONCEPTS if isinstance(c.gold, Question)}


def _category_counts(concept_ids: set[str]) -> dict[Category, int]:
    counts: dict[Category, int] = {}
    for concept_id in concept_ids:
        category = concept_by_id(concept_id).category
        counts[category] = counts.get(category, 0) + 1
    return counts


def _gold(step: PlanStep) -> tuple[object, ...]:
    """What the plan is scored on (spec, "What is gold"); `purpose`, `rationale`, the wording of
    the references, `seed`, `goals` and the order of independent steps are left out."""
    kind = type(step).__name__
    if isinstance(step, BuildScenarioStep):
        return (
            kind,
            step.arm,
            step.role is ExperimentRole.BASELINE,
            step.interventions,
            step.network_id,
            step.demand_id,
            step.depends_on,
        )
    if isinstance(step, DeriveNetworkStep):
        return (kind, step.modifications, step.base_network_id, step.depends_on)
    if isinstance(step, ObtainDemandStep):
        return (kind, step.demand_ref is not None, step.depends_on)
    return (kind, step.depends_on)


def _gold_of(plan: StudyPlan) -> tuple[object, ...]:
    return (plan.network_id, tuple(_gold(s) for s in plan.steps))


class TestScope:
    def test_the_bank_holds_exactly_the_concepts_with_a_gold_question(self) -> None:
        assert set(PLANS) == QUESTION_IDS

    def test_counts_by_category_and_split_match_the_spec(self) -> None:
        assert _category_counts(set(PLANS)) == {
            Category.SINGLE: 31,
            Category.MULTI_ARM: 14,
            Category.COMBINED: 6,
            Category.ADVERSARIAL: 3,
        }
        splits = [SPLITS[cid] for cid in PLANS]
        assert (splits.count("dev"), splits.count("held_out")) == (36, 18)

    def test_no_ambiguous_unintelligible_or_out_of_scope_concept_has_a_plan(self) -> None:
        unplanned = {Category.AMBIGUOUS, Category.UNINTELLIGIBLE, Category.OUT_OF_SCOPE}
        assert not [c.id for c in CONCEPTS if c.category in unplanned and c.id in PLANS]


class TestStoredPlans:
    @pytest.mark.parametrize("concept_id", sorted(PLANS))
    def test_plan_starts_with_obtain_network_and_covers_the_needed_arms(
        self, concept_id: str
    ) -> None:
        plan = PLANS[concept_id]
        question = next(c.gold for c in CONCEPTS if c.id == concept_id)
        assert isinstance(question, Question)

        assert isinstance(plan.steps[0], ObtainNetworkStep)
        assert plan.arms == needed_arms(question, 0)

    @pytest.mark.parametrize("concept_id", sorted(PLANS))
    def test_build_steps_cover_exactly_the_needed_arms_once(self, concept_id: str) -> None:
        question = concept_by_id(concept_id).gold
        assert isinstance(question, Question)
        built = [s.arm for s in PLANS[concept_id].steps if isinstance(s, BuildScenarioStep)]

        assert sorted(built) == sorted(needed_arms(question, 0))

    def test_stored_gold_fields_are_what_the_rules_script_proposes_today(self) -> None:
        """A change in `needed_arms` or the plan types fails here and forces a review of the bank.
        Free text and step order are not compared, so the review can edit them. Regenerate with
        `python -m eval.plan_bank.bank` after a reviewed change, which overwrites those edits.
        Concepts listed in `corrected.json` are the maintainer's own gold and are skipped here;
        the invariants above still hold for them."""
        proposed = build_plans()
        assert set(proposed) == set(PLANS)
        corrected = set(load_corrected()["plans"])  # the maintainer's gold, not the proposal
        changed = [
            c for c in PLANS if c not in corrected and _gold_of(PLANS[c]) != _gold_of(proposed[c])
        ]
        assert not changed

    def test_corrected_concepts_are_bank_concepts(self) -> None:
        assert set(load_corrected()["plans"]) <= set(PLANS)

    def test_stored_file_round_trips_through_the_adapter(self) -> None:
        assert PLANS_PATH.read_text(encoding="utf-8") == dump_plans(PLANS)

    def test_corrected_concepts_still_rest_on_the_arms_and_window_the_maintainer_accepted(
        self,
    ) -> None:
        """`needed_arms` and `study_window` come from the gold `Question`, not from the plan, so a
        corrected plan goes stale if the `Question` changes. `corrected.json` records both when the
        review is applied (`basis`); empty today, as no plan is corrected."""
        assert basis_drift(load_corrected(), load_corrected_basis()) == []


def _windowed_concept() -> Concept:
    return next(
        c
        for c in planned_concepts()
        if isinstance(c.gold, Question)
        and c.gold.intent is Intent.COMPARE
        and study_window(c.gold) is not None
    )


def _corrected_with_basis(
    concept: Concept,
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    assert isinstance(concept.gold, Question)
    return {"plans": {concept.id: "why"}}, {concept.id: question_basis(concept.gold)}


class TestCorrectedBasis:
    """A synthetic corrected concept: the real `corrected.json` is not touched."""

    def test_an_unchanged_question_is_in_line_with_its_recorded_basis(self) -> None:
        concept = _windowed_concept()
        corrected, basis = _corrected_with_basis(concept)
        assert basis_drift(corrected, basis) == []

    def test_a_question_change_that_alters_the_needed_arms_is_reported(self) -> None:
        concept = _windowed_concept()
        corrected, basis = _corrected_with_basis(concept)
        assert isinstance(concept.gold, Question)
        changed = replace(concept, gold=replace(concept.gold, intent=Intent.DESCRIBE))
        assert needed_arms(changed.gold, 0) != needed_arms(concept.gold, 0)  # type: ignore[arg-type]

        problems = basis_drift(corrected, basis, (changed,))
        assert [p.split(":")[0] for p in problems] == [concept.id]

    def test_a_question_change_that_moves_the_study_window_is_reported(self) -> None:
        concept = _windowed_concept()
        corrected, basis = _corrected_with_basis(concept)
        assert isinstance(concept.gold, Question)

        def later(i: Intervention) -> Intervention:
            return i if i.window is None else replace(i, window=TimeWindow(i.window.start, 90000.0))

        moved = tuple(later(i) for i in concept.gold.interventions)
        arms = tuple(
            replace(a, interventions=tuple(later(i) for i in a.interventions))
            for a in concept.gold.arms
        )
        gold = replace(concept.gold, interventions=moved, arms=arms)
        assert study_window(gold) != study_window(concept.gold)

        assert basis_drift(corrected, basis, (replace(concept, gold=gold),))

    def test_a_corrected_concept_without_a_recorded_basis_is_reported(self) -> None:
        concept = _windowed_concept()
        corrected, _ = _corrected_with_basis(concept)
        assert basis_drift(corrected, {}) != []

    def test_the_basis_is_saved_beside_the_notes_and_the_old_format_still_loads(
        self, tmp_path: Path
    ) -> None:
        concept = _windowed_concept()
        corrected, basis = _corrected_with_basis(concept)
        path = tmp_path / "corrected.json"

        save_corrected(corrected, path)  # the original format: no `basis` key
        assert "basis" not in json.loads(path.read_text(encoding="utf-8"))
        assert load_corrected_basis(path) == {}

        save_corrected(corrected, path, basis=basis)
        assert load_corrected(path) == corrected
        assert load_corrected_basis(path) == json.loads(json.dumps(basis))


class TestLookup:
    def test_concept_id_of_a_variant_is_its_concept(self) -> None:
        assert concept_id_of("R001") == "R001"
        assert concept_id_of("R001.ca") == "R001"

    @pytest.mark.parametrize("request_id", ["R999.ca", "R001.zzz"])
    def test_unknown_concept_or_variant_raises(self, request_id: str) -> None:
        with pytest.raises(KeyError):
            concept_id_of(request_id)

    def test_variants_share_the_plan_and_split_of_their_concept(self) -> None:
        for concept in CONCEPTS:
            for spec in concept.variants:
                request_id = concept.variant_id(spec)
                assert split_of(request_id) == SPLITS[concept.id]
                if concept.id in PLANS:
                    assert gold_plan_of(request_id) == PLANS[concept.id]

    def test_concept_without_a_plan_raises(self) -> None:
        unplanned = next(c.id for c in CONCEPTS if c.id not in PLANS)
        with pytest.raises(KeyError):
            gold_plan_of(unplanned)

    def test_window_is_computed_from_the_gold_question(self) -> None:
        concept = next(c for c in CONCEPTS if isinstance(c.gold, Question))
        assert isinstance(concept.gold, Question)
        assert window_for(concept.id) == study_window(concept.gold)
