"""The phase-1 section of the plan bank (E3.7 ticket 04): one case per counterfactual concept.

Stopgap until E3.7 reworks this set (ADR-0038): phase 0 now plans every arm a question needs, so
the planner no longer leaves treatments for the Expert. The cases keep the old shape by building
their context locally: the realised arms are the reference side of the contrasts, and the case asks
for the treatments (ADR-0025 §2, replaced). A phase-1 case gives the Coordinator the question plus
a `PlanningContext` with the phase-0 experiments already realised, and its gold is the plan with
only the arms still missing: the treatments. It tests that the Coordinator does not repeat a
realised arm (`plan_validation._coverage_problems`).

The cases are stored in `phase1.json`, apart from the 54 phase-0 plans (`plans.json`), and do not
count towards them. The ids of the context (network, scenarios) are placeholders: a bank has no
database, and the scorer reads the arms, not the ids. Regenerate with `python -m
eval.plan_bank.phase1` after a reviewed change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.plan_bank.bank import load_plans, planned_concepts
from eval.plan_bank.propose import propose_plan
from eval.request_bank.concepts import Concept, concept_by_id
from resto.application.ports.agents.coordinator import PlanningContext
from resto.application.schemas import adapter_for
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.experiment import Experiment
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.study_plan import BuildScenarioStep, StudyPlan

PHASE1_PATH = Path(__file__).parent / "phase1.json"
PHASE = 1


@dataclass(frozen=True, slots=True)
class Phase1Case:
    context: PlanningContext
    plan: StudyPlan


def phase1_concepts() -> list[Concept]:
    """The concepts that get a phase-1 case: the counterfactual ones."""
    return [
        c
        for c in planned_concepts()
        if isinstance(c.gold, Question) and c.gold.intent is Intent.COUNTERFACTUAL
    ]


def phase1_question(concept_id: str) -> Question:
    gold = concept_by_id(concept_id).gold
    if not isinstance(gold, Question):
        raise KeyError(concept_id)
    return gold


def _reference_side(question: Question) -> tuple[str, ...]:
    """The reference side of every contrast, in the question's order (the retired phase-0 rule)."""
    contrasts = question.effective_contrasts
    if not contrasts:
        return (BASE_ARM,)
    wanted = {c.reference for c in contrasts}
    ordered = [BASE_ARM, *(a.label for a in question.effective_arms)]
    return tuple(label for label in ordered if label in wanted)


def build_case(concept_id: str, question: Question, phase0: StudyPlan | None = None) -> Phase1Case:
    """The context phase 0 leaves behind and the plan for what is still missing. `phase0` is the
    stored (possibly corrected) phase-0 plan; the proposal when not given."""
    phase0 = propose_plan(question) if phase0 is None else phase0
    reference = _reference_side(question)
    experiments = tuple(
        Experiment(
            scenario_id=f"scenario-{concept_id}-{s.arm}",
            arm=s.arm,
            role=s.role,
            purpose=s.purpose,
        )
        for s in phase0.steps
        if isinstance(s, BuildScenarioStep) and s.arm in reference
    )
    if tuple(e.arm for e in experiments) != reference:
        raise ValueError(f"{concept_id}: phase 0 does not realise the arms it needs")
    context = PlanningContext(
        phase=PHASE, network_id=f"network-{concept_id}", experiments=experiments
    )
    plan = propose_plan(question, PHASE, {e.arm for e in experiments})
    return Phase1Case(context, plan)


def build_phase1() -> dict[str, Phase1Case]:
    """The cases, with the context taken from the stored phase-0 plans, so a corrected phase-0 plan
    cannot desync phase 1."""
    plans = load_plans()
    return {c.id: build_case(c.id, phase1_question(c.id), plans[c.id]) for c in phase1_concepts()}


def dump_phase1(cases: dict[str, Phase1Case]) -> str:
    context, plan = adapter_for(PlanningContext), adapter_for(StudyPlan)
    rows: dict[str, Any] = {
        cid: {
            "context": context.dump_python(cases[cid].context, mode="json"),
            "plan": plan.dump_python(cases[cid].plan, mode="json"),
        }
        for cid in sorted(cases)
    }
    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def save_phase1(cases: dict[str, Phase1Case], path: Path = PHASE1_PATH) -> None:
    path.write_text(dump_phase1(cases), encoding="utf-8")


def load_phase1(path: Path = PHASE1_PATH) -> dict[str, Phase1Case]:
    """Every stored case is validated on load, so its own invariants check the gold."""
    context, plan = adapter_for(PlanningContext), adapter_for(StudyPlan)
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {
        cid: Phase1Case(context.validate_python(r["context"]), plan.validate_python(r["plan"]))
        for cid, r in rows.items()
    }


if __name__ == "__main__":
    built = build_phase1()
    save_phase1(built)
    print(f"wrote {len(built)} phase-1 cases to {PHASE1_PATH}")
