"""Expert benchmark bank loading and scoring rules (E3.3; docs/evaluating-resto.md §4.4)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import pytest
from eval.expert_benchmark.bank import BenchmarkQuestion, Family, load_bank
from eval.expert_benchmark.report import (
    THRESHOLDS,
    ScoredRun,
    render_markdown,
    repetition_metrics,
    summarize,
)
from eval.expert_benchmark.scoring import Score, jaccard, score_answer, within_tolerance

from resto.domain.value_objects.answer_value import (
    AnswerValue,
    BottleneckCause,
    BottleneckCauses,
    Change,
    ChangeDirection,
    EdgeCause,
    Edges,
    Measure,
    NoValue,
    Quantity,
)
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer


def _question(qid: str, gold: Mapping[str, Any]) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id=qid, family=Family.of(qid), text="q", network_id="n", result_ids=("r1",), gold=gold
    )


NET = "abc123"


def _ranked(edge_ids: tuple[str, ...]) -> Edges:
    return Edges(edge_ids, network_id=NET, ranked=True)


def _answer(*values: AnswerValue) -> ExpertAnswer:
    return ExpertAnswer(
        answer="prose",
        basis=Basis.OBSERVED,
        confidence=0.8,
        evidence=(Evidence(kind=EvidenceKind.QUERY, ref="q1"),),
        values=values,
    )


OCC = _question("S03-desc-occ", {"edges_above_threshold": ["B1B0"]})
TT = _question("S00-desc-tt", {"edge_id": "B2C2", "mean_travel_time_s": 23.403})
DIAG = _question(
    "S00-diag",
    {
        "top_3": ["B2C2", "C2D2", "E3E2"],
        "causes": {"B2C2": "intervention", "C2D2": "spillback", "E3E2": "signal"},
    },
)
DIR = _question("S09-cf-dir", {"edge_id": "B2C2", "direction": "increase", "pct_change": 114.4})
TOPK = _question(
    "S05-cf-topk", {"top_k_by_delay_change": [["B0C0", 594.9], ["C1C0", 92.5], ["C1C2", 7.6]]}
)
BAND = _question("S17-cf-band", {"band": "5-20%", "pct_change": 7.6})


def test_family_is_the_id_suffix() -> None:
    assert Family.of("S03-desc-occ") is Family.DESC_OCC
    assert Family.of("S17-cf-band") is Family.CF_BAND


def test_the_real_bank_loads_with_baseline_results_for_counterfactuals() -> None:
    bank = load_bank()
    assert len(bank) == 117
    cf = load_bank(ids=["S09-cf-dir"])[0]
    desc = load_bank(ids=["S09-desc-tt"])[0]
    assert len(desc.result_ids) == 3
    assert len(cf.result_ids) == 6
    task = cf.to_task()
    assert task.mode.value == "forced"
    assert not task.notes_allowed
    assert "S09" not in task.question


def test_the_real_bank_carries_a_gold_cause_for_each_diagnostic_edge() -> None:
    diagnostic = [q for q in load_bank() if q.family is Family.DIAG]
    assert len(diagnostic) == 20
    for question in diagnostic:
        assert sorted(question.gold["causes"]) == sorted(question.gold["top_3"])
        assert "reason" not in question.gold
        assert question.text.endswith("and why is each of them congested?")
    totals = Counter(cause for q in diagnostic for cause in q.gold["causes"].values())
    assert totals == {"intervention": 21, "signal": 33, "spillback": 6}


def test_jaccard_and_tolerance_helpers() -> None:
    assert jaccard([], []) == 1.0
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert within_tolerance(23.4, 23.403)
    assert not within_tolerance(21.95, 23.403)
    assert within_tolerance(0.0, 0.0)
    assert not within_tolerance(0.1, 0.0)


def test_no_answer_or_a_rejected_answer_is_incorrect() -> None:
    assert not score_answer(OCC, None).correct
    answer = _answer(Edges(edge_ids=("B1B0",), network_id=NET))
    rejected = score_answer(OCC, answer, rejection="bad ref")
    assert not rejected.correct
    assert "rejected" in rejected.detail


def test_desc_occ_needs_the_exact_set() -> None:
    assert score_answer(OCC, _answer(Edges(edge_ids=("B1B0",), network_id=NET))).correct
    assert not score_answer(OCC, _answer(Edges(edge_ids=("B1B0", "B2C2"), network_id=NET))).correct
    assert not score_answer(OCC, _answer(Quantity(Measure.MEAN_DELAY, 3.0))).correct
    empty = _question("S00-desc-occ", {"edges_above_threshold": []})
    assert score_answer(empty, _answer(Edges(edge_ids=(), network_id=NET))).correct


def test_desc_tt_uses_the_travel_time_on_the_gold_edge_within_5_percent() -> None:
    assert score_answer(TT, _answer(Quantity(Measure.TRAVEL_TIME, 23.4, "B2C2", NET))).correct
    assert not score_answer(TT, _answer(Quantity(Measure.TRAVEL_TIME, 21.95, "B2C2", NET))).correct
    wrong_edge = score_answer(TT, _answer(Quantity(Measure.TRAVEL_TIME, 23.4, "C2D2", NET)))
    assert not wrong_edge.correct
    assert "missing" in wrong_edge.detail


def test_diag_is_correct_from_jaccard_0_6() -> None:
    smoke_answer = score_answer(DIAG, _answer(_ranked(("A2B2", "B2C2", "C2D2"))))
    assert smoke_answer.jaccard == pytest.approx(0.5)
    assert not smoke_answer.correct
    four = score_answer(DIAG, _answer(_ranked(("B2C2", "C2D2", "E3E2", "A2B2"))))
    assert four.jaccard == pytest.approx(0.75)
    assert four.correct


def _causes(**by_edge: BottleneckCause) -> BottleneckCauses:
    return BottleneckCauses(tuple(EdgeCause(e, NET, c) for e, c in by_edge.items()))


def test_diag_counts_causes_over_the_edges_shared_with_the_gold() -> None:
    edges = Edges(("B2C2", "C2D2", "A2B2"), network_id=NET, ranked=True)
    causes = _causes(
        B2C2=BottleneckCause.INTERVENTION,
        C2D2=BottleneckCause.SIGNAL,
        A2B2=BottleneckCause.DEMAND,
    )
    score = score_answer(DIAG, _answer(edges, causes))
    # A2B2 is not in the gold top-3: the Jaccard penalises it, the cause count ignores it.
    assert (score.shared_edges, score.correct_causes) == (2, 1)
    assert "C2D2 signal/spillback" in score.detail


def test_diag_cause_accuracy_is_independent_of_the_jaccard_verdict() -> None:
    edges = Edges(("B2C2", "C2D2", "E3E2"), network_id=NET, ranked=True)
    causes = _causes(
        B2C2=BottleneckCause.INTERVENTION,
        C2D2=BottleneckCause.SPILLBACK,
        E3E2=BottleneckCause.SIGNAL,
    )
    score = score_answer(DIAG, _answer(edges, causes))
    assert score.correct
    assert (score.shared_edges, score.correct_causes) == (3, 3)


def test_diag_without_a_cause_value_scores_every_shared_edge_wrong() -> None:
    score = score_answer(DIAG, _answer(_ranked(("B2C2", "C2D2", "E3E2"))))
    assert score.correct
    assert (score.shared_edges, score.correct_causes) == (3, 0)


def test_diag_cause_value_missing_an_edge_scores_that_edge_wrong() -> None:
    edges = Edges(("B2C2", "C2D2"), network_id=NET, ranked=True)
    causes = _causes(B2C2=BottleneckCause.INTERVENTION)
    score = score_answer(DIAG, _answer(edges, causes))
    assert (score.shared_edges, score.correct_causes) == (2, 1)


def test_diag_without_an_answer_shares_no_edges() -> None:
    for score in (
        score_answer(DIAG, None),
        score_answer(DIAG, _answer(Edges(("B2C2",), network_id=NET)), rejection="bad ref"),
    ):
        assert (score.shared_edges, score.correct_causes) == (0, 0)


def _run(question: BenchmarkQuestion, score: Score, repetition: int = 1) -> ScoredRun:
    record: dict[str, Any] = {
        "rejection": None,
        "model": "fake",
        "expert_version": "vtest",
        "steps": [],
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "real_cost_usd": None,
        "stop_reason": "output",
    }
    return ScoredRun(question, repetition, score, _answer(Edges(("B2C2",), network_id=NET)), record)


def test_diag_cause_accuracy_sums_over_one_repetitions_shared_edges() -> None:
    other = _question("S01-diag", DIAG.gold)
    runs = [
        _run(DIAG, Score(True, "", jaccard=1.0, shared_edges=3, correct_causes=3)),
        _run(other, Score(False, "", jaccard=0.2, shared_edges=1, correct_causes=0)),
        _run(_question("S02-diag", DIAG.gold), Score(False, "no answer")),
    ]
    # micro-average: 3 correct / 4 shared, not the mean of per-question rates (0.5)
    assert repetition_metrics(runs)["diag_cause_accuracy"] == pytest.approx(0.75)
    assert repetition_metrics([runs[2]])["diag_cause_accuracy"] is None


def test_diag_cause_accuracy_aggregates_across_repetitions_against_the_dod_bar() -> None:
    runs = [
        _run(DIAG, Score(True, "", jaccard=1.0, shared_edges=3, correct_causes=3), 1),
        _run(DIAG, Score(True, "", jaccard=1.0, shared_edges=3, correct_causes=1), 2),
    ]
    summary = summarize(runs)
    aggregate = summary["aggregate"]["diag_cause_accuracy"]
    assert aggregate["mean"] == pytest.approx(2 / 3)
    assert aggregate["std"] == pytest.approx(0.4714, abs=1e-4)
    assert THRESHOLDS["diag_cause_accuracy"] == (">=", 0.70)
    assert "| diag_cause_accuracy | 0.67 | 0.47 | >= 0.70 ❌ |" in render_markdown(
        "t", summary, runs
    )


def test_cf_topk_compares_edge_sets() -> None:
    score = score_answer(TOPK, _answer(_ranked(("B0C0", "C1C0", "C1C2"))))
    assert score.correct
    assert score.jaccard == 1.0


@pytest.mark.parametrize(
    ("direction", "gold", "correct"),
    [
        (ChangeDirection.INCREASE, "increase", True),
        (ChangeDirection.DECREASE, "increase", False),
        (ChangeDirection.UNCHANGED, "within_threshold", True),
    ],
)
def test_cf_dir_compares_directions(direction: ChangeDirection, gold: str, correct: bool) -> None:
    question = _question("S09-cf-dir", {"edge_id": "B2C2", "direction": gold})
    answer = _answer(Change(Measure.TIME_LOSS, direction, edge_id="B2C2", network_id=NET))
    assert score_answer(question, answer).correct is correct


def test_cf_dir_ignores_a_change_on_another_measure_or_edge() -> None:
    other_edge = _answer(
        Change(Measure.TIME_LOSS, ChangeDirection.INCREASE, edge_id="C2D2", network_id=NET)
    )
    other_measure = _answer(
        Change(Measure.SPEED, ChangeDirection.INCREASE, edge_id="B2C2", network_id=NET)
    )
    assert not score_answer(DIR, other_edge).correct
    assert not score_answer(DIR, other_measure).correct


def test_cf_band_derives_the_band_from_the_percentage() -> None:
    right = _answer(Change(Measure.MEAN_DELAY, ChangeDirection.INCREASE, 7.6))
    wrong = _answer(Change(Measure.MEAN_DELAY, ChangeDirection.INCREASE, 25.0))
    no_pct = _answer(Change(Measure.MEAN_DELAY, ChangeDirection.INCREASE))
    assert score_answer(BAND, right).correct
    assert not score_answer(BAND, wrong).correct
    assert not score_answer(BAND, no_pct).correct


def test_desc_tt_on_an_edge_without_traffic_expects_no_value() -> None:
    closed = _question("S01-desc-tt", {"edge_id": "B2C2", "no_value": "no_traffic"})
    assert score_answer(closed, _answer(NoValue(Measure.TRAVEL_TIME, "B2C2", NET))).correct
    zero = _answer(Quantity(Measure.TRAVEL_TIME, 0.0, "B2C2", NET))
    assert not score_answer(closed, zero).correct
    assert not score_answer(TT, _answer(NoValue(Measure.TRAVEL_TIME, "B2C2", NET))).correct
