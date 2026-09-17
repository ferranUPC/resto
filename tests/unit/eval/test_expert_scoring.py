"""Expert benchmark bank loading and scoring rules (E3.3; docs/evaluating-resto.md §4.4)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from eval.expert_benchmark.bank import BenchmarkQuestion, Family, load_bank
from eval.expert_benchmark.scoring import jaccard, score_answer, within_tolerance

from resto.domain.value_objects.answer_value import (
    AnswerValue,
    Change,
    ChangeDirection,
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
DIAG = _question("S00-diag", {"top_3": ["B2C2", "C2D2", "E3E2"], "reason": "signal"})
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


def test_jaccard_and_tolerance_helpers() -> None:
    assert jaccard([], []) == 1.0
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)
    assert within_tolerance(23.4, 23.403)
    assert not within_tolerance(21.95, 23.403)
    assert within_tolerance(0.0, 0.0)
    assert not within_tolerance(0.1, 0.0)


def test_no_answer_or_a_rejected_answer_is_incorrect() -> None:
    assert not score_answer(OCC, None).correct
    rejected = score_answer(OCC, _answer(Edges(edge_ids=("B1B0",))), rejection="bad ref")
    assert not rejected.correct
    assert "rejected" in rejected.detail


def test_desc_occ_needs_the_exact_set() -> None:
    assert score_answer(OCC, _answer(Edges(edge_ids=("B1B0",)))).correct
    assert not score_answer(OCC, _answer(Edges(edge_ids=("B1B0", "B2C2")))).correct
    assert not score_answer(OCC, _answer(Quantity(Measure.MEAN_DELAY, 3.0))).correct
    empty = _question("S00-desc-occ", {"edges_above_threshold": []})
    assert score_answer(empty, _answer(Edges(edge_ids=()))).correct


def test_desc_tt_uses_the_travel_time_on_the_gold_edge_within_5_percent() -> None:
    assert score_answer(TT, _answer(Quantity(Measure.TRAVEL_TIME, 23.4, "B2C2"))).correct
    assert not score_answer(TT, _answer(Quantity(Measure.TRAVEL_TIME, 21.95, "B2C2"))).correct
    wrong_edge = score_answer(TT, _answer(Quantity(Measure.TRAVEL_TIME, 23.4, "C2D2")))
    assert not wrong_edge.correct
    assert "missing" in wrong_edge.detail


def test_diag_is_correct_from_jaccard_0_6() -> None:
    smoke_answer = score_answer(DIAG, _answer(Edges(("A2B2", "B2C2", "C2D2"), ranked=True)))
    assert smoke_answer.jaccard == pytest.approx(0.5)
    assert not smoke_answer.correct
    four = score_answer(DIAG, _answer(Edges(("B2C2", "C2D2", "E3E2", "A2B2"), ranked=True)))
    assert four.jaccard == pytest.approx(0.75)
    assert four.correct


def test_cf_topk_compares_edge_sets() -> None:
    score = score_answer(TOPK, _answer(Edges(("B0C0", "C1C0", "C1C2"), ranked=True)))
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
    answer = _answer(Change(Measure.TIME_LOSS, direction, edge_id="B2C2"))
    assert score_answer(question, answer).correct is correct


def test_cf_dir_ignores_a_change_on_another_measure_or_edge() -> None:
    other_edge = _answer(Change(Measure.TIME_LOSS, ChangeDirection.INCREASE, edge_id="C2D2"))
    other_measure = _answer(Change(Measure.SPEED, ChangeDirection.INCREASE, edge_id="B2C2"))
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
    assert score_answer(closed, _answer(NoValue(Measure.TRAVEL_TIME, "B2C2"))).correct
    assert not score_answer(closed, _answer(Quantity(Measure.TRAVEL_TIME, 0.0, "B2C2"))).correct
    assert not score_answer(TT, _answer(NoValue(Measure.TRAVEL_TIME, "B2C2"))).correct
