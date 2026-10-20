"""`OsmMap.trace`, the road between two points of a snapshot (E6.1/10): one-way roads, the speed
of each road and the streets the user named. The tool around it is tested in
`tools/test_network_import.py`."""

from __future__ import annotations

import math
from typing import Any
from xml.etree import ElementTree

import pytest

from resto.application.osm_map import (
    MAX_LINK_REACH_M,
    MAX_ZONE_M,
    MIN_ZONE_M,
    Area,
    DropRule,
    OsmMap,
    Unreached,
)
from resto.domain.services.geo import distance_m
from tests.unit.application.tools._osm_doubles import DIAGONAL_B23_OSM, HOSPITAL, MACIA

H = (HOSPITAL.lat, HOSPITAL.lon)
P = (MACIA.lat, MACIA.lon)

A, B = (41.3900, 2.1000), (41.3900, 2.1100)
"""Two nodes 834 m apart, farther than a point is ever moved to reach a road."""


def map_of(*ways: str) -> OsmMap:
    """Nodes 1 (A), 2 (B), 3 and 4 (a detour north of A to B) and the given ways."""
    nodes = (
        f'<node id="1" lat="{A[0]}" lon="{A[1]}"/><node id="2" lat="{B[0]}" lon="{B[1]}"/>'
        '<node id="3" lat="41.3905" lon="2.1000"/><node id="4" lat="41.3905" lon="2.1100"/>'
    )
    return OsmMap(ElementTree.fromstring(f"<osm>{nodes}{''.join(ways)}</osm>"))


def way(way_id: int, nodes: tuple[int, ...], **tags: str) -> str:
    refs = "".join(f'<nd ref="{n}"/>' for n in nodes)
    tagged = "".join(f'<tag k="{k}" v="{v}"/>' for k, v in tags.items())
    return f'<way id="{way_id}">{refs}{tagged}</way>'


def found(trace: dict[str, Any] | Unreached) -> dict[str, Any]:
    assert not isinstance(trace, Unreached), trace
    return trace


def streets_of(trace: dict[str, Any] | Unreached) -> list[str]:
    return [segment["name"] or segment["ref"] for segment in found(trace)["route"]]


def test_by_time_the_corridor_takes_the_motorway_and_by_length_the_slow_decoy() -> None:
    osm = OsmMap.read(DIAGONAL_B23_OSM)

    by_time = found(osm.trace(H, P))
    by_length = found(osm.trace(H, P, by="length"))

    assert "B-23" in streets_of(by_time) and "Carretera Reial" not in streets_of(by_time)
    assert streets_of(by_length) == ["Carretera Reial"]
    assert by_length["total_m"] < by_time["total_m"]
    assert by_time["minutes"] < by_length["minutes"]


def test_the_way_back_cannot_take_the_ramp_against_its_direction() -> None:
    back = OsmMap.read(DIAGONAL_B23_OSM).trace(P, H)

    assert streets_of(back) == ["Carretera Reial"]


@pytest.mark.parametrize(
    ("tags", "forward", "backward"),
    [
        pytest.param({"highway": "residential"}, True, True, id="two-way"),
        pytest.param({"highway": "residential", "oneway": "yes"}, True, False, id="oneway"),
        pytest.param({"highway": "residential", "oneway": "-1"}, False, True, id="against"),
        pytest.param(
            {"highway": "primary", "junction": "roundabout"}, True, False, id="roundabout"
        ),
        pytest.param({"highway": "motorway"}, True, False, id="motorway"),
        pytest.param({"highway": "motorway_link"}, True, False, id="motorway-link"),
        pytest.param({"highway": "motorway", "oneway": "no"}, True, True, id="two-way-motorway"),
    ],
)
def test_a_road_is_only_driven_in_the_directions_it_allows(
    tags: dict[str, str], forward: bool, backward: bool
) -> None:
    osm = map_of(way(1, (1, 2), **tags))

    assert (osm.trace(A, B) != Unreached(A)) is forward
    assert (osm.trace(B, A) != Unreached(B)) is backward


def test_a_point_no_road_can_take_it_to_the_other_has_no_drivable_path() -> None:
    osm = map_of(way(1, (1, 2), highway="residential", oneway="yes"))

    assert osm.trace(B, A) == Unreached(B)


