"""`NominatimGeocoder` against a loopback server with saved responses (ADR-0045 §2, §3)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from resto.adapters.osm.nominatim import DEFAULT_USER_AGENT, NominatimGeocoder
from resto.application.ports.osm import ExternalServiceError, LocatedPlace, PlaceRejected
from resto.domain.value_objects.network_source import MAX_POLYGON_VERTICES, PlaceName
from tests.unit.adapters.osm._server import FakeService, Reply, fake_service

NO_WAIT = 0.0


def _geocoder(service: FakeService, tmp_path: Path, **kwargs: float) -> NominatimGeocoder:
    return NominatimGeocoder(
        tmp_path / "cache", base_url=service.url, min_interval_s=kwargs.get("interval", NO_WAIT)
    )


def test_a_boundary_relation_resolves_to_a_polygon_in_lat_lon(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_boundary.json"))

        polygon = _geocoder(service, tmp_path).resolve(PlaceName("Sant Gervasi"))

    assert polygon.osm_id == 347950
    assert polygon.ring[0] == (41.39, 2.15)  # GeoJSON is lon,lat; the domain is lat,lon
    assert polygon.ring[0] == polygon.ring[-1]
    assert len(polygon.ring) == 5


def test_the_query_names_the_place_and_asks_for_geojson(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_boundary.json"))

        _geocoder(service, tmp_path).resolve(PlaceName("Sant Gervasi"))

    query = parse_qs(urlparse(service.received[0].path).query)
    assert query["q"] == ["Sant Gervasi"]
    assert query["format"] == ["jsonv2"]
    assert query["polygon_geojson"] == ["1"]


def test_the_largest_part_of_a_multipolygon_is_kept(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_multipolygon.json"))

        polygon = _geocoder(service, tmp_path).resolve(PlaceName("Two Islands"))

    assert (41.1, 2.1) in polygon.ring
    assert (41.0, 2.0) not in polygon.ring


def test_a_detailed_boundary_is_simplified_to_the_vertex_limit(tmp_path: Path) -> None:
    ring = [
        [
            2.0 + 0.01 * math.cos(2 * math.pi * i / 300),
            41.0 + 0.01 * math.sin(2 * math.pi * i / 300),
        ]
        for i in range(300)
    ]
    ring.append(ring[0])
    body = [
        {
            "osm_type": "relation",
            "osm_id": 777,
            "category": "boundary",
            "type": "administrative",
            "geojson": {"type": "Polygon", "coordinates": [ring]},
        }
    ]
    with fake_service() as service:
        service.answer(Reply(json.dumps(body).encode()))

        polygon = _geocoder(service, tmp_path).resolve(PlaceName("Round Town"))

    assert 100 < len(polygon.ring) - 1 <= MAX_POLYGON_VERTICES


@pytest.mark.parametrize(
    ("fixture", "reason_has"),
    [
        ("nominatim_point.json", "node"),
        ("nominatim_office.json", "office"),
        ("nominatim_empty.json", "no result"),
    ],
)
def test_anything_but_a_boundary_relation_is_rejected_with_a_reason(
    tmp_path: Path, fixture: str, reason_has: str
) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture(fixture))

        with pytest.raises(PlaceRejected) as raised:
            _geocoder(service, tmp_path).resolve(PlaceName("Eixample"))

    assert reason_has in raised.value.reason


def test_the_user_agent_is_sent_and_is_our_own(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_boundary.json"))

        _geocoder(service, tmp_path).resolve(PlaceName("Sant Gervasi"))

    sent = service.received[0].headers["user-agent"]
    assert sent == DEFAULT_USER_AGENT
    assert "python" not in sent.lower()


def test_requests_are_spaced_by_the_minimum_interval(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_boundary.json"))
        geocoder = _geocoder(service, tmp_path, interval=0.3)

        geocoder.resolve(PlaceName("one"))
        geocoder.resolve(PlaceName("two"))

    first, second = service.received
    assert second.at - first.at >= 0.3


def test_the_default_spacing_is_one_request_per_second(tmp_path: Path) -> None:
    assert NominatimGeocoder(tmp_path).min_interval_s == 1.0


def test_a_repeated_name_is_answered_from_the_cache_without_a_request(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_boundary.json"))

        first = _geocoder(service, tmp_path).resolve(PlaceName("Sant Gervasi"))
        again = _geocoder(service, tmp_path).resolve(PlaceName("  sant gervasi "))

    assert again == first
    assert len(service.received) == 1


def test_a_rejection_is_not_cached_as_a_polygon(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(
            Reply.fixture("nominatim_point.json"), Reply.fixture("nominatim_boundary.json")
        )
        geocoder = _geocoder(service, tmp_path)

        with pytest.raises(PlaceRejected):
            geocoder.resolve(PlaceName("Eixample"))
        polygon = geocoder.resolve(PlaceName("Eixample"))

    assert polygon.osm_id == 347950


@pytest.mark.parametrize(
    "reply",
    [
        Reply(b"slow down", status=429, content_type="text/plain"),
        Reply(b"oops", status=503, content_type="text/plain"),
        Reply(b"<html>not json</html>", content_type="text/html"),
    ],
)
def test_a_failing_service_names_nominatim(tmp_path: Path, reply: Reply) -> None:
    with fake_service() as service:
        service.answer(reply)

        with pytest.raises(ExternalServiceError) as raised:
            _geocoder(service, tmp_path).resolve(PlaceName("Eixample"))

    assert raised.value.service == "nominatim"
    assert "nominatim" in str(raised.value)


def test_an_unreachable_service_names_nominatim(tmp_path: Path) -> None:
    geocoder = NominatimGeocoder(tmp_path, base_url="http://127.0.0.1:9", min_interval_s=NO_WAIT)

    with pytest.raises(ExternalServiceError) as raised:
        geocoder.resolve(PlaceName("Eixample"))

    assert raised.value.service == "nominatim"


# -- locating a point (ADR-0046) ----------------------------------------------------------------


def test_a_point_of_interest_is_located_with_its_kind_and_name(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_hospital.json"))

        place = _geocoder(service, tmp_path).locate("Hospital Broggi")

    assert place == LocatedPlace(
        query="Hospital Broggi",
        lat=41.3852412,
        lon=2.043679,
        category="amenity",
        type="hospital",
        name="Hospital Sant Joan Despí Moisès Broggi",
    )
    query = parse_qs(urlparse(service.received[0].path).query)
    assert query["q"] == ["Hospital Broggi"] and query["limit"] == ["1"]
    assert "polygon_geojson" not in query


def test_a_place_nominatim_does_not_know_is_located_as_nothing(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply.fixture("nominatim_empty.json"))

        assert _geocoder(service, tmp_path).locate("Atlantis") is None


def test_a_located_point_is_cached_apart_from_the_boundary_of_the_same_name(
    tmp_path: Path,
) -> None:
    with fake_service() as service:
        service.answer(
            Reply.fixture("nominatim_hospital.json"), Reply.fixture("nominatim_boundary.json")
        )
        geocoder = _geocoder(service, tmp_path)

        first = geocoder.locate("Sant Gervasi")
        again = _geocoder(service, tmp_path).locate(" sant gervasi ")
        polygon = geocoder.resolve(PlaceName("Sant Gervasi"))

    assert again is not None and first is not None
    assert (again.lat, again.lon) == (first.lat, first.lon)
    assert polygon.osm_id == 347950
    assert len(service.received) == 2


def test_locating_with_a_failing_service_names_nominatim(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply(b"oops", status=503, content_type="text/plain"))

        with pytest.raises(ExternalServiceError) as raised:
            _geocoder(service, tmp_path).locate("Hospital Broggi")

    assert raised.value.service == "nominatim"
