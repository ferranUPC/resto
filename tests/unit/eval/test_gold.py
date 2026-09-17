"""Unit tests for the question bank's pure gold-answer math (eval/question_bank/gold.py,
work-plan E3.2). No SUMO, no DatabaseMCP - synthetic `query_edgedata`-shaped mappings only."""

from __future__ import annotations

import math

import pytest
from eval.question_bank.gold import (
    BottleneckReason,
    Direction,
    EdgeMeasure,
    MagnitudeBand,
    bottleneck_reason,
    classify_direction,
    edges_above_threshold,
    magnitude_band,
    mean_edgedata,
    pct_change,
    top_bottleneck_edges,
    top_k_by_delta,
)


def _edge(time_loss: float = 0.0, entered: float = 0.0, occupancy: float = 0.0) -> dict[str, float]:
    return {"time_loss": time_loss, "entered": entered, "occupancy": occupancy}


class TestMeanEdgedata:
    def test_averages_each_measure_per_edge_across_seeds(self) -> None:
        seed1 = {"E1": _edge(occupancy=2.0), "E2": _edge(occupancy=4.0)}
        seed2 = {"E1": _edge(occupancy=4.0), "E2": _edge(occupancy=8.0)}
        result = mean_edgedata([seed1, seed2])
        assert result["E1"]["occupancy"] == 3.0
        assert result["E2"]["occupancy"] == 6.0

    def test_single_seed_is_unchanged(self) -> None:
        seed1 = {"E1": _edge(occupancy=5.0)}
        expected = {"E1": {"time_loss": 0.0, "entered": 0.0, "occupancy": 5.0}}
        assert mean_edgedata([seed1]) == expected

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError):
            mean_edgedata([])


class TestPctChange:
    def test_positive_baseline(self) -> None:
        assert pct_change(100.0, 110.0) == pytest.approx(10.0)
        assert pct_change(100.0, 90.0) == pytest.approx(-10.0)

    def test_zero_baseline_zero_value_is_no_change(self) -> None:
        assert pct_change(0.0, 0.0) == 0.0

    def test_zero_baseline_nonzero_value_is_unbounded_in_that_sign(self) -> None:
        assert pct_change(0.0, 5.0) == math.inf
        assert pct_change(0.0, -5.0) == -math.inf


class TestClassifyDirection:
    def test_within_threshold_both_sides(self) -> None:
        assert classify_direction(100.0, 105.0) == Direction.WITHIN_THRESHOLD
        assert classify_direction(100.0, 95.0) == Direction.WITHIN_THRESHOLD

    def test_exactly_at_threshold_is_within(self) -> None:
        assert classify_direction(100.0, 105.0, pct_threshold=5.0) == Direction.WITHIN_THRESHOLD

    def test_just_past_threshold_is_a_direction(self) -> None:
        assert classify_direction(100.0, 105.01) == Direction.INCREASE
        assert classify_direction(100.0, 94.99) == Direction.DECREASE

    def test_zero_baseline(self) -> None:
        assert classify_direction(0.0, 0.0) == Direction.WITHIN_THRESHOLD
        assert classify_direction(0.0, 1.0) == Direction.INCREASE
        assert classify_direction(0.0, -1.0) == Direction.DECREASE

    def test_a_different_pct_threshold_does_not_relabel_as_5pct(self) -> None:
        # 8% change is outside a 5% band but inside a 10% one - the label must reflect whichever
        # threshold was actually passed, not hardcode "5pct" regardless.
        assert classify_direction(100.0, 108.0, pct_threshold=5.0) == Direction.INCREASE
        assert classify_direction(100.0, 108.0, pct_threshold=10.0) == Direction.WITHIN_THRESHOLD


class TestMagnitudeBand:
    def test_band_boundaries_are_half_open_on_the_low_side(self) -> None:
        assert magnitude_band(4.99) == MagnitudeBand.UNDER_5
        assert magnitude_band(5.0) == MagnitudeBand.BETWEEN_5_AND_20
        assert magnitude_band(19.99) == MagnitudeBand.BETWEEN_5_AND_20
        assert magnitude_band(20.0) == MagnitudeBand.BETWEEN_20_AND_50
        assert magnitude_band(49.99) == MagnitudeBand.BETWEEN_20_AND_50
        assert magnitude_band(50.0) == MagnitudeBand.OVER_50

    def test_sign_is_irrelevant(self) -> None:
        assert magnitude_band(-30.0) == magnitude_band(30.0)


