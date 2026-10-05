"""Applies an exported plan review to the bank file (E3.7 ticket 03).

The review page exports one row per concept: `accepted` keeps the proposal, `corrected` carries the
maintainer's replacement `StudyPlan` as JSON. Every plan of the bank must be reviewed, once. The
result is one gold per concept; it is written with `save_plans` and the regeneration test is then
updated on purpose.

    python -m eval.plan_bank.annotation.review path/to/plan-review.json

The `phase1` key of the export is reserved for the phase-1 cases (ticket 04) and ignored here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from eval.plan_bank.bank import PLANS_PATH, load_plans, save_plans
from resto.application.schemas import adapter_for
from resto.domain.value_objects.study_plan import StudyPlan

FORMAT = "resto-plan-review/v1"
REVIEWED = ("accepted", "corrected")


def apply_review(plans: dict[str, StudyPlan], review: dict[str, Any]) -> dict[str, StudyPlan]:
    """The plans after the review: corrections replace proposals, accepted plans are kept."""
    if review.get("format") != FORMAT:
        raise ValueError(f"not a plan review export: format must be {FORMAT!r}")
    rows: dict[str, dict[str, Any]] = {}
    for row in review.get("plans", []):
        concept_id = row["concept_id"]
        if concept_id in rows:
            raise ValueError(f"{concept_id} is reviewed twice: one gold per concept")
        rows[concept_id] = row
    unknown = sorted(set(rows) - set(plans))
    if unknown:
        raise ValueError(f"the review names concepts with no plan: {unknown}")
    missing = sorted(set(plans) - set(rows))
    if missing:
        raise ValueError(f"the review is missing concepts: {missing}")
    adapter = adapter_for(StudyPlan)
    result: dict[str, StudyPlan] = {}
    for concept_id in sorted(plans):
        row = rows[concept_id]
        status = row.get("status")
        if status not in REVIEWED:
            raise ValueError(f"{concept_id} is not reviewed yet (status {status!r})")
        if status == "accepted":
            result[concept_id] = plans[concept_id]
            continue
        if not row.get("plan"):
            raise ValueError(f"{concept_id} is corrected but carries no plan")
        try:
            result[concept_id] = adapter.validate_python(row["plan"])
        except ValidationError as err:
            raise ValueError(f"{concept_id}: the corrected plan is invalid: {err}") from err
    return result


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        raise SystemExit("usage: python -m eval.plan_bank.annotation.review <export.json>")
    review = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    applied = apply_review(load_plans(), review)
    save_plans(applied)
    print(f"wrote {len(applied)} reviewed plans to {PLANS_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
