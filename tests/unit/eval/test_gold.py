"""Unit tests for the question bank's pure gold-answer math (eval/question_bank/gold.py,
work-plan E3.2). No SUMO, no DatabaseMCP - synthetic `query_edgedata`-shaped mappings, a toy
topology, and DEV-NET's topology read from its committed `.net.xml` (ADR-0029's cases)."""

from __future__ import annotations

import math

import pytest
from eval.question_bank.build import dev_net_topology
from eval.question_bank.gold import (
    Direction,
    EdgeMeasure,
    MagnitudeBand,
    NetworkTopology,
    bottleneck_causes,
    classify_direction,
    edges_above_threshold,
    magnitude_band,
    mean_edgedata,
    pct_change,
    top_bottleneck_edges,
    top_k_by_delta,
)

from resto.domain.value_objects.answer_value import BottleneckCause
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.time_window import TimeWindow


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


def _intervention(target: EdgeTarget | LaneTarget | TlsTarget | None) -> Intervention:
    if target is None:
        return Intervention(
            InterventionType.DEMAND_SCALE, None, {"factor": 1.2}, window=TimeWindow(0.0, 300.0)
        )
    kind = (
        InterventionType.SIGNAL_PROGRAM
        if isinstance(target, TlsTarget)
        else InterventionType.LANE_CLOSURE
    )
    return Intervention(kind, target, window=TimeWindow(0.0, 300.0))


# a toy corridor W -> X -> Y -> Z plus a side street S -> X; one lane drop (XY), no traffic light
# at Y or Z, a traffic light at X controlling the side street only
_TOY = NetworkTopology(
    edge_nodes={"WX": ("W", "X"), "XY": ("X", "Y"), "YZ": ("Y", "Z"), "SX": ("S", "X")},
    tls_controlled_edges={"X": frozenset({"SX"})},
    lane_drop_edges=frozenset({"XY"}),
)


@pytest.fixture(scope="module")
def dev_net() -> NetworkTopology:
    return dev_net_topology()


class TestBottleneckCauses:
    def test_a_known_lane_drop_is_a_merge(self) -> None:
        assert bottleneck_causes(["XY"], (), _TOY) == [BottleneckCause.MERGE]

    def test_an_edge_with_nothing_at_its_end_is_demand(self) -> None:
        assert bottleneck_causes(["YZ"], (), _TOY) == [BottleneckCause.DEMAND]

    def test_one_cause_per_edge_in_rank_order(self) -> None:
        # WX ends where the higher-ranked XY starts: its queue comes from downstream
        assert bottleneck_causes(["YZ", "XY", "WX"], (), _TOY) == [
            BottleneckCause.DEMAND,
            BottleneckCause.MERGE,
            BottleneckCause.SPILLBACK,
        ]

    def test_spillback_only_looks_at_higher_ranked_edges(self) -> None:
        assert bottleneck_causes(["WX", "XY"], (), _TOY)[0] is BottleneckCause.DEMAND

    def test_an_edge_matching_several_causes_gets_the_first(self) -> None:
        # XY is the target (intervention), a lane drop (merge) and feeds a higher-ranked YZ
        # (spillback): intervention wins
        causes = bottleneck_causes(["YZ", "XY"], (_intervention(EdgeTarget("XY")),), _TOY)
        assert causes == [BottleneckCause.DEMAND, BottleneckCause.INTERVENTION]
        # without the intervention, merge wins over spillback
        assert bottleneck_causes(["YZ", "XY"], (), _TOY)[1] is BottleneckCause.MERGE

    def test_signal_means_controlled_by_a_traffic_light_not_ending_at_its_node(self) -> None:
        # WX ends at X, which has a traffic light, but the light does not control WX
        assert bottleneck_causes(["SX", "WX"], (), _TOY) == [
            BottleneckCause.SIGNAL,
            BottleneckCause.DEMAND,
        ]

    def test_s03_the_direct_feeder_of_a_closed_edge_is_intervention(
        self, dev_net: NetworkTopology
    ) -> None:
        closure = _intervention(LaneTarget("B0C0", 0))
        causes = bottleneck_causes(["B1B0", "A2B2", "E3E2"], (closure,), dev_net)
        assert causes[0] is BottleneckCause.INTERVENTION

    def test_s13_an_edge_feeding_a_higher_ranked_edge_is_spillback(
        self, dev_net: NetworkTopology
    ) -> None:
        program = _intervention(TlsTarget("C2"))
        causes = bottleneck_causes(["B2C2", "D2C2", "A2B2"], (program,), dev_net)
        assert causes == [
            BottleneckCause.INTERVENTION,
            BottleneckCause.INTERVENTION,
            BottleneckCause.SPILLBACK,
        ]

    def test_s14_an_edge_controlled_by_the_target_traffic_light_is_intervention(
        self, dev_net: NetworkTopology
    ) -> None:
        program = _intervention(TlsTarget("B2"))
        causes = bottleneck_causes(["C2B2", "B2A2", "D2C2"], (program,), dev_net)
        assert causes == [
            BottleneckCause.INTERVENTION,
            BottleneckCause.SIGNAL,
            BottleneckCause.SPILLBACK,
        ]

    def test_s10_a_signalised_edge_far_from_the_intervention_is_signal(
        self, dev_net: NetworkTopology
    ) -> None:
        speed_limit = _intervention(LaneTarget("C1D1", 0))
        causes = bottleneck_causes(["A2B2", "E3E2", "B2C2"], (speed_limit,), dev_net)
        assert causes[0] is BottleneckCause.SIGNAL

    def test_s17_demand_scale_never_yields_intervention(self, dev_net: NetworkTopology) -> None:
        causes = bottleneck_causes(["A2B2", "C2D2", "B1B2"], (_intervention(None),), dev_net)
        assert BottleneckCause.INTERVENTION not in causes
        assert causes == [BottleneckCause.SIGNAL] * 3


class TestTopBottleneckEdges:
    def test_ranks_by_total_time_loss_without_weighting_by_flow_again(self) -> None:
        # time_loss is already a total over vehicles: a busy edge with little total delay must not
        # outrank a quieter edge where more vehicle-seconds are lost
        edgedata = {
            "busy_low_loss": _edge(time_loss=100.0, entered=20.0),
            "quiet_high_loss": _edge(time_loss=150.0, entered=5.0),
            "mid": _edge(time_loss=120.0, entered=10.0),
        }
        assert top_bottleneck_edges(edgedata, k=2) == ["quiet_high_loss", "mid"]

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