_MERGE_EDGES = frozenset({"B0C0", "C0D0"})
_SIGNAL_EDGES = frozenset({"A2B2", "B2C2", "C2D2", "D2E2"})


class TestBottleneckReason:
    def test_merge_edges(self) -> None:
        assert (
            bottleneck_reason("B0C0", merge_edges=_MERGE_EDGES, signalised_edges=_SIGNAL_EDGES)
            == BottleneckReason.MERGE
        )

    def test_signalised_edges(self) -> None:
        assert (
            bottleneck_reason("B2C2", merge_edges=_MERGE_EDGES, signalised_edges=_SIGNAL_EDGES)
            == BottleneckReason.SIGNAL
        )

    def test_everything_else_is_demand(self) -> None:
        assert (
            bottleneck_reason("A1B1", merge_edges=_MERGE_EDGES, signalised_edges=_SIGNAL_EDGES)
            == BottleneckReason.DEMAND
        )

    def test_edge_sets_are_a_parameter_not_a_hardcoded_default(self) -> None:
        # a different network's topology groups must change the classification - proves gold.py
        # carries no DEV-NET-specific knowledge of its own.
        assert (
            bottleneck_reason("A1B1", merge_edges=frozenset({"A1B1"}), signalised_edges=frozenset())
            == BottleneckReason.MERGE
        )


class TestTopBottleneckEdges:
    def test_ranks_by_time_loss_times_entered(self) -> None:
        edgedata = {
            "low": _edge(time_loss=1.0, entered=10.0),  # score 10
            "high": _edge(time_loss=5.0, entered=10.0),  # score 50
            "mid": _edge(time_loss=2.0, entered=10.0),  # score 20
        }
        assert top_bottleneck_edges(edgedata, k=2) == ["high", "mid"]

    def test_k_larger_than_available_edges(self) -> None:
        edgedata = {"only": _edge(time_loss=1.0, entered=1.0)}
        assert top_bottleneck_edges(edgedata, k=3) == ["only"]


class TestTopKByDelta:
    def test_ranks_by_absolute_change_and_reports_signed_value(self) -> None:
        baseline = {"E1": _edge(time_loss=10.0), "E2": _edge(time_loss=10.0)}
        intervention = {"E1": _edge(time_loss=12.0), "E2": _edge(time_loss=2.0)}
        result = top_k_by_delta(baseline, intervention, EdgeMeasure.TIME_LOSS, k=2)
        assert result == [("E2", -8.0), ("E1", 2.0)]

    def test_edge_missing_from_baseline_defaults_to_zero(self) -> None:
        baseline: dict[str, dict[str, float]] = {}
        intervention = {"NEW": _edge(time_loss=5.0)}
        assert top_k_by_delta(baseline, intervention, EdgeMeasure.TIME_LOSS, k=1) == [("NEW", 5.0)]


class TestEdgesAboveThreshold:
    def test_strictly_greater_than_excludes_the_boundary(self) -> None:
        edgedata = {"E1": _edge(occupancy=5.0), "E2": _edge(occupancy=5.01)}
        assert edges_above_threshold(edgedata, EdgeMeasure.OCCUPANCY, 5.0) == ["E2"]

    def test_result_is_sorted(self) -> None:
        edgedata = {"C": _edge(occupancy=9.0), "A": _edge(occupancy=9.0)}
        assert edges_above_threshold(edgedata, EdgeMeasure.OCCUPANCY, 1.0) == ["A", "C"]

    def test_no_edge_above_threshold_is_an_empty_list(self) -> None:
        edgedata = {"E1": _edge(occupancy=1.0)}
        assert edges_above_threshold(edgedata, EdgeMeasure.OCCUPANCY, 5.0) == []
