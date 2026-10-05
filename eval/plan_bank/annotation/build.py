"""Writes `review.html`: the review page with the 54 proposed plans embedded, delicate ones first,
and the phase-1 cases in a section of their own.

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
from eval.plan_bank.phase1 import load_phase1, phase1_question
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
_PHASE1_PLACEHOLDER = "/*__PHASE1__*/[]"
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


def _item(concept_id: str, question: Question, plan: StudyPlan, **extra: Any) -> dict[str, Any]:
    return {
        "concept_id": concept_id,
        "split": SPLITS[concept_id],
        "question": _question_summary(question),
        "rationale": plan.rationale,
        "steps": [step_line(s) for s in plan.steps],
        "plan": adapter_for(StudyPlan).dump_python(plan, mode="json"),
        **extra,
    }


def plan_items() -> list[dict[str, Any]]:
    plans = load_plans()
    items = [
        _item(c.id, q, plans[c.id], flags=flags_of(q, plans[c.id]))
        for c in planned_concepts()
        if isinstance(q := c.gold, Question)
    ]
    items.sort(key=lambda i: (-len(i["flags"]), i["concept_id"]))
    return items


def phase1_items() -> list[dict[str, Any]]:
    """One item per phase-1 case: the question, the arms phase 0 realised and the gold plan."""
    return [
        _item(
            cid,
            phase1_question(cid),
            case.plan,
            realised=[e.arm for e in case.context.experiments],
            flags=[],
        )
        for cid, case in sorted(load_phase1().items())
    ]


def _embed(items: list[dict[str, Any]]) -> str:
    # `</` is escaped so a question text can never close the <script> element.
    return json.dumps(items, ensure_ascii=False).replace("</", "<\\/")


def render(
    template: str, items: list[dict[str, Any]], phase1: list[dict[str, Any]] | None = None
) -> str:
    for placeholder in (_PLACEHOLDER, _PHASE1_PLACEHOLDER):
        if placeholder not in template:
            raise ValueError(f"template has no {placeholder} placeholder")
    return (
        template.replace(_PLACEHOLDER, _embed(items))
        .replace(_PHASE1_PLACEHOLDER, _embed(phase1 or []))
        .replace(_FORMAT_PLACEHOLDER + '""', json.dumps(FORMAT))
    )


def main() -> None:
    items, phase1 = plan_items(), phase1_items()
    OUTPUT.write_text(render(TEMPLATE.read_text(encoding="utf-8"), items, phase1), encoding="utf-8")
    print(f"{OUTPUT} written with {len(items)} plans and {len(phase1)} phase-1 cases")


if __name__ == "__main__":
    main()
