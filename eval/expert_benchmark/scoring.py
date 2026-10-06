"""Scores one Expert answer against its gold answer — pure, no I/O (eval/README.md §4.4).

A question is incorrect when there is no answer, when promotion rejected it, or when the expected
typed value is missing; otherwise the family's rule decides. A diagnostic score also counts the
Bottleneck causes (ADR-0029) over the edges the answer shares with the gold top-3.

An edge is a (network id, edge id) pair: the gold names its network in `gold["network_id"]` and each
answer value names its own (ADR-0032), so the right edge on the wrong network scores as wrong.
"""

from __future__ import annotations

from collections.abc import Collection, Hashable
from dataclasses import dataclass
from typing import Any

from eval.expert_benchmark.bank import BenchmarkQuestion, Family
from eval.question_bank.gold import magnitude_band
from resto.domain.services.comparison import within_tolerance
from resto.domain.value_objects.answer_value import (
    AnswerValue,
    BottleneckCauses,
    Change,
    ChangeDirection,
    Edges,
    Measure,
    NoValue,
    Quantity,
)
from resto.domain.value_objects.expert_answer import ExpertAnswer

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
    # diagnostic only: edges shared by answer and gold, and how many carry the gold cause
    shared_edges: int = 0
    correct_causes: int = 0


def jaccard(a: Collection[Hashable], b: Collection[Hashable]) -> float:
    """Set overlap in [0, 1]; two empty sets are identical (1.0)."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def score_answer(
    question: BenchmarkQuestion, answer: ExpertAnswer | None, *, rejection: str | None = None
) -> Score:
    if answer is None:
        return Score(False, "no answer")
    if rejection is not None:
        return Score(False, f"rejected: {rejection}")
    return _SCORERS[question.family](question, answer.values)


EdgeRef = tuple[str, str]


def _gold_refs(question: BenchmarkQuestion, edge_ids: Collection[str]) -> list[EdgeRef]:
    network_id = question.gold["network_id"]
    return [(network_id, edge_id) for edge_id in edge_ids]


def _first_edges(values: tuple[AnswerValue, ...]) -> Edges | None:
    return next((v for v in values if isinstance(v, Edges)), None)


def _find_change(
    values: tuple[AnswerValue, ...], measure: Measure, edge: EdgeRef | None
) -> Change | None:
    """The change of `measure` on `edge`, or (edge None) on the whole network."""
    for value in values:
        if (
            isinstance(value, Change)
            and value.measure is measure
            and value.edge_references == (() if edge is None else (edge,))
        ):
            return value
    return None


def _score_desc_occ(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    edges = _first_edges(values)
    if edges is None:
        return Score(False, "missing edges value")
    gold = set(_gold_refs(question, question.gold["edges_above_threshold"]))
    predicted = set(edges.edge_references)
    return Score(
        predicted == gold,
        f"predicted {_listed(predicted)}, gold {_listed(gold)}",
    )


def _listed(refs: Collection[EdgeRef]) -> list[str]:
    """Edge ids for a score detail, each prefixed by its network when the refs span several."""
    networks = {network_id for network_id, _ in refs}
    if len(networks) > 1:
        return sorted(f"{network_id[:8]}:{edge_id}" for network_id, edge_id in refs)
    return sorted(edge_id for _, edge_id in refs)


def _score_desc_tt(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    edge_id = question.gold["edge_id"]
    edge: EdgeRef = (question.gold["network_id"], edge_id)
    said_no_value = any(
        isinstance(v, NoValue) and v.measure is Measure.TRAVEL_TIME and v.edge_references == (edge,)
        for v in values
    )
    if "no_value" in question.gold:
        detail = "answered no value" if said_no_value else "gold: no vehicle crossed, no value"
        return Score(said_no_value, detail)
    if said_no_value:
        return Score(False, "answered no value, but the edge had traffic")
    quantity = next(
        (
            v
            for v in values
            if isinstance(v, Quantity)
            and v.measure is Measure.TRAVEL_TIME
            and v.edge_references == (edge,)
        ),
        None,
    )
    if quantity is None:
        return Score(False, f"missing travel_time quantity on {edge_id}")
    gold = float(question.gold["mean_travel_time_s"])
    detail = f"predicted {quantity.value:.2f} s, gold {gold:.2f} s"
    return Score(within_tolerance(quantity.value, gold), detail)


def _score_edge_ranking(gold_refs: list[EdgeRef], values: tuple[AnswerValue, ...]) -> Score:
    edges = _first_edges(values)
    if edges is None:
        return Score(False, "missing edges value")
    overlap = jaccard(edges.edge_references, gold_refs)
    return Score(
        overlap >= JACCARD_CORRECT,
        f"predicted {_listed(edges.edge_references)}, gold {_listed(gold_refs)}, "
        f"jaccard {overlap:.2f}",
        jaccard=overlap,
    )


def _score_diag(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    """Jaccard decides `correct`; the causes are graded on the shared edges only, so a wrong edge
    costs once (in the Jaccard). A missing cause value scores every shared edge wrong."""
    gold_ids = list(question.gold["top_3"])
    gold_refs = _gold_refs(question, gold_ids)
    ranking = _score_edge_ranking(gold_refs, values)
    edges = _first_edges(values)
    if edges is None:
        return ranking
    cause_value = next((v for v in values if isinstance(v, BottleneckCauses)), None)
    predicted: dict[EdgeRef, Any] = {}
    if cause_value is not None:
        predicted = {(c.network_id, c.edge_id): c.cause for c in cause_value.causes}
    gold_causes = question.gold["causes"]
    shared = [ref for ref in edges.edge_references if ref in gold_refs]
    correct = sum(predicted.get(ref) == gold_causes[ref[1]] for ref in shared)
    pairs = ", ".join(
        f"{ref[1]} {predicted.get(ref, 'missing')}/{gold_causes[ref[1]]}" for ref in shared
    )
    return Score(
        ranking.correct,
        f"{ranking.detail}; causes (predicted/gold) {correct}/{len(shared)}: {pairs or 'none'}",
        jaccard=ranking.jaccard,
        shared_edges=len(shared),
        correct_causes=correct,
    )


def _score_cf_topk(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    gold_ids = [e for e, _ in question.gold["top_k_by_delay_change"]]
    return _score_edge_ranking(_gold_refs(question, gold_ids), values)


def _score_cf_dir(question: BenchmarkQuestion, values: tuple[AnswerValue, ...]) -> Score:
    edge_id = question.gold["edge_id"]
    change = _find_change(values, Measure.TIME_LOSS, (question.gold["network_id"], edge_id))
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
