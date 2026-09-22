"""Abstention recall / false-requests (E4.5; docs/evaluating-resto.md §4.5): pairs a forced-mode
run with the free-mode run of the same question and repetition, and checks the two derived rates.
"""

from __future__ import annotations

from typing import Any

from eval.expert_benchmark.bank import BenchmarkQuestion, Family
from eval.expert_benchmark.report import repetition_metrics, score_records, summarize

from resto.application.schemas import adapter_for
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.question import Intent, Mode, Question

GOLD_EDGE = "B1B0"


def _question(qid: str) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id=qid,
        family=Family.DESC_OCC,
        text="which edges exceed 3.5% occupancy?",
        network_id="n",
        result_ids=("r1",),
        gold={"edges_above_threshold": [GOLD_EDGE]},
    )


def _answer(edge_ids: tuple[str, ...]) -> ExpertAnswer:
    return ExpertAnswer(
        answer="prose",
        basis=Basis.OBSERVED,
        confidence=0.8,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref="q1"),),
        values=(Edges(edge_ids=edge_ids),),
    )


def _abstention() -> ExpertAnswer:
    return ExpertAnswer(
        answer="no simulation covers this",
        basis=Basis.EXTRAPOLATED,
        confidence=0.2,
        needs_simulation=True,
        proposed_experiment=Question(text="run it", intent=Intent.DESCRIBE, network_ref="n"),
    )


def _record(
    question_id: str, mode: Mode, answer: ExpertAnswer | None, *, rejection: str | None = None
) -> dict[str, Any]:
    return {
        "question_id": question_id,
        "repetition": 1,
        "mode": mode.value,
        "model": "fake",
        "expert_version": "vtest",
        "rejection": rejection,
        "answer": None if answer is None else adapter_for(ExpertAnswer).dump_python(
            answer, mode="json"
        ),
        "steps": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0,
        "stop_reason": "output",
    }


CORRECT = _question("S00-desc-occ")  # forced answer will be correct, free will not abstain
INCORRECT = _question("S01-desc-occ")  # forced answer will be wrong, free will abstain (recalled)
FALSE_REQUEST = _question("S02-desc-occ")  # forced answer will be correct, free will abstain
QUESTIONS = [CORRECT, INCORRECT, FALSE_REQUEST]


def _scored() -> tuple[list[Any], list[Any]]:
    forced_records = [
        _record(CORRECT.id, Mode.FORCED, _answer((GOLD_EDGE,))),
        _record(INCORRECT.id, Mode.FORCED, _answer(("B2C2",))),
        _record(FALSE_REQUEST.id, Mode.FORCED, _answer((GOLD_EDGE,))),
    ]
    free_records = [
        _record(CORRECT.id, Mode.FREE, _answer((GOLD_EDGE,))),
        _record(INCORRECT.id, Mode.FREE, _abstention()),
        _record(FALSE_REQUEST.id, Mode.FREE, _abstention()),
    ]
    return score_records(forced_records, QUESTIONS), score_records(free_records, QUESTIONS)


def test_recall_and_false_requests_on_a_hand_computed_mix() -> None:
    forced, free = _scored()
    metrics = repetition_metrics(forced, free)
    # one forced-incorrect question (INCORRECT), which abstained in free -> recall 1/1
    assert metrics["abstention_recall"] == 1.0
    # two abstentions (INCORRECT, FALSE_REQUEST), one of which was forced-correct -> 1/2
    assert metrics["abstention_false_requests"] == 0.5


def test_recall_is_none_without_any_forced_incorrect_answer() -> None:
    forced, free = _scored()
    only_correct = [r for r in forced if r.question.id != INCORRECT.id]
    metrics = repetition_metrics(only_correct, free)
    assert metrics["abstention_recall"] is None


def test_false_requests_is_none_without_any_abstention() -> None:
    forced, _ = _scored()
    no_free = score_records([], QUESTIONS)
    metrics = repetition_metrics(forced, no_free)
    assert metrics["abstention_recall"] == 0.0  # INCORRECT never recalled: nothing abstained
    assert metrics["abstention_false_requests"] is None


def test_a_free_run_with_no_answer_never_counts_as_abstained() -> None:
    forced, _ = _scored()
    crashed_free = score_records(
        [_record(INCORRECT.id, Mode.FREE, None), _record(FALSE_REQUEST.id, Mode.FREE, None)],
        QUESTIONS,
    )
    metrics = repetition_metrics(forced, crashed_free)
    assert (metrics["abstention_recall"], metrics["abstention_false_requests"]) == (0.0, None)


def test_summarize_wires_free_runs_into_the_matching_repetition_and_totals_cost() -> None:
    forced, free = _scored()
    summary = summarize(forced, free)
    assert summary["aggregate"]["abstention_recall"]["mean"] == 1.0
    assert summary["aggregate"]["abstention_false_requests"]["mean"] == 0.5
    assert summary["runs"] == len(forced) + len(free)
