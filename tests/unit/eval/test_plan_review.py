"""Unit tests for the plan review page and the application of its export (E3.7 ticket 03).
The reviews here are synthetic: the maintainer's real review is not part of the repo."""

from __future__ import annotations

import json
from typing import Any

import pytest
from eval.plan_bank.annotation.build import TEMPLATE, phase1_items, plan_items, render
from eval.plan_bank.annotation.review import (
    FORMAT,
    apply_phase1_review,
    apply_review,
    corrected_notes,
)
from eval.plan_bank.bank import load_plans, planned_concepts
from eval.plan_bank.phase1 import Phase1Case, load_phase1

from resto.application.schemas import adapter_for
from resto.domain.value_objects.study_plan import ObtainNetworkStep, StudyPlan

PLANS = load_plans()
CASES = load_phase1()


def _dump(plan: StudyPlan) -> dict[str, Any]:
    return adapter_for(StudyPlan).dump_python(plan, mode="json")


def _review(
    status: str = "accepted", overrides: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    rows = []
    for concept_id in sorted(PLANS):
        row: dict[str, Any] = {"concept_id": concept_id, "status": status, "note": "", "plan": None}
        row.update((overrides or {}).get(concept_id, {}))
        rows.append(row)
    return {"format": FORMAT, "reviewer": "t", "exported_at": "t", "plans": rows, "phase1": []}


# --- the page ------------------------------------------------------------------------------------


def test_the_page_lists_every_planned_concept_once():
    items = plan_items()
    assert sorted(i["concept_id"] for i in items) == sorted(c.id for c in planned_concepts())
    assert len(items) == len(planned_concepts())


def test_each_item_has_question_steps_and_flags():
    item = plan_items()[0]
    assert {"concept_id", "question", "steps", "flags", "plan"} <= set(item)
    assert item["steps"] and item["question"]


def test_delicate_plans_come_first():
    counts = [len(i["flags"]) for i in plan_items()]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > 0


def test_flags_mark_the_delicate_shapes():
    by_id = {i["concept_id"]: i for i in plan_items()}
    for concept_id, plan in PLANS.items():
        flags = set(by_id[concept_id]["flags"])
        assert ("multi_arm" in flags) == (len(plan.arms) > 1)
        assert ("derive_network" in flags) == any(s.kind == "derive_network" for s in plan.steps)
        only_network = len(plan.steps) == 1 and isinstance(plan.steps[0], ObtainNetworkStep)
        assert ("network_only" in flags) == only_network
    assert any("no_demand_ref" in i["flags"] for i in by_id.values())
    assert any("nested_arms" in i["flags"] for i in by_id.values())


def test_the_rendered_page_embeds_the_items_and_cannot_be_closed_by_them():
    items = [{"concept_id": "R1", "question": "</script><b>x", "steps": [], "flags": []}]
    page = render(TEMPLATE.read_text(encoding="utf-8"), items)
    assert "</script><b>x" not in page
    assert "/*__ITEMS__*/[]" not in page
    assert FORMAT in page


def test_the_template_leaves_a_phase_one_section():
    assert 'id="phase1"' in TEMPLATE.read_text(encoding="utf-8")


# --- applying a review ---------------------------------------------------------------------------


def test_accepting_every_plan_keeps_the_proposals():
    assert apply_review(PLANS, _review()) == PLANS


def test_a_corrected_plan_replaces_its_proposal_and_only_that_one():
    base = _dump(PLANS["R001"])
    base["rationale"] = "corrected by hand"
    review = _review(overrides={"R001": {"status": "corrected", "plan": base, "note": "n"}})
    result = apply_review(PLANS, review)
    assert result["R001"].rationale == "corrected by hand"
    assert {k: v for k, v in result.items() if k != "R001"} == {
        k: v for k, v in PLANS.items() if k != "R001"
    }


def test_a_corrected_plan_must_be_a_valid_plan():
    broken = _dump(PLANS["R001"])
    broken["steps"] = []
    review = _review(overrides={"R001": {"status": "corrected", "plan": broken}})
    with pytest.raises(ValueError):
        apply_review(PLANS, review)


def test_a_corrected_row_without_a_plan_is_refused():
    with pytest.raises(ValueError, match="R001"):
        apply_review(PLANS, _review(overrides={"R001": {"status": "corrected"}}))


def test_a_pending_plan_is_refused():
    with pytest.raises(ValueError, match="R001"):
        apply_review(PLANS, _review(overrides={"R001": {"status": "pending"}}))


def test_one_gold_per_concept():
    review = _review()
    review["plans"].append(dict(review["plans"][0]))
    with pytest.raises(ValueError, match="twice"):
        apply_review(PLANS, review)


def test_a_review_must_cover_exactly_the_bank_concepts():
    review = _review()
    review["plans"].pop()
    with pytest.raises(ValueError, match="missing"):
        apply_review(PLANS, review)
    review = _review()
    review["plans"][0]["concept_id"] = "R999"
    with pytest.raises(ValueError):
        apply_review(PLANS, review)


def test_a_foreign_export_is_refused():
    review = _review()
    review["format"] = "something-else"
    with pytest.raises(ValueError, match="format"):
        apply_review(PLANS, review)


def test_the_applied_review_round_trips_through_the_bank_file(tmp_path):
    from eval.plan_bank.bank import load_plans as load
    from eval.plan_bank.bank import save_plans

    path = tmp_path / "plans.json"
    save_plans(apply_review(PLANS, _review()), path)
    assert load(path) == PLANS
    assert json.loads(path.read_text(encoding="utf-8")).keys() == {*PLANS}


# --- the phase-1 section -------------------------------------------------------------------------


def _review1(
    status: str = "accepted", overrides: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    rows = []
    for concept_id in sorted(CASES):
        row: dict[str, Any] = {"concept_id": concept_id, "status": status, "note": "", "plan": None}
        row.update((overrides or {}).get(concept_id, {}))
        rows.append(row)
    review = _review()
    review["phase1"] = rows
    return review


def test_the_page_lists_every_phase_one_case_once_with_its_realised_arms():
    items = phase1_items()
    assert sorted(i["concept_id"] for i in items) == sorted(CASES)
    assert len(items) == len(CASES)
    for item in items:
        case = CASES[item["concept_id"]]
        assert item["realised"] == [e.arm for e in case.context.experiments]
        assert item["steps"] and item["question"]


def test_the_rendered_page_embeds_the_phase_one_items():
    items = [{"concept_id": "R1", "question": "x", "steps": [], "flags": []}]
    phase1 = [{"concept_id": "R9", "question": "</script>", "realised": [], "steps": []}]
    page = render(TEMPLATE.read_text(encoding="utf-8"), items, phase1)
    assert '"R9"' in page
    assert '</script>"' not in page
    assert "/*__PHASE1__*/[]" not in page


def test_accepting_every_phase_one_case_keeps_them():
    assert apply_phase1_review(CASES, _review1()) == CASES


def test_a_corrected_phase_one_plan_replaces_its_case_plan():
    plan = _dump(CASES["R001"].plan)
    plan["rationale"] = "corrected by hand"
    result = apply_phase1_review(
        CASES, _review1(overrides={"R001": {"status": "corrected", "plan": plan}})
    )
    assert result["R001"].plan.rationale == "corrected by hand"
    assert result["R001"].context == CASES["R001"].context
    assert {k: v for k, v in result.items() if k != "R001"} == {
        k: v for k, v in CASES.items() if k != "R001"
    }


def test_a_corrected_phase_one_plan_may_not_repeat_a_realised_arm():
    case: Phase1Case = CASES["R001"]
    phase0 = PLANS["R001"]
    repeated = _dump(case.plan)
    repeated["steps"] = _dump(phase0)["steps"]
    review = _review1(overrides={"R001": {"status": "corrected", "plan": repeated}})
    with pytest.raises(ValueError, match="R001"):
        apply_phase1_review(CASES, review)


def test_every_phase_one_case_must_be_reviewed_once():
    with pytest.raises(ValueError, match="missing"):
        apply_phase1_review(CASES, {**_review1(), "phase1": []})
    twice = _review1()
    twice["phase1"].append(dict(twice["phase1"][0]))
    with pytest.raises(ValueError, match="twice"):
        apply_phase1_review(CASES, twice)
    with pytest.raises(ValueError, match="R001"):
        apply_phase1_review(CASES, _review1(overrides={"R001": {"status": "pending"}}))


def test_phase_zero_review_ignores_the_phase_one_rows():
    assert apply_review(PLANS, _review1()) == PLANS


# --- validation of corrections, notes ------------------------------------------------------------


def test_a_corrected_phase_zero_plan_must_cover_the_needed_arms():
    plan = _dump(PLANS["R001"])
    plan["steps"] = plan["steps"][:1]
    review = _review(overrides={"R001": {"status": "corrected", "plan": plan}})
    with pytest.raises(ValueError, match="phase-0"):
        apply_review(PLANS, review)


def test_a_corrected_phase_zero_plan_derives_each_topology_once():
    concept_id = next(
        c for c, p in PLANS.items() if any(s.kind == "derive_network" for s in p.steps)
    )
    plan = _dump(PLANS[concept_id])
    plan["steps"] = [s for s in plan["steps"] if s["kind"] != "derive_network"]
    review = _review(overrides={concept_id: {"status": "corrected", "plan": plan}})
    with pytest.raises(ValueError):
        apply_review(PLANS, review)


def test_a_corrected_phase_one_plan_may_not_hold_a_baseline():
    plan = _dump(CASES["R001"].plan)
    for step in plan["steps"]:
        if step["kind"] == "build_scenario":
            step["role"] = "baseline"
    review = _review1(overrides={"R001": {"status": "corrected", "plan": plan}})
    with pytest.raises(ValueError, match="R001"):
        apply_phase1_review(CASES, review)


def test_the_note_of_each_corrected_row_is_kept():
    review = _review1(overrides={"R001": {"status": "corrected", "note": "why"}})
    assert corrected_notes(review, "plans") == {}
    assert corrected_notes(review, "phase1") == {"R001": "why"}
