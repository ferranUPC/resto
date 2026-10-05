"""Applies an exported plan review to the bank file (E3.7 ticket 03).

The review page exports one row per concept: `accepted` keeps the proposal, `corrected` carries the
maintainer's replacement `StudyPlan` as JSON. Every plan of the bank must be reviewed, once. The
result is one gold per concept; it is written with `save_plans`, and the corrected concepts with
their notes go to `corrected.json`, which the regeneration tests read to skip their gold fields.

    python -m eval.plan_bank.annotation.review path/to/plan-review.json

The `phase1` key of the export holds the same rows for the phase-1 cases (`eval.plan_bank.phase1`):
every case reviewed once, and a corrected plan must still pass the plan validation's coverage check
for the case's context. `apply_review` ignores that key; `main` applies both.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from eval.plan_bank.bank import PLANS_PATH, load_plans, save_corrected, save_plans
from eval.plan_bank.phase1 import (
    PHASE1_PATH,
    Phase1Case,
    load_phase1,
    phase1_question,
    save_phase1,
)

# No public coverage check exists: `plan_problems` needs repositories a bank does not have.
from resto.application.executor.plan_validation import _coverage_problems  # noqa: PLC2701
from resto.application.schemas import adapter_for
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.question import Question
from resto.domain.value_objects.study_plan import BuildScenarioStep, DeriveNetworkStep, StudyPlan

FORMAT = "resto-plan-review/v1"
REVIEWED = ("accepted", "corrected")


def _rows(review: dict[str, Any], key: str, known: set[str]) -> dict[str, dict[str, Any]]:
    """The review rows under `key`, one per concept, covering exactly `known`."""
    if review.get("format") != FORMAT:
        raise ValueError(f"not a plan review export: format must be {FORMAT!r}")
    rows: dict[str, dict[str, Any]] = {}
    for row in review.get(key, []):
        concept_id = row["concept_id"]
        if concept_id in rows:
            raise ValueError(f"{concept_id} is reviewed twice: one gold per concept")
        rows[concept_id] = row
    unknown = sorted(set(rows) - known)
    if unknown:
        raise ValueError(f"the review names concepts with no plan: {unknown}")
    missing = sorted(known - set(rows))
    if missing:
        raise ValueError(f"the review is missing concepts: {missing}")
    for concept_id in sorted(known):
        status = rows[concept_id].get("status")
        if status not in REVIEWED:
            raise ValueError(f"{concept_id} is not reviewed yet (status {status!r})")
        if status == "corrected" and not rows[concept_id].get("plan"):
            raise ValueError(f"{concept_id} is corrected but carries no plan")
    return rows


def _corrected(concept_id: str, row: dict[str, Any]) -> StudyPlan:
    try:
        return adapter_for(StudyPlan).validate_python(row["plan"])
    except ValidationError as err:
        raise ValueError(f"{concept_id}: the corrected plan is invalid: {err}") from err


def _phase0_problems(plan: StudyPlan, question: Question) -> list[str]:
    """The checks a bank can run without a database: the arms phase 0 needs, and one
    `derive_network` per distinct topology those arms use."""
    problems = _coverage_problems(plan, question, 0, set())
    topologies = {a.topology_changes for a in question.effective_arms if a.topology_changes}
    derived = sum(isinstance(s, DeriveNetworkStep) for s in plan.steps)
    if derived != len(topologies):
        problems.append(f"{derived} derive_network step(s) for {len(topologies)} topology(ies)")
    return problems


def corrected_notes(review: dict[str, Any], key: str) -> dict[str, str]:
    """The maintainer's note of each corrected row under `key`, to keep the justification."""
    return {
        row["concept_id"]: row.get("note") or ""
        for row in review.get(key, [])
        if row.get("status") == "corrected"
    }


def apply_review(plans: dict[str, StudyPlan], review: dict[str, Any]) -> dict[str, StudyPlan]:
    """The plans after the review: corrections replace proposals, accepted plans are kept. A
    corrected plan must cover the arms phase 0 needs and derive each topology once."""
    rows = _rows(review, "plans", set(plans))
    result: dict[str, StudyPlan] = {}
    for concept_id in sorted(plans):
        if rows[concept_id]["status"] == "accepted":
            result[concept_id] = plans[concept_id]
            continue
        plan = _corrected(concept_id, rows[concept_id])
        problems = _phase0_problems(plan, phase1_question(concept_id))
        if problems:
            raise ValueError(f"{concept_id}: the corrected plan is not a phase-0 plan: {problems}")
        result[concept_id] = plan
    return result


def apply_phase1_review(
    cases: dict[str, Phase1Case], review: dict[str, Any]
) -> dict[str, Phase1Case]:
    """The phase-1 cases after the review. A correction replaces the plan only: the context is what
    phase 0 realised. The corrected plan must cover what the phase still needs and repeat nothing
    the context realised."""
    rows = _rows(review, "phase1", set(cases))
    result: dict[str, Phase1Case] = {}
    for concept_id in sorted(cases):
        case = cases[concept_id]
        if rows[concept_id]["status"] == "corrected":
            plan = _corrected(concept_id, rows[concept_id])
            realised = {e.arm for e in case.context.experiments}
            problems = _coverage_problems(plan, phase1_question(concept_id), 1, realised)
            if any(
                isinstance(s, BuildScenarioStep) and s.role is ExperimentRole.BASELINE
                for s in plan.steps
            ):
                problems.append("a phase-1 plan has no baseline arm")
            if problems:
                raise ValueError(
                    f"{concept_id}: the corrected plan is not a phase-1 plan: {problems}"
                )
            case = Phase1Case(case.context, plan)
        result[concept_id] = case
    return result


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        raise SystemExit("usage: python -m eval.plan_bank.annotation.review <export.json>")
    review = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    applied = apply_review(load_plans(), review)
    applied_phase1 = apply_phase1_review(load_phase1(), review)
    save_plans(applied)
    save_phase1(applied_phase1)
    save_corrected(
        {"plans": corrected_notes(review, "plans"), "phase1": corrected_notes(review, "phase1")}
    )
    print(f"wrote {len(applied)} reviewed plans to {PLANS_PATH}")
    print(f"wrote {len(applied_phase1)} reviewed phase-1 cases to {PHASE1_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
