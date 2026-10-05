"""Writes `review.html`: the review page with the 54 proposed plans embedded, delicate ones first.

Each item carries the concept's gold `Question` in short form, the plan's steps as one line each,
the flags that make a plan delicate and the plan itself as JSON (the page edits it to correct).

    python -m eval.plan_bank.annotation.build
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.plan_bank.annotation.review import FORMAT
from eval.plan_bank.bank import load_plans, planned_concepts
from eval.request_bank.concepts import SPLITS
from resto.application.schemas import adapter_for
from resto.domain.value_objects.arm import BASE_ARM, contains
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    PlanStep,
    RerouteDemandStep,
    RunSimulationStep,
    StudyPlan,
)

HERE = Path(__file__).parent
TEMPLATE = HERE / "template.html"
OUTPUT = HERE / "review.html"
_PLACEHOLDER = "/*__ITEMS__*/[]"
_FORMAT_PLACEHOLDER = "/*__FORMAT__*/"


def flags_of(question: Question, plan: StudyPlan) -> list[str]:
    flags: list[str] = []
    if len(plan.arms) > 1:
        flags.append("multi_arm")
    if any(isinstance(s, DeriveNetworkStep) for s in plan.steps):
        flags.append("derive_network")
    arms = question.effective_arms
    if question.intent is Intent.COUNTERFACTUAL and any(
        contains(a, b) for a in arms for b in arms if a is not b
    ):
        flags.append("nested_counterfactual")
    if any(isinstance(s, ObtainDemandStep) and s.demand_ref is None for s in plan.steps):
        flags.append("no_demand_ref")
    if len(plan.steps) == 1 and isinstance(plan.steps[0], ObtainNetworkStep):
        flags.append("network_only")
    return flags


def _ref(value: object) -> str:
    step = getattr(value, "step", None)
    return f"step {step}" if step is not None else str(value)


def step_line(step: PlanStep) -> str:
    if isinstance(step, ObtainNetworkStep):
        return f"obtain_network: {step.network_ref!r}"
    if isinstance(step, ObtainDemandStep):
        return f"obtain_demand on {_ref(step.network_id)}: demand_ref={step.demand_ref!r}"
    if isinstance(step, DeriveNetworkStep):
        mods = "; ".join(type(m).__name__ for m in step.modifications)
        return f"derive_network from {_ref(step.base_network_id)}: {mods}"
    if isinstance(step, RerouteDemandStep):
        return f"reroute_demand {_ref(step.demand_id)} on {_ref(step.network_id)}"
    if isinstance(step, BuildScenarioStep):
        return (
            f"build_scenario arm={step.arm} role={step.role} on network "
            f"{_ref(step.network_id)}, demand {_ref(step.demand_id)}, "
            f"{len(step.interventions)} intervention(s)"
        )
    if isinstance(step, RunSimulationStep):
        return f"run_simulation {_ref(step.scenario_id)}"
    return type(step).__name__


def _question_summary(q: Question) -> dict[str, Any]:
    return {
        "text": q.text,
        "intent": q.intent.value,
        "network_ref": q.network_ref,
        "demand_ref": q.demand_ref,
        "arms": [a.label for a in q.effective_arms] or [BASE_ARM],
        "contrasts": [f"{c.treatment} vs {c.reference}" for c in q.effective_contrasts],
        "network_only": q.network_only,
    }


def plan_items() -> list[dict[str, Any]]:
    plans = load_plans()
    adapter = adapter_for(StudyPlan)
    items: list[dict[str, Any]] = []
    for concept in planned_concepts():
        question = concept.gold
        assert isinstance(question, Question)
        plan = plans[concept.id]
        items.append(
            {
                "concept_id": concept.id,
                "split": SPLITS[concept.id],
                "question": _question_summary(question),
                "rationale": plan.rationale,
                "steps": [step_line(s) for s in plan.steps],
                "flags": flags_of(question, plan),
                "plan": adapter.dump_python(plan, mode="json"),
            }
        )
    items.sort(key=lambda i: (-len(i["flags"]), i["concept_id"]))
    return items


def render(template: str, items: list[dict[str, Any]]) -> str:
    if _PLACEHOLDER not in template:
        raise ValueError(f"template has no {_PLACEHOLDER} placeholder")
    # `</` is escaped so a question text can never close the <script> element.
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return template.replace(_PLACEHOLDER, payload).replace(
        _FORMAT_PLACEHOLDER + '""', json.dumps(FORMAT)
    )


def main() -> None:
    items = plan_items()
    OUTPUT.write_text(render(TEMPLATE.read_text(encoding="utf-8"), items), encoding="utf-8")
    print(f"{OUTPUT} written with {len(items)} plans")


if __name__ == "__main__":
    main()
