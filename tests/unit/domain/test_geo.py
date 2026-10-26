"""`area_km2`, `distance_m`, `inside_by_m`, `bbox_around` and `expand_area`, on worked figures."""

from __future__ import annotations

import pytest

from resto.domain.services.geo import (
    MAX_MARGIN_PCT,
    area_km2,
    bbox_around,
    distance_m,
    expand_area,
    format_coordinate,
    inside_by_m,
)
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


TOOTHED = Polygon(
    (
        (41.370, 2.130),
        (41.370, 2.150),
        (41.376, 2.145),  # a notch in the south side
        (41.380, 2.160),
        (41.390, 2.160),
        (41.390, 2.130),
        (41.370, 2.130),
    ),
    osm_id=4130114,
)


def test_a_grown_ring_holds_every_original_point_at_least_the_margin_inside() -> None:
    grown = expand_area(TOOTHED, 5)

    assert isinstance(grown, Polygon)
    side_m = 1000 * area_km2(TOOTHED) ** 0.5
    for point in TOOTHED.ring:
        assert inside_by_m(grown, point) >= 0.05 * side_m - 0.1


def test_a_grown_polygon_keeps_its_osm_id_and_stays_closed() -> None:
    grown = expand_area(TOOTHED, 5)

    assert isinstance(grown, Polygon)
    assert grown.osm_id == 4130114
    assert grown.ring[0] == grown.ring[-1]


def test_a_grown_polygon_fills_the_notches_of_the_original() -> None:
    grown = expand_area(TOOTHED, 5)

    assert area_km2(grown) > area_km2(TOOTHED) * 1.1


def test_a_grown_box_is_still_a_box_moved_the_margin_on_every_side() -> None:
    box = BBox(41.35, 2.10, 41.45, 2.20)
    margin_m = 0.05 * 1000 * area_km2(box) ** 0.5

    grown = expand_area(box, 5)

    assert isinstance(grown, BBox)
    assert distance_m((box.south, box.west), (grown.south, box.west)) == pytest.approx(
        margin_m, rel=0.01
    )
    assert distance_m((box.south, box.west), (box.south, grown.west)) == pytest.approx(
        margin_m, rel=0.01
    )
    assert grown.north > box.north and grown.east > box.east


def test_no_margin_leaves_the_area_as_it_was() -> None:
    box = BBox(41.35, 2.10, 41.45, 2.20)

    assert expand_area(box, 0) == box
    assert expand_area(TOOTHED, 0) == TOOTHED


def test_the_margin_is_a_share_of_the_side_of_a_square_of_the_same_surface() -> None:
    # a square of side s grown by m on every side has area (s + 2m)^2
    square = BBox(41.35, 2.10, 41.3589933, 2.1119)
    side_km = area_km2(square) ** 0.5

    grown = area_km2(expand_area(square, 10))

    assert grown == pytest.approx((side_km * 1.2) ** 2, rel=0.01)


def test_a_polygon_of_fewer_than_three_distinct_points_or_on_one_line_cannot_be_grown() -> None:
    line = Polygon(((41.0, 2.0), (41.5, 2.0), (42.0, 2.0), (41.0, 2.0)))

    with pytest.raises(ValueError, match="line"):
        expand_area(line, 5)


@pytest.mark.parametrize(
    ("degrees", "text"),
    [(41.3896127, "41.3896127"), (2.15, "2.15"), (41.0, "41"), (0.00000001, "0"), (-2.1, "-2.1")],
)
def test_a_coordinate_is_written_with_up_to_seven_decimals_and_no_exponent(
    degrees: float, text: str
) -> None:
    assert format_coordinate(degrees) == text


@pytest.mark.parametrize("margin", [-1.0, MAX_MARGIN_PCT + 1])
def test_a_margin_out_of_range_is_refused(margin: float) -> None:
    with pytest.raises(ValueError, match="margin_pct"):
        expand_area(TOOTHED, margin)
