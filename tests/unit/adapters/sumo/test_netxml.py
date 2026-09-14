"""SumolibNetworkQuery (E1.1): NetworkMCP's read-only queries over dev-net.net.xml."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.netxml import SumolibNetworkQuery

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"


@pytest.fixture(scope="module")
def query() -> SumolibNetworkQuery:
    return SumolibNetworkQuery(DEV_NET)


# --- has_edge / has_lane / has_tls -------------------------------------------------


def test_has_edge_true_for_a_known_edge_false_for_an_unknown_one(
    query: SumolibNetworkQuery,
) -> None:
    assert query.has_edge("A0A1") is True
    assert query.has_edge("NOPE") is False


def test_has_lane_true_within_the_lane_count_false_beyond_it(
    query: SumolibNetworkQuery,
) -> None:
    assert query.has_lane("A0A1", 0) is True
    assert query.has_lane("A0A1", 5) is False


def test_has_lane_false_for_an_unknown_edge(query: SumolibNetworkQuery) -> None:
    assert query.has_lane("NOPE", 0) is False


def test_has_tls_true_for_a_known_signal_false_for_an_unknown_one(
    query: SumolibNetworkQuery,
) -> None:
    assert query.has_tls("A2") is True
    assert query.has_tls("NOPE") is False


# --- get_edge ------------------------------------------------------------------------


def test_get_edge_returns_core_attributes_for_a_known_edge(query: SumolibNetworkQuery) -> None:
    edge = query.get_edge("A0A1")

    assert edge["id"] == "A0A1"
    assert edge["from_node"] == "A0"
    assert edge["to_node"] == "A1"
    assert edge["lane_count"] == 1
    assert edge["speed"] == pytest.approx(13.89)
    assert "passenger" in edge["allows"]


def test_get_edge_reports_lane_count_for_the_two_lane_bottleneck(
    query: SumolibNetworkQuery,
) -> None:
    # B0C0 is the 2->1 merge bottleneck built into DEV-NET (E0.5).
    assert query.get_edge("B0C0")["lane_count"] == 2


def test_get_edge_unknown_id_raises_key_error(query: SumolibNetworkQuery) -> None:
    with pytest.raises(KeyError):
        query.get_edge("NOPE")


# --- get_lanes -----------------------------------------------------------------------


def test_get_lanes_returns_one_entry_per_lane_with_index_and_speed(
    query: SumolibNetworkQuery,
) -> None:
    [lane] = query.get_lanes("A0A1")

    assert lane["id"] == "A0A1_0"
    assert lane["index"] == 0
    assert lane["speed"] == pytest.approx(13.89)


def test_get_lanes_returns_two_entries_for_the_two_lane_bottleneck(
    query: SumolibNetworkQuery,
) -> None:
    lanes = query.get_lanes("B0C0")

    assert [lane["index"] for lane in lanes] == [0, 1]


def test_get_lanes_unknown_edge_raises_key_error(query: SumolibNetworkQuery) -> None:
    with pytest.raises(KeyError):
        query.get_lanes("NOPE")


# --- get_neighbours --------------------------------------------------------------------


def test_get_neighbours_returns_the_outgoing_edges(query: SumolibNetworkQuery) -> None:
    assert set(query.get_neighbours("A0A1")) == {"A1A2", "A1B1"}


def test_get_neighbours_differs_from_its_reverse_edge(query: SumolibNetworkQuery) -> None:
    # get_neighbours is directional: A0A1's successors are not A1A0's.
    assert set(query.get_neighbours("A0A1")) != set(query.get_neighbours("A1A0"))


def test_get_neighbours_unknown_edge_raises_key_error(query: SumolibNetworkQuery) -> None:
    with pytest.raises(KeyError):
        query.get_neighbours("NOPE")


# --- shortest_path ---------------------------------------------------------------------


def test_shortest_path_returns_the_edge_sequence_between_two_edges(
    query: SumolibNetworkQuery,
) -> None:
    path = query.shortest_path("A0A1", "B0B1")

    assert path[0] == "A0A1"
    assert path[-1] == "B0B1"
    assert path == ["A0A1", "A1B1", "B1C1", "C1C0", "C0B0", "B0B1"]


def test_shortest_path_from_an_edge_to_itself_is_the_single_edge(
    query: SumolibNetworkQuery,
) -> None:
    assert query.shortest_path("A0A1", "A0A1") == ["A0A1"]


def test_shortest_path_unknown_edge_raises_key_error(query: SumolibNetworkQuery) -> None:
    with pytest.raises(KeyError):
        query.shortest_path("NOPE", "A0A1")
    with pytest.raises(KeyError):
        query.shortest_path("A0A1", "NOPE")


# --- edges_in_bbox -----------------------------------------------------------------------


def test_edges_in_bbox_returns_edges_overlapping_the_box(query: SumolibNetworkQuery) -> None:
    assert set(query.edges_in_bbox((0, 0, 50, 50))) == {"A0A1", "A1A0", "A0B0", "B0A0"}


def test_edges_in_bbox_excludes_edges_far_outside_the_box(query: SumolibNetworkQuery) -> None:
    found = query.edges_in_bbox((0, 0, 50, 50))
    assert "E0E1" not in found  # E0E1 sits near DEV-NET's far corner (x > 700).


def test_edges_in_bbox_is_empty_far_outside_the_network(query: SumolibNetworkQuery) -> None:
    # DEV-NET's convBoundary is 0,0,800,800 (eval/dev-net/README.md) - well clear of this box.
    assert query.edges_in_bbox((-1000, -1000, -900, -900)) == []


# --- capacity_estimate -------------------------------------------------------------------


def test_capacity_estimate_matches_the_greenshields_formula_for_a_known_edge(
    query: SumolibNetworkQuery,
) -> None:
    # ADR-0015: q_max = v_free[km/h] * k_jam / 4, k_jam = 1000 / 7.5 veh/km/lane, per lane.
    # A0A1: speed 13.89 m/s (=50.0 km/h), 1 lane -> 50.0 * (1000/7.5) / 4.
    assert query.capacity_estimate("A0A1") == pytest.approx(1666.8, rel=1e-3)


def test_capacity_estimate_scales_linearly_with_lane_count(query: SumolibNetworkQuery) -> None:
    # B0C0 has the same speed as A0A1 but 2 lanes instead of 1 (E0.5 bottleneck).
    assert query.capacity_estimate("B0C0") == pytest.approx(
        2 * query.capacity_estimate("A0A1")
    )


def test_capacity_estimate_unknown_edge_raises_key_error(query: SumolibNetworkQuery) -> None:
    with pytest.raises(KeyError):
        query.capacity_estimate("NOPE")


# --- get_tls -------------------------------------------------------------------------------


def test_get_tls_returns_the_controlled_edges(query: SumolibNetworkQuery) -> None:
    assert set(query.get_tls("A2")["controlled_edges"]) == {"A1A2", "A3A2", "B2A2"}


def test_get_tls_program_phase_durations_sum_to_a_full_cycle(
    query: SumolibNetworkQuery,
) -> None:
    [phases] = query.get_tls("A2")["programs"].values()
    assert sum(duration for _state, duration in phases) == 90


def test_get_tls_unknown_id_raises_key_error(query: SumolibNetworkQuery) -> None:
    with pytest.raises(KeyError):
        query.get_tls("NOPE")
