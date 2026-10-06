"""Unit tests for the "changed since last review" mark of the plan review page (E3.7).
The snapshot is the gold projection of the plans of commit 29fcc09; no git, no LLM."""

from __future__ import annotations

import copy
import json
from typing import Any

from eval.plan_bank.annotation.build import OUTPUT, TEMPLATE, plan_items, render
from eval.plan_bank.annotation.changes import (
    REVIEWED_COMMIT,
    SNAPSHOT_PATH,
    changes_by_concept,
    describe_changes,
    gold_projection,
    load_snapshot,
    project_all,
    save_snapshot,
)
from eval.plan_bank.bank import PLANS_PATH

CURRENT: dict[str, dict[str, Any]] = json.loads(PLANS_PATH.read_text(encoding="utf-8"))
SNAPSHOT = load_snapshot()


def _plan_with_derive() -> tuple[str, dict[str, Any]]:
    concept_id = next(
        c for c, p in CURRENT.items() if any(s["kind"] == "derive_network" for s in p["steps"])
    )
    return concept_id, CURRENT[concept_id]


def test_the_snapshot_has_its_provenance_and_covers_the_reviewed_plans():
    raw = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert raw["source"]["commit"] == REVIEWED_COMMIT == "29fcc09"
    assert set(raw["plans"]) == set(CURRENT)


def test_the_projection_is_stable():
    plan = CURRENT["R003"]
    assert gold_projection(plan) == gold_projection(copy.deepcopy(plan))
    assert project_all(CURRENT) == project_all(copy.deepcopy(CURRENT))
    assert json.dumps(project_all(CURRENT)) == json.dumps(project_all(CURRENT))


def test_the_projection_keeps_gold_and_drops_free_text():
    plan = copy.deepcopy(CURRENT["R003"])
    plan["rationale"] = "other words"
    for step in plan["steps"]:
        step["purpose"] = "other words"
        if step["kind"] == "build_scenario":
            step["interventions"] = []
        if step["kind"] == "obtain_demand":
            step["demand_ref"] = "another phrase"
            step["seed"] = 99
    assert gold_projection(plan) == gold_projection(CURRENT["R003"])


def test_saving_a_snapshot_writes_the_projection_with_its_source(tmp_path):
    out = tmp_path / "snapshot.json"
    save_snapshot(CURRENT, out)
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["plans"] == project_all(CURRENT)
    assert raw["source"]["commit"] == REVIEWED_COMMIT


def test_an_identical_plan_is_not_marked():
    snapshot = project_all(CURRENT)
    assert changes_by_concept(CURRENT, snapshot) == {c: [] for c in CURRENT}


def test_a_plan_with_other_gold_is_marked_and_says_what_changed():
    snapshot = project_all(CURRENT)
    concept_id = "R003"
    plan = copy.deepcopy(CURRENT[concept_id])
    arms = [s for s in plan["steps"] if s["kind"] == "build_scenario"]
    arms[1]["arm"] = "renamed"
    changes = changes_by_concept({**CURRENT, concept_id: plan}, snapshot)
    assert changes[concept_id] == ["arms added: renamed", "arms removed: closure"]
    assert all(not v for k, v in changes.items() if k != concept_id)


def test_a_new_step_is_reported():
    current = gold_projection(CURRENT["R003"])
    plan = copy.deepcopy(CURRENT["R003"])
    plan["steps"] = [s for s in plan["steps"] if s["kind"] != "run_simulation"]
    assert describe_changes(gold_projection(plan), current) == ["new step: run_simulation x3"]


def test_free_text_changes_do_not_mark_a_plan():
    snapshot = project_all(CURRENT)
    plan = copy.deepcopy(CURRENT["R003"])
    plan["rationale"] = "reworded"
    assert changes_by_concept({"R003": plan}, snapshot) == {"R003": []}


def test_a_plan_missing_from_the_snapshot_is_marked():
    assert describe_changes(None, gold_projection(CURRENT["R003"])) != []


def test_derive_network_modifications_changes_are_reported():
    concept_id, plan = _plan_with_derive()
    other = copy.deepcopy(plan)
    next(s for s in other["steps"] if s["kind"] == "derive_network")["modifications"] = []
    assert describe_changes(gold_projection(plan), gold_projection(other)) == [
        "derive_network modifications changed"
    ]


def test_the_demand_ref_presence_is_gold_but_its_wording_is_not():
    other = copy.deepcopy(CURRENT["R003"])
    next(s for s in other["steps"] if s["kind"] == "obtain_demand")["demand_ref"] = None
    assert describe_changes(gold_projection(CURRENT["R003"]), gold_projection(other)) == [
        "demand_ref presence changed"
    ]


def test_every_item_of_the_page_carries_its_changes_against_the_snapshot():
    items = {i["concept_id"]: i for i in plan_items()}
    expected = changes_by_concept(CURRENT, SNAPSHOT)
    assert {c: i["changes"] for c, i in items.items()} == expected
    assert any(i["changes"] for i in items.values())  # r9 and r13 moved some of the 54


def test_delicate_plans_still_come_first_whatever_changed():
    counts = [len(i["flags"]) for i in plan_items()]
    assert counts == sorted(counts, reverse=True)


def test_the_rendered_page_names_the_reviewed_commit_and_has_the_changed_controls():
    page = render(TEMPLATE.read_text(encoding="utf-8"), [])
    assert f'"{REVIEWED_COMMIT}"' in page
    assert "changed since last review" in page
    assert "onlyChanged" in page
    assert "__SNAPSHOT_COMMIT__" not in page


def test_the_committed_page_is_up_to_date():
    expected = render(TEMPLATE.read_text(encoding="utf-8"), plan_items())
    assert OUTPUT.read_text(encoding="utf-8") == expected
