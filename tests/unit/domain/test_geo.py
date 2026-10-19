"""`area_km2`, `distance_m`, `inside_by_m` and `bbox_around`, checked against worked figures."""

from __future__ import annotations

import pytest

from resto.domain.services.geo import area_km2, bbox_around, distance_m, inside_by_m
from resto.domain.value_objects.network_source import BBox, Polygon


def test_a_one_degree_box_on_the_equator_is_about_12364_km2() -> None:
    # 111.195 km per degree on a sphere of radius 6371 km: 111.195 ** 2
    assert area_km2(BBox(south=-0.5, west=0.0, north=0.5, east=1.0)) == pytest.approx(
        12364.0, rel=0.01
    )


def test_a_box_shrinks_with_latitude() -> None:
    equator = area_km2(BBox(0.0, 0.0, 0.1, 0.1))
    barcelona = area_km2(BBox(41.35, 2.10, 41.45, 2.20))

    # cos(41.4 deg) = 0.75
    assert barcelona == pytest.approx(equator * 0.75, rel=0.01)


def test_a_polygon_has_the_area_of_its_ring_whatever_the_direction() -> None:
    triangle = ((0.0, 0.0), (0.0, 0.1), (0.1, 0.0), (0.0, 0.0))
    reversed_ring = tuple(reversed(triangle))

    expected = 0.5 * 11.1195 * 11.1195
    assert area_km2(Polygon(triangle)) == pytest.approx(expected, rel=0.01)
    assert area_km2(Polygon(reversed_ring)) == pytest.approx(expected, rel=0.01)


def test_a_degree_north_is_about_111_km_and_a_degree_east_less_away_from_the_equator() -> None:
    assert distance_m((41.0, 2.0), (42.0, 2.0)) == pytest.approx(111_195, rel=0.001)
    # cos(41.39 deg) = 0.7503
    assert distance_m((41.39, 2.10), (41.39, 2.15)) == pytest.approx(4171, rel=0.01)


BOX = BBox(south=41.37, west=2.06, north=41.40, east=2.15)


@pytest.mark.parametrize(
    ("point", "depth"),
    [
        pytest.param((41.38, 2.10), 1112, id="inside-nearest-the-south-edge"),
        pytest.param((41.365, 2.10), -556, id="outside-south"),
        pytest.param((41.38, 2.16), -834, id="outside-east"),
    ],
)
def test_depth_is_the_distance_to_the_border_negative_outside(
    point: tuple[float, float], depth: float
) -> None:
    assert inside_by_m(BOX, point) == pytest.approx(depth, rel=0.01)


def test_depth_in_a_polygon_follows_its_slanted_side() -> None:
    triangle = Polygon(((41.0, 2.0), (41.0, 2.1), (41.1, 2.0), (41.0, 2.0)))

    assert inside_by_m(triangle, (41.01, 2.01)) > 0
    assert inside_by_m(triangle, (41.09, 2.09)) < 0


def test_a_box_around_points_holds_them_with_the_margin_on_every_side() -> None:
    box = bbox_around([(41.38, 2.10), (41.39, 2.12)], 300)

    assert distance_m((box.south, 2.10), (41.38, 2.10)) == pytest.approx(300, rel=0.01)
    assert distance_m((41.39, box.east), (41.39, 2.12)) == pytest.approx(300, rel=0.01)
    assert (box.north > 41.39, box.west < 2.10) == (True, True)
