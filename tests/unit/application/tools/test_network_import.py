"""Area-of-interest import tools (E6.1/04; ADR-0033, ADR-0045): a fake `OsmSource` serving a small
committed `.osm`, real `netconvert` (SUMO 1.27.1), no network and no LLM."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import sumolib.net

from resto.adapters.osm.overpass import OverpassOsmSource
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.typemaps import typemap_dir
from resto.application.ports.osm import ExternalServiceError, OsmLimits
from resto.application.tools.network_import import (
    ImportRun,
    fetch_osm,
    join_junctions,
    keep_largest_component,
    keep_vclass,
    list_import_profiles,
    netconvert,
    remove_isolated,
)
from resto.domain.value_objects.artifact_ref import ArtifactRef
from tests.unit.adapters.osm._server import FakeService, Reply, fake_service
from tests.unit.application.tools._osm_doubles import (
    DISTRICT,
    DISTRICT_OSM,
    FakeGeocoder,
    FakeOsmSource,
)

RING = [list(point) for point in DISTRICT.ring]


def run_in(
    tmp_path: Path,
    osm: Any = None,
    geocoder: FakeGeocoder | None = None,
    limits: OsmLimits | None = None,
) -> ImportRun:
    return ImportRun(
        runner=SubprocessNetconvertRunner(),
        osm=osm or FakeOsmSource(),
        geocoder=geocoder or FakeGeocoder(),
        out_dir=tmp_path,
        typemap_dir=typemap_dir(),
        limits=limits or OsmLimits(),
    )


def edges_of(result: Mapping[str, Any]) -> set[str]:
    net = sumolib.net.readNet(result["net_artifact"]["path"])
    return {edge.getID() for edge in net.getEdges()}


def imported(run: ImportRun, profile: str = "roads") -> tuple[Mapping[str, Any], str]:
    fetched = fetch_osm(run, polygon=RING)
    snapshot = fetched["osm_snapshot"]["content_hash"]
    return netconvert(run, osm_snapshot=snapshot, profile=profile), snapshot


def test_the_profiles_are_listed_with_their_description() -> None:
    listing = list_import_profiles(run_in(Path(".")))

    names = [p["name"] for p in listing["profiles"]]
    assert names == ["roads", "rail", "bicycle", "pedestrian"]
    assert all(p["description"] for p in listing["profiles"])
    assert "passenger" in listing["vclasses"]


def test_fetch_osm_returns_the_snapshot_and_the_source_for_the_recipe(tmp_path: Path) -> None:
    osm = FakeOsmSource()

    result = fetch_osm(run_in(tmp_path, osm), polygon=RING)

    assert result["source"]["kind"] == "polygon"
    assert result["osm_snapshot"]["kind"] == "osm"
    assert Path(result["osm_snapshot"]["path"]).read_bytes() == DISTRICT_OSM.read_bytes()
    assert osm.downloads == 1


def test_the_imported_network_is_cut_to_the_polygon_and_loads_in_sumo(tmp_path: Path) -> None:
    result, _ = imported(run_in(tmp_path))

    edges = edges_of(result)
    assert {"100#0", "101#0", "-101#0"} <= edges
    assert not any(e.lstrip("-").startswith("104") for e in edges), "the far road was not cut"
    assert not any(e.lstrip("-").startswith("103") for e in edges), "the island was not dropped"


def test_the_options_hold_the_cut_with_longitude_first_and_absolute_typemaps(
    tmp_path: Path,
) -> None:
    result, _ = imported(run_in(tmp_path))

    options = result["netconvert_options"]
    boundary = options[options.index("--keep-edges.in-geo-boundary") + 1]
    assert boundary.split()[0] == "2.15,41.39"
    typemaps = options[options.index("--type-files") + 1].split(",")
    assert typemaps == [str(typemap_dir() / "osmNetconvert.typ.xml")]
    assert all(Path(t).is_absolute() for t in typemaps)


def test_a_second_request_for_the_same_area_does_not_download_again(tmp_path: Path) -> None:
    osm = FakeOsmSource()
    run = run_in(tmp_path, osm)

    first = fetch_osm(run, polygon=RING)
    again = fetch_osm(run, polygon=RING)

    assert osm.downloads == 1
    assert again["osm_snapshot"] == first["osm_snapshot"]


def test_with_the_real_overpass_adapter_a_second_request_makes_no_second_http_call(
    tmp_path: Path,
) -> None:
    with fake_service() as service:
        service.answer(Reply(DISTRICT_OSM.read_bytes(), content_type="application/osm3s+xml"))
        run = run_in(tmp_path, OverpassOsmSource(base_url=service.url))

        fetch_osm(run, polygon=RING)
        fetch_osm(run, polygon=RING)

        assert _requests(service) == 1


def _requests(service: FakeService) -> int:
    return len(service.received)


def test_the_recipe_of_an_imported_network_replays_to_the_same_content_hash(
    tmp_path: Path,
) -> None:
    run = run_in(tmp_path)
    fetched = fetch_osm(run, polygon=RING)
    snapshot = ArtifactRef(
        path=Path(fetched["osm_snapshot"]["path"]),
        content_hash=fetched["osm_snapshot"]["content_hash"],
        kind="osm",
    )
    built = netconvert(run, osm_snapshot=snapshot.content_hash, profile="roads")
    cleaned = remove_isolated(run, osm_snapshot=snapshot.content_hash)

    for result in (built, cleaned):
        replayed = SubprocessNetconvertRunner().build(
            snapshot, None, result["netconvert_options"], tmp_path / "replay" / "x"
        )
        assert replayed.content_hash == result["net_artifact"]["content_hash"]


@pytest.mark.parametrize("profile", ["roads", "rail", "bicycle", "pedestrian"])
def test_every_profile_builds_a_network(profile: str, tmp_path: Path) -> None:
    result, _ = imported(run_in(tmp_path), profile)

    assert edges_of(result)


def test_the_cleanup_tools_add_their_options_to_the_recipe(tmp_path: Path) -> None:
    run = run_in(tmp_path)
    _, snapshot = imported(run)

    largest = keep_largest_component(run, osm_snapshot=snapshot)
    isolated = remove_isolated(run, osm_snapshot=snapshot)
    joined = join_junctions(run, osm_snapshot=snapshot)
    passenger = keep_vclass(run, osm_snapshot=snapshot, vclass="passenger")

    assert "--keep-edges.components" in largest["netconvert_options"]
    assert "--remove-edges.isolated" in isolated["netconvert_options"]
    assert "--junctions.join" in joined["netconvert_options"]
    assert passenger["netconvert_options"][-2:] == ["--keep-edges.by-vclass", "passenger"]
    for result in (largest, isolated, joined, passenger):
        assert edges_of(result)


def test_cleanups_accumulate_and_a_repeat_changes_nothing(tmp_path: Path) -> None:
    run = run_in(tmp_path)
    _, snapshot = imported(run)

    once = remove_isolated(run, osm_snapshot=snapshot)
    twice = remove_isolated(run, osm_snapshot=snapshot)
    both = join_junctions(run, osm_snapshot=snapshot)

    assert twice["netconvert_options"] == once["netconvert_options"]
    assert {"--remove-edges.isolated", "--junctions.join"} <= set(both["netconvert_options"])


def test_a_new_netconvert_starts_the_cleanups_again(tmp_path: Path) -> None:
    run = run_in(tmp_path)
    result, snapshot = imported(run)
    remove_isolated(run, osm_snapshot=snapshot)

    again = netconvert(run, osm_snapshot=snapshot, profile="roads")

    assert again["netconvert_options"] == result["netconvert_options"]


def test_netconvert_on_a_snapshot_that_was_not_fetched_says_so(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fetch_osm"):
        netconvert(run_in(tmp_path), osm_snapshot="deadbeef", profile="roads")


def test_an_unknown_profile_names_the_choices(tmp_path: Path) -> None:
    run = run_in(tmp_path)
    fetched = fetch_osm(run, polygon=RING)

    with pytest.raises(ValueError, match="roads"):
        netconvert(run, osm_snapshot=fetched["osm_snapshot"]["content_hash"], profile="space")


def test_a_network_with_more_edges_than_the_limit_needs_the_user(tmp_path: Path) -> None:
    run = run_in(tmp_path, limits=OsmLimits(max_edges=2))
    fetched = fetch_osm(run, polygon=RING)

    result = netconvert(run, osm_snapshot=fetched["osm_snapshot"]["content_hash"])

    needs = result["needs_user"]
    assert needs["reason"]["kind"] == "area_too_large"
    assert needs["reason"]["limit_edges"] == 2 and needs["reason"]["edges"] > 2
    assert any("Split the area" in r for r in needs["recommendations"])
    assert "net_artifact" not in result


def test_a_cleanup_that_rebuilds_a_network_over_the_limit_needs_the_user(tmp_path: Path) -> None:
    run = run_in(tmp_path)
    _, snapshot = imported(run)
    strict = replace(run, limits=OsmLimits(max_edges=2))

    result = remove_isolated(strict, osm_snapshot=snapshot)

    assert result["needs_user"]["reason"]["kind"] == "area_too_large"
    assert "net_artifact" not in result


def test_an_area_above_the_limit_needs_the_user_and_nothing_is_downloaded(
    tmp_path: Path,
) -> None:
    osm = FakeOsmSource()
    barcelona = [41.32, 2.05, 41.47, 2.23]  # about 250 km2

    result = fetch_osm(run_in(tmp_path, osm), bbox=barcelona)

    needs = result["needs_user"]
    assert needs["reason"]["kind"] == "area_too_large"
    assert needs["reason"]["limit_km2"] == 10.0
    assert needs["reason"]["area_km2"] > 10.0
    assert any("smaller area" in r for r in needs["recommendations"])
    assert osm.calls == []


def test_a_place_that_is_not_a_boundary_needs_the_user_with_the_geocoders_reason(
    tmp_path: Path,
) -> None:
    osm = FakeOsmSource()
    geocoder = FakeGeocoder(rejection="the best match is a node, not a boundary relation")

    result = fetch_osm(run_in(tmp_path, osm, geocoder), place_name="Eixample")

    needs = result["needs_user"]
    assert needs["reason"] == {"place": "Eixample", "kind": "place_not_boundary"}
    assert any("polygon" in r for r in needs["recommendations"])
    assert "not a boundary relation" in needs["message"]
    assert osm.calls == []


def test_a_place_name_is_resolved_once_and_the_recipe_gets_the_polygon(tmp_path: Path) -> None:
    geocoder = FakeGeocoder()

    result = fetch_osm(run_in(tmp_path, geocoder=geocoder), place_name="Sant Antoni")

    assert geocoder.queries == ["Sant Antoni"]
    assert result["source"]["kind"] == "polygon"
    assert result["source"]["osm_id"] == 7


def test_a_geocoder_failure_is_an_error_by_name_not_a_need_for_the_user(
    tmp_path: Path,
) -> None:
    run = run_in(tmp_path, geocoder=FakeGeocoder(down=True))

    with pytest.raises(ExternalServiceError, match="nominatim"):
        fetch_osm(run, place_name="Sant Antoni")


@pytest.mark.parametrize(
    "requirement", ["bus stops", "tram lines", "public transport", "paradas de bus"]
)
def test_a_public_transport_requirement_is_unsupported_and_nothing_is_downloaded(
    requirement: str, tmp_path: Path
) -> None:
    osm = FakeOsmSource()

    result = fetch_osm(run_in(tmp_path, osm), polygon=RING, requirements=[requirement])

    reason = result["needs_user"]["reason"]
    assert reason == {"requirement": requirement, "kind": "unsupported_requirement"}
    assert osm.calls == []


def test_a_supported_requirement_does_not_stop_the_import(tmp_path: Path) -> None:
    result = fetch_osm(run_in(tmp_path), polygon=RING, requirements=["with bicycle lanes"])

    assert "needs_user" not in result


def test_exactly_one_way_to_name_the_area(tmp_path: Path) -> None:
    run = run_in(tmp_path)

    with pytest.raises(ValueError, match="exactly one"):
        fetch_osm(run)
    with pytest.raises(ValueError, match="exactly one"):
        fetch_osm(run, polygon=RING, bbox=[41.39, 2.15, 41.398, 2.16])


def test_a_bbox_is_the_south_west_north_east_of_the_source(tmp_path: Path) -> None:
    result = fetch_osm(run_in(tmp_path), bbox=[41.390, 2.150, 41.398, 2.160])

    assert result["source"] == {
        "south": 41.39,
        "west": 2.15,
        "north": 41.398,
        "east": 2.16,
        "kind": "bbox",
    }
