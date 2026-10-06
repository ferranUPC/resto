"""The plan bank: one gold `StudyPlan` per concept that has a gold `Question`, keyed by concept id
and stored in `plans.json` with the same `TypeAdapter` the framework uses.

The stored plans are what the planner (`resto.domain.services.planner`) returns, kept as a
reviewed regression snapshot (r13 ticket 04): a change in the rules shows up as a diff of
`plans.json`. The study window is not stored: it is computed from the gold `Question` with
`study_window`.
Regenerate the file with `python -m eval.plan_bank.bank` after a reviewed change, unless the
review corrected plans (`corrected.json`): regenerating would overwrite the corrections.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.request_bank.concepts import CONCEPTS, SPLITS, Concept, concept_by_id
from resto.application.schemas import adapter_for
from resto.domain.services.experiment_design import study_window
from resto.domain.services.planner import PlanningContext, plan_study
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.study_plan import StudyPlan
from resto.domain.value_objects.time_window import TimeWindow

PLANS_PATH = Path(__file__).parent / "plans.json"
CORRECTED_PATH = Path(__file__).parent / "corrected.json"


def planned_concepts(concepts: tuple[Concept, ...] = CONCEPTS) -> list[Concept]:
    """The concepts whose gold is a `Question`: ambiguous, unintelligible and out-of-scope
    concepts never reach the planner."""
    return [c for c in concepts if isinstance(c.gold, Question)]


def build_plans(concepts: tuple[Concept, ...] = CONCEPTS) -> dict[str, StudyPlan]:
    """Run the planner over every planned concept, in phase 0."""
    return {
        c.id: plan_study(c.gold, PlanningContext(phase=0))
        for c in planned_concepts(concepts)
        if isinstance(c.gold, Question)
    }


def dump_plans(plans: dict[str, StudyPlan]) -> str:
    adapter = adapter_for(StudyPlan)
    rows: dict[str, Any] = {
        concept_id: adapter.dump_python(plans[concept_id], mode="json")
        for concept_id in sorted(plans)
    }
    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def save_plans(plans: dict[str, StudyPlan], path: Path = PLANS_PATH) -> None:
    path.write_text(dump_plans(plans), encoding="utf-8")


def load_plans(path: Path = PLANS_PATH) -> dict[str, StudyPlan]:
    """Every stored plan is validated on load, so its own invariants check the gold."""
    adapter = adapter_for(StudyPlan)
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {concept_id: adapter.validate_python(row) for concept_id, row in rows.items()}


def load_corrected(path: Path = CORRECTED_PATH) -> dict[str, dict[str, str]]:
    """The concepts the maintainer corrected, per section (`plans`, `phase1`), each with the note
    that justifies the correction. The regeneration tests leave their gold fields out of the
    comparison with the planner; `eval.plan_bank.annotation.review` writes the file."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {"plans": dict(rows["plans"]), "phase1": dict(rows["phase1"])}


def save_corrected(corrected: dict[str, dict[str, str]], path: Path = CORRECTED_PATH) -> None:
    rows = {key: dict(sorted(corrected[key].items())) for key in ("plans", "phase1")}
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def concept_id_of(request_id: str) -> str:
    """A request id is its concept id (`R001`) or the concept id plus a variant key (`R001.ca`)."""
    concept = concept_by_id(request_id.split(".", 1)[0])
    known = {concept.id, *(concept.variant_id(v) for v in concept.variants)}
    if request_id not in known:
        raise KeyError(request_id)
    return concept.id


def split_of(request_id: str) -> str:
    return SPLITS[concept_id_of(request_id)]


def gold_plan_of(request_id: str, plans: dict[str, StudyPlan] | None = None) -> StudyPlan:
    """The gold plan of a request; raises `KeyError` when its concept has no plan."""
    stored = load_plans() if plans is None else plans
    return stored[concept_id_of(request_id)]


def window_for(request_id: str) -> TimeWindow | None:
    """The study window the Demand Generator is given, derived from the gold `Question`."""
    gold = concept_by_id(concept_id_of(request_id)).gold
    if not isinstance(gold, Question):
        raise KeyError(request_id)
    return study_window(gold)


if __name__ == "__main__":
    proposed = build_plans()
    save_plans(proposed)
    print(f"wrote {len(proposed)} plans to {PLANS_PATH}")
