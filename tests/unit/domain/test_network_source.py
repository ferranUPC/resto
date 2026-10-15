import pytest

from resto.domain.value_objects.network_source import (
    BBox,
    GridNetwork,
    PlaceName,
    Polygon,
    RandomNetwork,
    SpiderNetwork,
)
from tests.unit.domain._fixtures import square_ring


def test_bbox_requires_south_below_north_and_west_below_east() -> None:
    BBox(south=41.38, west=2.15, north=41.40, east=2.18)
    with pytest.raises(ValueError, match="south"):
        BBox(south=41.40, west=2.15, north=41.38, east=2.18)
    with pytest.raises(ValueError, match="west"):
        BBox(south=41.38, west=2.18, north=41.40, east=2.15)


def test_bbox_rejects_coordinates_outside_the_globe() -> None:
    with pytest.raises(ValueError, match="latitude"):
        BBox(south=-91.0, west=0.0, north=0.0, east=1.0)
    with pytest.raises(ValueError, match="longitude"):
        BBox(south=0.0, west=0.0, north=1.0, east=181.0)


def test_polygon_takes_a_closed_ring_and_may_carry_its_osm_id() -> None:
    polygon = Polygon(ring=square_ring(), osm_id=347950)
    assert polygon.osm_id == 347950


def test_polygon_rejects_an_open_ring() -> None:
    with pytest.raises(ValueError, match="closed"):
        Polygon(ring=square_ring()[:-1])


def test_polygon_needs_at_least_three_distinct_vertices() -> None:
    with pytest.raises(ValueError, match="vertices"):
        Polygon(ring=((41.0, 2.0), (41.1, 2.1), (41.0, 2.0)))


def test_polygon_allows_200_vertices_and_no_more() -> None:
    def ring(vertices: int) -> tuple[tuple[float, float], ...]:
        points = tuple((41.0 + i * 1e-4, 2.0 + (i % 2) * 1e-4) for i in range(vertices))
        return (*points, points[0])

    Polygon(ring=ring(200))
    with pytest.raises(ValueError, match="200"):
        Polygon(ring=ring(201))


def test_polygon_rejects_coordinates_outside_the_globe() -> None:
    with pytest.raises(ValueError, match="latitude"):
        Polygon(ring=((95.0, 2.0), (41.1, 2.1), (41.1, 2.0), (95.0, 2.0)))


def test_place_name_requires_text() -> None:
    PlaceName(query="Eixample, Barcelona")
    with pytest.raises(ValueError, match="query"):
        PlaceName(query="  ")


@pytest.mark.parametrize(
    ("kwargs", "parameter"),
    [
        ({"x_number": 1}, "x_number"),
        ({"y_number": 1}, "y_number"),
        ({"x_length": 0.0}, "x_length"),
        ({"y_length": -5.0}, "y_length"),
    ],
)
def test_grid_rejects_out_of_range_parameters_by_name(
    kwargs: dict[str, float], parameter: str
) -> None:
    with pytest.raises(ValueError, match=parameter):
        GridNetwork(**kwargs)  # type: ignore[arg-type]


def test_grid_defaults_follow_netgenerate() -> None:
    grid = GridNetwork()
    assert (grid.x_number, grid.y_number, grid.x_length, grid.y_length) == (5, 5, 100.0, 100.0)


@pytest.mark.parametrize(
    ("kwargs", "parameter"),
    [
        ({"arm_number": 2}, "arm_number"),
        ({"circle_number": 0}, "circle_number"),
        ({"space_radius": 0.0}, "space_radius"),
    ],
)
def test_spider_rejects_out_of_range_parameters_by_name(
    kwargs: dict[str, float], parameter: str
) -> None:
    with pytest.raises(ValueError, match=parameter):
        SpiderNetwork(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kwargs", "parameter"),
    [
        ({"iterations": 0}, "iterations"),
        ({"min_distance": 0.0}, "min_distance"),
        ({"max_distance": 50.0, "min_distance": 100.0}, "max_distance"),
        ({"seed": -1}, "seed"),
    ],
)
def test_random_rejects_out_of_range_parameters_by_name(
    kwargs: dict[str, float], parameter: str
) -> None:
    with pytest.raises(ValueError, match=parameter):
        RandomNetwork(**{"seed": 1, **kwargs})  # type: ignore[arg-type]


def test_random_network_carries_its_seed() -> None:
    assert RandomNetwork(seed=7).seed == 7
    with pytest.raises(TypeError):
        RandomNetwork()  # type: ignore[call-arg]
