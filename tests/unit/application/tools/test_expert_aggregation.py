"""Expert v1 aggregation tools (ADR-0022): means across runs, per-vehicle measures undefined without
traffic, rankings, baseline vs treatment comparisons, allow-list. Hand-computed canned edgedata."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

import pytest

from resto.adapters.persistence.memory import InMemoryResultRepository
from resto.application.tools.expert import (
    NotAvailableError,
    compare_edges,
    compare_kpis,
    edge_stats,
    rank_edges,
)
from resto.domain.value_objects.kpis import Kpis
from tests.unit.domain._samples import simulation_result


def _edge(tt: float, occ: float, loss: float, entered: float) -> dict[str, float]:
    sampled = 100.0 if entered else 0.0
    return {
        "sampled_seconds": sampled, "travel_time": tt, "speed": 10.0 if entered else 0.0,
        "occupancy": occ, "density": occ * 2, "time_loss": loss, "waiting_time": 0.0,
        "entered": entered, "left": entered,
    }


EDGEDATA: dict[str, dict[str, dict[str, float]]] = {
    # baseline runs
    "b1": {"A": _edge(20, 2.0, 100, 10), "B": _edge(30, 5.0, 300, 10), "C": _edge(15, 1.0, 10, 5)},
    "b2": {"A": _edge(22, 4.0, 120, 12), "B": _edge(34, 3.0, 340, 10), "C": _edge(15, 1.0, 20, 5)},
    # treatment runs: C is closed (no traffic in either run)
    "t1": {"A": _edge(40, 6.0, 400, 10), "B": _edge(31, 4.0, 310, 10), "C": _edge(0, 0.0, 0, 0)},
    "t2": {"A": _edge(44, 8.0, 440, 10), "B": _edge(33, 4.0, 330, 10), "C": _edge(0, 0.0, 0, 0)},
}
AVAILABLE = frozenset(EDGEDATA)


class CannedResults(InMemoryResultRepository):
    def query_edgedata(
        self, result_id: str, edge_ids: Iterable[str], window: tuple[float, float] | None
    ) -> Mapping[str, Any]:
        data = EDGEDATA[result_id]
        wanted = list(edge_ids)
        return {e: v for e, v in data.items() if not wanted or e in wanted}


@pytest.fixture
def results() -> CannedResults:
    repo = CannedResults()
    for rid, delay in (("b1", 28.0), ("b2", 30.0), ("t1", 32.0), ("t2", 34.0)):
        kpis = Kpis(mean_delay=delay, mean_travel_time=90.0, teleports=0, departed=100, arrived=99)
        repo.store(replace(simulation_result(), result_id=rid, kpis=kpis))
    return repo


def test_edge_stats_averages_across_runs_with_spread(results: CannedResults) -> None:
    stats = edge_stats(results, AVAILABLE, ["b1", "b2"], ["A"])["A"]
    assert stats["occupancy"] == {"mean": 3.0, "std": 1.414, "runs": 2}
    assert stats["travel_time"]["mean"] == 21.0
    assert stats["time_loss_per_vehicle"]["mean"] == 10.0  # 100/10 and 120/12


def test_per_vehicle_means_are_null_without_traffic_but_totals_are_zero(
    results: CannedResults,
) -> None:
    stats = edge_stats(results, AVAILABLE, ["t1", "t2"], ["C"])["C"]
    assert stats["travel_time"] is None
    assert stats["speed"] is None
    assert stats["time_loss_per_vehicle"] is None
    assert stats["time_loss"] == {"mean": 0.0, "std": 0.0, "runs": 2}
    assert stats["occupancy"]["mean"] == 0.0


def test_rank_edges_by_mean_with_threshold_and_top_k(results: CannedResults) -> None:
    ranked = rank_edges(results, AVAILABLE, ["b1", "b2"], "time_loss", top_k=2)
    assert [r["edge_id"] for r in ranked] == ["B", "A"]
    above = rank_edges(results, AVAILABLE, ["b1", "b2"], "occupancy", min_value=2.5)
    assert [r["edge_id"] for r in above] == ["B", "A"]  # 4.0 and 3.0; C is 1.0
    closed = rank_edges(results, AVAILABLE, ["t1", "t2"], "travel_time")
    assert "C" not in [r["edge_id"] for r in closed]


def test_compare_edges_ranks_by_absolute_difference(results: CannedResults) -> None:
    rows = compare_edges(results, AVAILABLE, ["b1", "b2"], ["t1", "t2"], "time_loss", top_k=2)
    # A: 110 -> 420 (+310); C: 15 -> 0 (-15, closed); B: 320 -> 320 (0)
    assert [r["edge_id"] for r in rows] == ["A", "C"]
    assert rows[0]["delta"] == 310.0
    assert rows[0]["relative_change_pct"] == pytest.approx(281.8)


def test_compare_edges_on_named_edges_keeps_undefined_per_vehicle_means(
    results: CannedResults,
) -> None:
    (row,) = compare_edges(
        results, AVAILABLE, ["b1", "b2"], ["t1", "t2"], "travel_time", edge_ids=["C"]
    )
    assert row["baseline"]["mean"] == 15.0
    assert row["treatment"] is None
    assert row["delta"] is None


def test_compare_kpis_reports_network_change(results: CannedResults) -> None:
    kpis = compare_kpis(results, AVAILABLE, ["b1", "b2"], ["t1", "t2"])
    assert kpis["mean_delay"]["delta"] == 4.0  # 29 -> 33
    assert kpis["mean_delay"]["relative_change_pct"] == pytest.approx(13.8)


def test_aggregation_tools_respect_the_allow_list(results: CannedResults) -> None:
    only_baseline = frozenset({"b1", "b2"})
    with pytest.raises(NotAvailableError):
        edge_stats(results, only_baseline, ["t1"], ["A"])
    with pytest.raises(NotAvailableError):
        compare_kpis(results, only_baseline, ["b1"], ["t1"])


def test_unknown_measure_and_empty_inputs_are_errors(results: CannedResults) -> None:
    with pytest.raises(ValueError, match="unknown measure"):
        rank_edges(results, AVAILABLE, ["b1"], "delay")
    with pytest.raises(ValueError, match="at least one"):
        rank_edges(results, AVAILABLE, [], "time_loss")
    with pytest.raises(ValueError, match="name the edges"):
        edge_stats(results, AVAILABLE, ["b1"], [])
