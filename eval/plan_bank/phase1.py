"""The phase-1 case set of the planner (r13 ticket 07): the part of planning the 54 phase-0 plans
do not exercise.

Each case is an experiment the Network Expert asks for after phase 0 realised the base arm of its
network. The experiments are the 57 counterfactual questions of the Expert benchmark
(`eval/question_bank/question-bank.json`, ids `S01-cf-dir` and its kin): each is a typed `Question`
with one intervention that the Expert can only settle by simulating it, and each entry stores the
baseline scenario and results phase 0 leaves behind. Nothing here calls a model, and no case
stores a plan: the expected plan is stated in `tests/unit/eval/test_phase1_cases.py` from the
stored question, not produced by the planner.

The question is the experiment as the Expert proposes it: it names no network, so the planner takes
the study's network from the context (user story 8 of the refactor).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from resto.application.schemas import adapter_for
from resto.domain.services.planner import PlanningContext
from resto.domain.value_objects.arm import BASE_ARM
from resto.domain.value_objects.question import Question

QUESTION_BANK_PATH = Path(__file__).resolve().parents[1] / "question_bank" / "question-bank.json"


@dataclass(frozen=True, slots=True)
class Phase1Case:
    id: str
    question: Question
    """The experiment the Expert asks for; `network_ref` is empty: the context names it."""
    context: PlanningContext
    """What phase 0 realised: the base arm, on the benchmark's network."""
    baseline_result_ids: tuple[str, ...]
    """The stored results of that base arm, which the Expert read before it asked."""


def load_phase1(path: Path = QUESTION_BANK_PATH) -> dict[str, Phase1Case]:
    """One case per counterfactual entry of the Expert benchmark, in file order. Every stored
    question is validated on load."""
    adapter = adapter_for(Question)
    cases: dict[str, Phase1Case] = {}
    for entry in json.loads(path.read_text(encoding="utf-8")):
        if not entry["id"].split("-", 1)[1].startswith("cf-"):
            continue
        stored = adapter.validate_python(entry["question"])
        baseline = tuple(entry["evidence"]["baseline_result_ids"])
        if stored.network_ref is None or not baseline:
            raise ValueError(f"{entry['id']}: no network or no stored baseline: not a phase-1 case")
        cases[entry["id"]] = Phase1Case(
            id=entry["id"],
            question=replace(stored, network_ref=None),
            context=PlanningContext(phase=1, network_id=stored.network_ref, realised=(BASE_ARM,)),
            baseline_result_ids=baseline,
        )
    return cases