@pytest.mark.parametrize(
    ("tags", "kmh"),
    [
        pytest.param({"highway": "primary", "maxspeed": "80"}, 80.0, id="km/h"),
        pytest.param({"highway": "primary", "maxspeed": "50 mph"}, 80.47, id="mph"),
        pytest.param({"highway": "primary", "maxspeed": "signals"}, 50.0, id="not-a-number"),
        pytest.param({"highway": "primary"}, 50.0, id="primary"),
        pytest.param({"highway": "motorway"}, 120.0, id="motorway"),
        pytest.param({"highway": "road"}, 20.0, id="unknown-class"),
    ],
)
def test_a_road_is_driven_at_its_maxspeed_or_the_default_of_its_class(
    tags: dict[str, str], kmh: float
) -> None:
    assert map_of(way(1, (1, 2), **tags)).ways[1].speed_kmh == pytest.approx(kmh, abs=0.01)


def test_the_default_speed_falls_from_one_road_class_to_the_next() -> None:
    classes = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified"]
    speeds = [map_of(way(1, (1, 2), highway=c)).ways[1].speed_kmh for c in classes]

    assert speeds == sorted(speeds, reverse=True) and len(set(speeds)) == len(speeds)


def test_a_street_the_user_named_wins_a_near_tie() -> None:
    # straight on the main road, 834 m; by the named street, north and back, about 945 m
    osm = map_of(
        way(1, (1, 2), highway="residential", name="Carrer Gran"),
        way(2, (1, 3, 4, 2), highway="residential", name="Carrer del Mig"),
    )

    assert streets_of(osm.trace(A, B)) == ["Carrer Gran"]
    assert streets_of(osm.trace(A, B, prefer=["carrer del mig"])) == ["Carrer del Mig"]


def test_a_street_the_user_named_is_suggested_however_short_its_stretch() -> None:
    osm = OsmMap.read(DIAGONAL_B23_OSM)

    plain = found(osm.trace(H, P))["suggested_selection"]
    named = found(osm.trace(H, P, prefer=["baix llobregat"]))["suggested_selection"]

    assert plain["names"] == ["Avinguda Diagonal"]
    assert named["names"] == ["Avinguda Diagonal", "Avinguda del Baix Llobregat"]


# -- zones suggested by a trace (E6.1/12) -----------------------------------------------------


def chain(*stretches: tuple[int, int, dict[str, str]]) -> OsmMap:
    """Nodes 1 to 40 along lat 41.39, 0.0005 degrees of longitude (about 42 m) apart, and a way
    for each (first node, last node, tags) that runs through the nodes between them."""
    nodes = "".join(
        f'<node id="{i}" lat="41.39" lon="{2.1 + 0.0005 * i:.4f}"/>' for i in range(1, 41)
    )
    ways = "".join(
        way(1000 + i, tuple(range(first, last + 1)), **tags)
        for i, (first, last, tags) in enumerate(stretches)
    )
    return OsmMap(ElementTree.fromstring(f"<osm>{nodes}{ways}</osm>"))


def trace_ends(osm: OsmMap, first: int, last: int) -> dict[str, Any]:
    return found(osm.trace(osm.nodes[first], osm.nodes[last]))["suggested_selection"]


def test_an_unnamed_ramp_on_the_route_is_suggested_as_a_zone_that_holds_it() -> None:
    osm = OsmMap.read(DIAGONAL_B23_OSM)

    suggested = found(osm.trace(H, P))["suggested_selection"]

    (zone,) = suggested["areas"]
    ramp = osm.ways[402]
    assert all(
        distance_m(tuple(zone["near"]), osm.nodes[n]) <= zone["radius_m"] for n in ramp.nodes
    )
    assert 10 <= zone["radius_m"] <= 5000
    assert suggested["names"] == ["Avinguda Diagonal"] and suggested["refs"] == ["B-23"]


def test_a_stretch_of_a_service_road_is_not_suggested_as_a_zone() -> None:
    osm = chain(
        (1, 3, {"highway": "service"}),
        (3, 6, {"highway": "primary", "name": "Avinguda"}),
        (6, 8, {"highway": "residential"}),
    )

    assert trace_ends(osm, 1, 8)["areas"] == []


