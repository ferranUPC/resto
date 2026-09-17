"""Scores one Expert answer against its gold answer — pure, no I/O (docs/evaluating-resto.md §4.4).

A question is incorrect when there is no answer, when promotion rejected it, or when the expected
typed value is missing; otherwise the family's rule decides.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from eval.expert_benchmark.bank import BenchmarkQuestion, Family
from eval.question_bank.gold import magnitude_band
from resto.domain.value_objects.answer_value import (
    AnswerValue,
    Change,
    ChangeDirection,
    Edges,
    Measure,
    Quantity,
)
from resto.domain.value_objects.expert_answer import ExpertAnswer

NUMERIC_TOLERANCE = 0.05
JACCARD_CORRECT = 0.6

_GOLD_DIRECTION = {
    "increase": ChangeDirection.INCREASE,
    "decrease": ChangeDirection.DECREASE,
    "within_threshold": ChangeDirection.UNCHANGED,
}


@dataclass(frozen=True, slots=True)
class Score:
    correct: bool
    detail: str
    jaccard: float | None = None


def jaccard(a: Collection[str], b: Collection[str]) -> float:
    """Set overlap in [0, 1]; two empty sets are identical (1.0)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def within_tolerance(predicted: float, gold: float, tolerance: float = NUMERIC_TOLERANCE) -> bool:
    if gold == 0.0:
        return predicted == 0.0
    return abs(predicted - gold) <= tolerance * abs(gold)


def score_answer(
    question: BenchmarkQuestion, answer: ExpertAnswer | None, *, rejection: str | None = None
) -> Score:
    if answer is None:
        return Score(False, "no answer")
    if rejection is not None:
        return Score(False, f"rejected: {rejection}")
    return _SCORERS[question.family](question, answer.values)


def _first_edges(values: tuple[AnswerValue, ...]) -> Edges | None:
    return next((v for v in values if isinstance(v, Edges)), None)


def _find_change(
    values: tuple[AnswerValue, ...], measure: Measure, edge_id: str | None
) -> Change | None:
    for value in values:
        if isinstance(value, Change) and (value.measure, value.edge_id) == (measure, edge_id):
            return value
    return None


def _score_desc_occ(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    edges = _first_edges(values)
    if edges is None:
        return Score(False, "missing edges value")
    gold = set(question.gold["edges_above_threshold"])
    predicted = set(edges.edge_ids)
    return Score(predicted == gold, f"predicted {sorted(predicted)}, gold {sorted(gold)}")


def _score_desc_tt(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    edge_id = question.gold["edge_id"]
    quantity = next(
        (
            v
            for v in values
            if isinstance(v, Quantity)
            and (v.measure, v.edge_id) == (Measure.TRAVEL_TIME, edge_id)
        ),
        None,
    )
    if quantity is None:
        return Score(False, f"missing travel_time quantity on {edge_id}")
    gold = float(question.gold["mean_travel_time_s"])
    detail = f"predicted {quantity.value:.2f} s, gold {gold:.2f} s"
    return Score(within_tolerance(quantity.value, gold), detail)


def _score_edge_ranking(gold_ids: list[str], values: tuple[AnswerValue, ...]) -> Score:
    edges = _first_edges(values)
    if edges is None:
        return Score(False, "missing edges value")
    overlap = jaccard(edges.edge_ids, gold_ids)
    return Score(
        overlap >= JACCARD_CORRECT,
        f"predicted {list(edges.edge_ids)}, gold {gold_ids}, jaccard {overlap:.2f}",
        jaccard=overlap,
    )


def _score_diag(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    return _score_edge_ranking(list(question.gold["top_3"]), values)


def _score_cf_topk(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    return _score_edge_ranking([e for e, _ in question.gold["top_k_by_delay_change"]], values)


def _score_cf_dir(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    edge_id = question.gold["edge_id"]
    change = _find_change(values, Measure.TIME_LOSS, edge_id)
    if change is None:
        return Score(False, f"missing time_loss change on {edge_id}")
    gold = _GOLD_DIRECTION[question.gold["direction"]]
    return Score(change.direction is gold, f"predicted {change.direction}, gold {gold}")


def _score_cf_band(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    change = _find_change(values, Measure.MEAN_DELAY, None)
    if change is None:
        return Score(False, "missing network mean_delay change")
    if change.relative_change_pct is None:
        return Score(False, "mean_delay change without relative_change_pct")
    band = magnitude_band(change.relative_change_pct)
    gold = question.gold["band"]
    return Score(
        band == gold, f"predicted {change.relative_change_pct:+.1f} % ({band}), gold {gold}"
    )


_SCORERS = {
    Family.DESC_OCC: _score_desc_occ,
    Family.DESC_TT: _score_desc_tt,
    Family.DIAG: _score_diag,
    Family.CF_DIR: _score_cf_dir,
    Family.CF_TOPK: _score_cf_topk,
    Family.CF_BAND: _score_cf_band,
}
