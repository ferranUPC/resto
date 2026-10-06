"""What r9 changed in the plans since the maintainer's earlier review (E3.7).

The earlier review was made on the plans of commit `29fcc09`, before the planner rules of r9 and
r13. `reviewed_snapshot.json` keeps the gold fields of those plans, so the review page can mark the
plans whose gold moved without git at run time. The projection is taken from the raw JSON: the old
file may not load with today's `StudyPlan` types.

The gold fields are those the plan is scored on: step kinds and dependencies, the arm and the
baseline-or-not role of each `build_scenario`, the modifications of each `derive_network` and
whether `obtain_demand` has a `demand_ref`. Free text, seeds and interventions are left out.

Rebuild the snapshot (only if the reference commit changes):

    git show 29fcc09:eval/plan_bank/plans.json > old-plans.json
    python -m eval.plan_bank.annotation.changes old-plans.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SNAPSHOT_PATH = Path(__file__).parent / "reviewed_snapshot.json"
REVIEWED_COMMIT = "29fcc09"
SOURCE = {
    "commit": REVIEWED_COMMIT,
    "file": "eval/plan_bank/plans.json",
    "what": "gold fields of the plans the maintainer reviewed before r9 (projection of changes.py)",
}


def _step_gold(step: dict[str, Any]) -> dict[str, Any]:
    kind = step["kind"]
    gold: dict[str, Any] = {"kind": kind, "depends_on": step.get("depends_on", [])}
    if kind == "build_scenario":
        gold["arm"] = step["arm"]
        gold["baseline"] = step["role"] == "baseline"
        gold["network_id"] = step["network_id"]
        gold["demand_id"] = step["demand_id"]
    elif kind == "derive_network":
        gold["modifications"] = step["modifications"]
        gold["base_network_id"] = step["base_network_id"]
    elif kind == "obtain_demand":
        gold["has_demand_ref"] = step.get("demand_ref") is not None
    return gold


def gold_projection(plan: dict[str, Any]) -> dict[str, Any]:
    """The gold fields of a plan given as raw JSON (one entry of `plans.json`)."""
    return {"network_id": plan["network_id"], "steps": [_step_gold(s) for s in plan["steps"]]}


def project_all(plans: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {concept_id: gold_projection(plans[concept_id]) for concept_id in sorted(plans)}


def load_snapshot(path: Path = SNAPSHOT_PATH) -> dict[str, dict[str, Any]]:
    return dict(json.loads(path.read_text(encoding="utf-8"))["plans"])


def save_snapshot(plans: dict[str, dict[str, Any]], path: Path = SNAPSHOT_PATH) -> None:
    rows = {"source": SOURCE, "plans": project_all(plans)}
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _arms(projection: dict[str, Any]) -> dict[str, bool]:
    return {s["arm"]: s["baseline"] for s in projection["steps"] if s["kind"] == "build_scenario"}


def _kinds(projection: dict[str, Any]) -> Counter[str]:
    return Counter(s["kind"] for s in projection["steps"])


def _field(projection: dict[str, Any], kind: str, key: str) -> list[Any]:
    return [s[key] for s in projection["steps"] if s["kind"] == kind]


def describe_changes(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    """A short list of what moved between two projections; empty when the gold is identical."""
    if old is None:
        return ["not in the reviewed snapshot"]
    if old == new:
        return []
    notes: list[str] = []
    old_arms, new_arms = _arms(old), _arms(new)
    if added := [a for a in new_arms if a not in old_arms]:
        notes.append(f"arms added: {', '.join(added)}")
    if removed := [a for a in old_arms if a not in new_arms]:
        notes.append(f"arms removed: {', '.join(removed)}")
    if roles := [a for a in new_arms if a in old_arms and new_arms[a] != old_arms[a]]:
        notes.append(f"baseline role changed: {', '.join(roles)}")
    new_steps, gone_steps = _kinds(new) - _kinds(old), _kinds(old) - _kinds(new)
    notes += [f"new step: {k}" + (f" x{n}" if n > 1 else "") for k, n in sorted(new_steps.items())]
    notes += [
        f"step gone: {k}" + (f" x{n}" if n > 1 else "") for k, n in sorted(gone_steps.items())
    ]
    old_mods = _field(old, "derive_network", "modifications")
    new_mods = _field(new, "derive_network", "modifications")
    if old_mods != new_mods and len(old_mods) == len(new_mods):
        notes.append("derive_network modifications changed")
    if _field(old, "obtain_demand", "has_demand_ref") != _field(
        new, "obtain_demand", "has_demand_ref"
    ):
        notes.append("demand_ref presence changed")
    return notes or ["dependencies or step order changed"]


def changes_by_concept(
    current: dict[str, dict[str, Any]], snapshot: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    """For each concept of the raw `current` plans, what changed against the snapshot."""
    return {
        concept_id: describe_changes(snapshot.get(concept_id), gold_projection(plan))
        for concept_id, plan in current.items()
    }


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        raise SystemExit("usage: python -m eval.plan_bank.annotation.changes <old plans.json>")
    save_snapshot(json.loads(Path(argv[0]).read_text(encoding="utf-8")))
    print(f"wrote {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])
