"""`area_km2`: the size of an area of interest, checked against worked figures."""

from __future__ import annotations

import pytest

from resto.domain.services.geo import area_km2
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
