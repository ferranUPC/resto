"""`OverpassOsmSource` against a loopback server with saved responses (ADR-0045 §3, §7)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs

import pytest

from resto.adapters.osm.overpass import DEFAULT_USER_AGENT, OverpassOsmSource
from resto.application.ports.osm import ExternalServiceError, OsmLimits
from resto.domain.value_objects.network_source import BBox, Polygon
from tests.unit.adapters.osm._server import FIXTURES, FakeService, Reply, fake_service

AREA = Polygon(
    ((41.390, 2.150), (41.390, 2.160), (41.398, 2.160), (41.398, 2.150), (41.390, 2.150))
)
OSM = Reply.fixture("overpass_small.osm", content_type="application/osm3s+xml")


def _source(service: FakeService, limits: OsmLimits | None = None) -> OverpassOsmSource:
    return OverpassOsmSource(base_url=service.url, limits=limits or OsmLimits())


def _query(service: FakeService, index: int = 0) -> str:
    return parse_qs(service.received[index].body.decode())["data"][0]


def test_the_snapshot_is_the_downloaded_osm_as_an_artifact(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(OSM)

        snapshot = _source(service).fetch(AREA, tmp_path)

    assert snapshot.kind == "osm"
    assert snapshot.path.read_bytes() == (FIXTURES / "overpass_small.osm").read_bytes()
    assert snapshot.path.parent == tmp_path.resolve()


def test_the_query_filters_by_poly_in_lat_lon_and_takes_whole_ways(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(OSM)

        _source(service).fetch(AREA, tmp_path)

    query = _query(service)
    assert 'poly:"41.39 2.15 41.39 2.16 41.398 2.16 41.398 2.15"' in query
    assert 'way["highway"]' in query
    assert 'way["railway"]' in query  # the rail profile needs them, the snapshot is per polygon
    assert "(._;>;)" in query


def test_a_second_fetch_of_the_same_polygon_does_not_download_again(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(OSM)
        source = _source(service)

        first = source.fetch(AREA, tmp_path)
        second = source.fetch(Polygon(AREA.ring, osm_id=42), tmp_path)

    assert len(service.received) == 1
    assert second == first


def test_another_polygon_is_downloaded_on_its_own(tmp_path: Path) -> None:
    other = BBox(south=41.0, west=2.0, north=41.01, east=2.01)
    with fake_service() as service:
        service.answer(OSM)
        source = _source(service)

        first = source.fetch(AREA, tmp_path)
        second = source.fetch(other, tmp_path)

    assert len(service.received) == 2
    assert second.path != first.path
    assert 'poly:"41 2 41 2.01 41.01 2.01 41.01 2"' in _query(service, 1)


def test_the_limits_come_from_the_configuration(tmp_path: Path) -> None:
    limits = OsmLimits(overpass_maxsize_bytes=1234, overpass_timeout_s=17)
    with fake_service() as service:
        service.answer(OSM)

        _source(service, limits).fetch(AREA, tmp_path)

    query = _query(service)
    assert "[maxsize:1234]" in query
    assert "[timeout:17]" in query


def test_the_user_agent_is_sent_and_is_our_own(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(OSM)

        _source(service).fetch(AREA, tmp_path)

    assert service.received[0].headers["user-agent"] == DEFAULT_USER_AGENT


@pytest.mark.parametrize(
    "reply",
    [
        Reply(b"too busy", status=429, content_type="text/plain"),
        Reply(b"gateway timeout", status=504, content_type="text/plain"),
        Reply.fixture("overpass_runtime_error.osm", content_type="application/osm3s+xml"),
        Reply(b"not xml at all", content_type="text/plain"),
    ],
)
def test_a_failing_service_names_overpass_and_stores_nothing(tmp_path: Path, reply: Reply) -> None:
    with fake_service() as service:
        service.answer(reply)

        with pytest.raises(ExternalServiceError) as raised:
            _source(service).fetch(AREA, tmp_path)

    assert raised.value.service == "overpass"
    assert "overpass" in str(raised.value)
    assert list(tmp_path.iterdir()) == []


def test_a_failed_download_is_retried_by_the_next_fetch(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply(b"busy", status=429, content_type="text/plain"), OSM)
        source = _source(service)

        with pytest.raises(ExternalServiceError):
            source.fetch(AREA, tmp_path)
        snapshot = source.fetch(AREA, tmp_path)

    assert snapshot.path.exists()


def test_a_service_slower_than_the_timeout_names_overpass(tmp_path: Path) -> None:
    with fake_service() as service:
        service.answer(Reply(OSM.body, delay_s=1.5))
        source = OverpassOsmSource(base_url=service.url, limits=OsmLimits(), client_timeout_s=0.3)

        with pytest.raises(ExternalServiceError) as raised:
            source.fetch(AREA, tmp_path)

    assert raised.value.service == "overpass"


def test_the_overpass_timeout_of_the_limits_bounds_the_client_wait_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("resto.adapters.osm.overpass._CLIENT_MARGIN_S", 0.2)
    with fake_service() as service:
        service.answer(Reply(OSM.body, delay_s=2.0))
        source = OverpassOsmSource(base_url=service.url, limits=OsmLimits(overpass_timeout_s=1))

        with pytest.raises(ExternalServiceError) as raised:
            source.fetch(AREA, tmp_path)

    assert raised.value.service == "overpass"
