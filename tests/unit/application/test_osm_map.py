"""`OsmMap.trace`, the road between two points of a snapshot (E6.1/10): one-way roads, the speed
of each road and the streets the user named. The tool around it is tested in
`tools/test_network_import.py`."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree

import pytest

from resto.application.osm_map import OsmMap, Unreached
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