def test_two_unnamed_stretches_close_to_each_other_give_one_zone() -> None:
    osm = chain(
        (1, 4, {"highway": "trunk_link"}),
        (4, 5, {"highway": "primary", "name": "Pont"}),
        (5, 8, {"highway": "primary_link"}),
    )

    assert len(trace_ends(osm, 1, 8)["areas"]) == 1


def test_two_unnamed_stretches_far_apart_give_two_zones() -> None:
    osm = chain(
        (1, 4, {"highway": "trunk_link"}),
        (4, 30, {"highway": "primary", "name": "Avinguda"}),
        (30, 34, {"highway": "primary_link"}),
    )

    assert len(trace_ends(osm, 1, 34)["areas"]) == 2


def test_the_radius_of_a_zone_stays_within_what_list_streets_accepts() -> None:
    tiny = chain((1, 2, {"highway": "motorway_link"}), (2, 5, {"highway": "primary", "name": "A"}))
    nodes = "".join(
        f'<node id="{i}" lat="41.39" lon="{2.0 + 0.02 * i:.4f}"/>' for i in range(1, 11)
    )
    ref = "".join(f'<nd ref="{i}"/>' for i in range(1, 11))
    huge = OsmMap(
        ElementTree.fromstring(
            f'<osm>{nodes}<way id="1">{ref}<tag k="highway" v="trunk"/></way></osm>'
        )
    )

    for osm, last in ((tiny, 5), (huge, 10)):
        (zone,) = trace_ends(osm, 1, last)["areas"]
        assert MIN_ZONE_M <= zone["radius_m"] <= MAX_ZONE_M


def test_a_route_with_only_named_or_ref_roads_has_no_zones_and_the_same_suggestion() -> None:
    osm = chain(
        (1, 5, {"highway": "primary", "name": "Avinguda"}),
        (5, 9, {"highway": "motorway", "ref": "B-23"}),
    )

    assert trace_ends(osm, 1, 9) == {
        "names": ["Avinguda"],
        "refs": ["B-23"],
        "connectors": "links",
        "areas": [],
    }


# -- whole ramps and roundabouts (E6.1/13) ---------------------------------------------------

STEP = 0.001
"""One step of latitude, about 111 m."""

RING = 100
"""First node of the roundabout; its 12 nodes (100 to 111) circle (41.3900, 2.1100)."""


def zone_map(*ways: str) -> OsmMap:
    """A road of nodes 0 to 12 going north from (41.39, 2.10), 111 m apart, a ring of 12 nodes 55 m
    around (41.3900, 2.1100) (nodes 100 to 111) and the given ways."""
    line = "".join(f'<node id="{i}" lat="{41.39 + i * STEP}" lon="2.1"/>' for i in range(13))
    ring = "".join(
        f'<node id="{RING + i}" lat="{41.39 + 0.0005 * math.sin(i * math.pi / 6)}" '
        f'lon="{2.11 + 0.0007 * math.cos(i * math.pi / 6)}"/>'
        for i in range(12)
    )
    return OsmMap(ElementTree.fromstring(f"<osm>{line}{ring}{''.join(ways)}</osm>"))


AT_THE_START = Area((41.39, 2.1), 150.0)
"""Holds nodes 0 and 1 of the road."""

AT_THE_RING = Area(
    (41.39 + 0.0005 * math.sin(math.pi / 4), 2.11 + 0.0007 * math.cos(math.pi / 4)), 25.0
)
"""Holds nodes 101 and 102 of the ring, both of the first way, and nothing else."""


def ring_ways(*, first: int = 1, **tags: str) -> list[str]:
    """The ring as four ways of three nodes each, the last closing it."""
    nodes = [RING + i for i in range(12)] + [RING]
    return [
        way(first + k, tuple(nodes[3 * k : 3 * k + 4]), highway="primary", junction="roundabout")
        for k in range(4)
    ]


def selected(osm: OsmMap, *areas: Area, drop: tuple[DropRule, ...] = ()) -> OsmMap:
    return osm.select([], [], "none", areas, drop)[0]


def test_a_zone_that_touches_one_way_of_a_roundabout_keeps_the_whole_ring() -> None:
    osm = zone_map(*ring_ways())

    kept, summary = osm.select([], [], "none", [AT_THE_RING])

    assert set(kept.ways) == {1, 2, 3, 4}
    assert len(kept.pieces(kept.ways)) == 1
    area = summary["areas"][0]
    assert area["by_class"]["primary"]["ways"] == 1
    ring_m = sum(osm.length_m(osm.ways[w]) for w in (1, 2, 3, 4))
    inside_m = distance_m(osm.nodes[RING + 1], osm.nodes[RING + 2])
    assert area["completed"]["ways"] == 4
    assert area["completed"]["length_m"] == pytest.approx(ring_m - inside_m, abs=1)


def test_a_ramp_cut_in_the_middle_is_kept_whole() -> None:
    osm = zone_map(way(1, tuple(range(7)), highway="motorway_link"))

    kept, summary = osm.select([], [], "none", [AT_THE_START])

    assert kept.ways[1].nodes == tuple(range(7))
    assert summary["areas"][0]["completed"]["ways"] == 1
    inside = summary["areas"][0]["by_class"]["motorway_link"]["length_m"]
    assert inside == pytest.approx(111, abs=2), "by_class counts the stretch inside"


def test_a_ramp_that_continues_in_other_links_is_followed_up_to_the_reach() -> None:
    # outside the zone: 111 m of the first, then 222 m each: 111, 333, 555 and 777 m
    osm = zone_map(
        way(1, (0, 1, 2), highway="motorway_link"),
        way(2, (2, 3, 4), highway="motorway_link"),
        way(3, (4, 5, 6), highway="motorway_link"),
        way(4, (6, 7, 8), highway="motorway_link"),
    )

    kept = selected(osm, AT_THE_START)

    assert set(kept.ways) == {1, 2, 3}
    assert 555 <= MAX_LINK_REACH_M < 777


def test_a_chain_of_764_m_does_not_come_in_whole() -> None:
    osm = zone_map(
        way(1, (0, 1, 2), highway="trunk_link"),
        way(2, tuple(range(2, 9)), highway="trunk_link"),
    )

    kept = selected(osm, AT_THE_START)

    assert set(kept.ways) == {1}


def test_a_road_of_another_class_is_still_cut_and_a_ramp_out_of_the_zone_stays_out() -> None:
    osm = zone_map(
        way(1, tuple(range(7)), highway="primary", name="Main"),
        way(2, tuple(range(7, 10)), highway="tertiary"),
        way(3, tuple(range(10, 13)), highway="motorway_link"),
    )

    kept = selected(osm, AT_THE_START)

    assert set(kept.ways) == {1}
    assert kept.ways[1].nodes == (0, 1)


def test_what_drop_removes_does_not_come_back_as_a_ramp_or_a_roundabout() -> None:
    osm = zone_map(
        *ring_ways(),
        way(9, tuple(range(7)), highway="motorway_link"),
        way(10, (8, 9), highway="primary", name="Main"),
    )
    around_the_ring = Area((41.39, 2.11), 200.0)

    no_links = osm.select(
        ["Main"], [], "none", [AT_THE_START], [DropRule(classes=("motorway_link",))]
    )[0]
    no_ring = osm.select(
        ["Main"], [], "none", [AT_THE_RING], [DropRule(classes=("primary",), area=around_the_ring)]
    )[0]

    assert 9 not in no_links.ways
    assert not {1, 2, 3, 4} & set(no_ring.ways)


def test_a_roundabout_is_completed_with_the_ways_no_rule_removes() -> None:
    osm = zone_map(*ring_ways())
    third_arm = Area(
        (41.39 + 0.0005 * math.sin(7 * math.pi / 6), 2.11 + 0.0007 * math.cos(7 * math.pi / 6)),
        10.0,
    )

    kept = selected(osm, AT_THE_RING, drop=(DropRule(classes=("primary",), area=third_arm),))

    assert set(kept.ways) == {1, 2, 4}


def test_the_same_zones_in_another_order_select_the_same_ways() -> None:
    osm = zone_map(
        *ring_ways(),
        way(9, (0, 1, 2), highway="motorway_link"),
        way(10, (2, 3, 4), highway="motorway_link"),
    )

    one, summary = osm.select([], [], "links", [AT_THE_START, AT_THE_RING])
    other, other_summary = osm.select([], [], "links", [AT_THE_RING, AT_THE_START])

    assert ElementTree.tostring(one._root) == ElementTree.tostring(other._root)
    assert summary["pieces"] == other_summary["pieces"]
