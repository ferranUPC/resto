"""Area-of-interest import tools (E6.1/04, E6.1/09, E6.1/10; ADR-0033, ADR-0045, ADR-0046): a fake
`OsmSource` serving a small committed `.osm`, a fake geocoder, real `netconvert` (SUMO 1.27.1), no
network and no LLM."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import sumolib.net

from resto.adapters.osm.overpass import OverpassOsmSource
from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.typemaps import typemap_dir
from resto.application.network_analysis import sanity_report
from resto.application.osm_import import OWN_TYPEMAPS
from resto.application.osm_map import Connectors, NetEdge, OsmMap
from resto.application.ports.osm import ExternalServiceError, OsmLimits
from resto.application.tools.network_import import (
    ImportRun,
    fetch_osm,
    join_junctions,
    keep_largest_component,
    keep_vclass,
    list_import_profiles,
    list_streets,
    locate_place,
    netconvert,
    remove_isolated,
    select_streets,
    trace_corridor,
    verify_coverage,
)
from resto.domain.services.geo import distance_m
from resto.domain.value_objects.artifact_ref import ArtifactRef
from tests.unit.adapters.osm._server import FakeService, Reply, fake_service
from tests.unit.application.tools._osm_doubles import (
    CAMPUS_OSM,
    CORRIDOR,
    CORRIDOR_OSM,
    DIAGONAL_AREA,
    DIAGONAL_B23_OSM,
    DISTRICT,
    DISTRICT_OSM,
    EAST_END,
    HOSPITAL,
    MACIA,
    WEST_END,
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
    assert typemaps == [
        str(typemap_dir() / "osmNetconvert.typ.xml"),
        str(OWN_TYPEMAPS / "restoServiceRoads.typ.xml"),
    ]
    assert all(Path(t).is_absolute() and Path(t).is_file() for t in typemaps)


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
    assert needs["reason"]["limit_km2"] == 25.0
    assert needs["reason"]["area_km2"] > 25.0
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


def test_a_service_street_stays_for_cars_but_a_driveway_and_a_parking_aisle_do_not(
    tmp_path: Path,
) -> None:
    run = run_in(tmp_path, FakeOsmSource(CAMPUS_OSM))
    fetched = fetch_osm(run, polygon=RING)
    snapshot = fetched["osm_snapshot"]["content_hash"]

    result = keep_vclass(run, osm_snapshot=snapshot, vclass="passenger")

    ways = {edge.lstrip("-").split("#")[0] for edge in edges_of(result)}
    assert {"200", "201"} <= ways, "the residential road and the named service street stay"
    assert not ways & {"202", "203"}, "the driveway and the parking aisle are dropped"


# -- locate, select, verify (E6.1/09, ADR-0046) ---------------------------------------------------

DIAGONAL = {300, 303, 305}
"""The roads called "Avinguda Diagonal", the lateral lane included; 301 is the same road as
"Carretera Reial", and the footway 306 is no road."""
CORRIDOR_WAYS = {300, 301, 302, 303, 304, 305}
"""The road with every name, its lateral lane, the link and the square between its stretches."""


def corridor_run(tmp_path: Path, osm: FakeOsmSource | None = None) -> tuple[ImportRun, str]:
    run = run_in(
        tmp_path, osm or FakeOsmSource(CORRIDOR_OSM), FakeGeocoder(places=(WEST_END, EAST_END))
    )
    fetched = fetch_osm(run, bbox=[CORRIDOR.south, CORRIDOR.west, CORRIDOR.north, CORRIDOR.east])
    return run, fetched["osm_snapshot"]["content_hash"]


def osm_ways_of(result: Mapping[str, Any]) -> set[int]:
    """The OSM ways a built network was made of, as `--output.original-names` records them."""
    return {
        w for edge in NetEdge.read_all(Path(result["net_artifact"]["path"])) for w in edge.osm_ways
    }


def built_from(run: ImportRun, selected: Mapping[str, Any]) -> Mapping[str, Any]:
    return netconvert(run, osm_snapshot=selected["osm_snapshot"]["content_hash"])


def test_a_located_place_gives_its_point_and_what_it_is(tmp_path: Path) -> None:
    run = run_in(tmp_path, geocoder=FakeGeocoder(places=(WEST_END,)))

    result = locate_place(run, query=" Hospital Broggi ")

    assert (result["lat"], result["lon"]) == (WEST_END.lat, WEST_END.lon)
    assert (result["category"], result["type"]) == ("amenity", "hospital")


def test_a_place_the_geocoder_does_not_know_is_an_answer_not_a_failure(tmp_path: Path) -> None:
    result = locate_place(run_in(tmp_path), query="Hospital Imaginari")

    assert "Hospital Imaginari" in result["not_found"]


def test_locating_with_the_geocoder_down_fails_by_its_name(tmp_path: Path) -> None:
    with pytest.raises(ExternalServiceError, match="nominatim"):
        locate_place(run_in(tmp_path, geocoder=FakeGeocoder(down=True)), query="Hospital Broggi")


def test_the_streets_of_a_snapshot_show_a_road_that_changes_name_and_keeps_its_ref(
    tmp_path: Path,
) -> None:
    run, snapshot = corridor_run(tmp_path)

    listing = list_streets(run, osm_snapshot=snapshot)

    rows = {(r["name"], r["ref"]): r for r in listing["streets"]}
    # 0.028 degrees of longitude at lat 41.39
    assert rows["Avinguda Diagonal", "N-340"]["length_m"] == pytest.approx(2336, abs=5)
    assert rows["Carretera Reial", "N-340"]["extent"]["west"] == 2.1
    assert rows["", ""]["classes"] == ["primary_link"]
    assert listing["total"] == len(listing["streets"]) == 9


def test_near_a_point_only_the_streets_that_pass_close_to_it_are_listed(tmp_path: Path) -> None:
    run, snapshot = corridor_run(tmp_path)

    listing = list_streets(run, osm_snapshot=snapshot, near=[41.3950, 2.1200], radius_m=100)

    assert {r["name"] for r in listing["streets"]} == {"Carrer de Dalt", "Passeig de la Diagonal"}


@pytest.mark.parametrize(
    ("names", "refs", "kept"),
    [
        pytest.param(["diagonal"], [], DIAGONAL, id="by-name"),
        pytest.param([], ["n-340"], {300, 301, 303}, id="by-ref-across-the-new-name"),
    ],
)
def test_a_selection_keeps_the_matching_streets_and_nothing_else(
    tmp_path: Path, names: list[str], refs: list[str], kept: set[int]
) -> None:
    run, snapshot = corridor_run(tmp_path)

    selected = select_streets(run, osm_snapshot=snapshot, names=names, refs=refs, connectors="none")

    assert osm_ways_of(built_from(run, selected)) <= kept
    assert selected["pieces"] == len(kept)  # nothing joins them without connectors
    assert selected["connectors"] == []


@pytest.mark.parametrize(
    ("connectors", "pieces", "built"),
    [
        pytest.param("links", 3, {300, 301, 304}, id="links-only-the-ramp"),
        pytest.param("all", 1, CORRIDOR_WAYS | {311}, id="all-the-square-and-a-crossing-too"),
    ],
)
def test_connectors_join_the_pieces_and_the_network_keeps_the_largest(
    tmp_path: Path, connectors: Connectors, pieces: int, built: set[int]
) -> None:
    run, snapshot = corridor_run(tmp_path)

    selected = select_streets(
        run, osm_snapshot=snapshot, names=["Diagonal"], refs=["N-340"], connectors=connectors
    )
    result = built_from(run, selected)

    assert selected["pieces"] == pieces
    assert osm_ways_of(result) == built
    report = sanity_report(SumolibNetworkQuery(Path(result["net_artifact"]["path"])))
    assert report.largest_scc_ratio == 1.0


def test_the_whole_area_keeps_the_cross_streets_a_selection_drops(tmp_path: Path) -> None:
    run, snapshot = corridor_run(tmp_path)

    everything = netconvert(run, osm_snapshot=snapshot)
    selected = select_streets(run, osm_snapshot=snapshot, names=["Diagonal"], refs=["N-340"])

    assert osm_ways_of(everything) >= {310, 311, 320}
    assert not {306, 310, 320} & osm_ways_of(built_from(run, selected))


def test_a_connector_keeps_only_the_stretch_that_joins_the_pieces(tmp_path: Path) -> None:
    run, snapshot = corridor_run(tmp_path)

    selected = select_streets(run, osm_snapshot=snapshot, names=["Diagonal"], refs=["N-340"])

    balmes = OsmMap.read(Path(selected["osm_snapshot"]["path"])).ways[311]
    assert balmes.nodes == (7, 16), "the 33 m between the road and its lateral lane, not the street"
    junctions = {
        j
        for e in NetEdge.read_all(Path(built_from(run, selected)["net_artifact"]["path"]))
        for j in (e.from_junction, e.to_junction)
    }
    assert not junctions & {"13", "14"}


def test_a_selection_that_matches_nothing_says_so_and_points_to_the_listing(
    tmp_path: Path,
) -> None:
    run, snapshot = corridor_run(tmp_path)

    with pytest.raises(ValueError, match="list_streets"):
        select_streets(run, osm_snapshot=snapshot, names=["Diagnal"])
    with pytest.raises(ValueError, match="at least one"):
        select_streets(run, osm_snapshot=snapshot, names=["  "])


def test_a_selection_replays_to_the_same_hash_and_trying_it_again_downloads_nothing(
    tmp_path: Path,
) -> None:
    osm = FakeOsmSource(CORRIDOR_OSM)
    run, snapshot = corridor_run(tmp_path, osm)

    selected = select_streets(run, osm_snapshot=snapshot, names=["Diagonal"], refs=["N-340"])
    again = select_streets(run, osm_snapshot=snapshot, names=["Diagonal"], refs=["N-340"])
    built = built_from(run, selected)

    assert again["osm_snapshot"] == selected["osm_snapshot"]
    assert osm.downloads == 1
    derived = ArtifactRef(
        Path(selected["osm_snapshot"]["path"]), selected["osm_snapshot"]["content_hash"], "osm"
    )
    replayed = SubprocessNetconvertRunner().build(
        derived, None, built["netconvert_options"], tmp_path / "replay" / "x"
    )
    assert replayed.content_hash == built["net_artifact"]["content_hash"]
    assert built["source"] == selected["source"]


def test_coverage_shows_the_missing_stretch_and_the_place_the_network_does_not_reach(
    tmp_path: Path,
) -> None:
    run, snapshot = corridor_run(tmp_path)
    locate_place(run, query=WEST_END.query)
    locate_place(run, query=EAST_END.query)
    selected = select_streets(
        run, osm_snapshot=snapshot, names=["Diagonal"], refs=["N-340"], connectors="links"
    )
    built_from(run, selected)

    report = verify_coverage(run, osm_snapshot=selected["osm_snapshot"]["content_hash"])

    assert report["components"] == 1
    assert report["extent"]["west"] == 2.1 and report["extent"]["east"] == 2.13
    (diagonal,) = [
        s
        for s in report["streets_with_missing_stretches"]
        if s["ref"] == "N-340" and s["name"] == "Avinguda Diagonal"
    ]
    (gap,) = diagonal["missing"]
    assert sorted(gap["ends"]) == [[41.39, 2.1315], [41.39, 2.15]]
    places = {p["query"]: p for p in report["places"]}
    assert places[WEST_END.query]["to_network_m"] < 50
    assert places[EAST_END.query]["to_network_m"] > 1500


def test_coverage_of_the_whole_corridor_reaches_both_places_and_misses_nothing(
    tmp_path: Path,
) -> None:
    run, snapshot = corridor_run(tmp_path)
    locate_place(run, query=WEST_END.query)
    locate_place(run, query=EAST_END.query)
    selected = select_streets(run, osm_snapshot=snapshot, names=["Diagonal"], refs=["N-340"])
    built_from(run, selected)

    report = verify_coverage(run, osm_snapshot=selected["osm_snapshot"]["content_hash"])

    assert report["streets_with_missing_stretches"] == []
    assert all(p["to_nearest_end_m"] < 50 for p in report["places"])


def test_coverage_before_anything_was_built_says_what_to_call(tmp_path: Path) -> None:
    run, snapshot = corridor_run(tmp_path)

    with pytest.raises(ValueError, match="netconvert"):
        verify_coverage(run, osm_snapshot=snapshot)


def b23_run(tmp_path: Path) -> tuple[ImportRun, str]:
    run = run_in(tmp_path, FakeOsmSource(DIAGONAL_B23_OSM), FakeGeocoder(places=(HOSPITAL, MACIA)))
    area = DIAGONAL_AREA
    fetched = fetch_osm(run, bbox=[area.south, area.west, area.north, area.east])
    return run, fetched["osm_snapshot"]["content_hash"]


def hospital_to_macia(run: ImportRun, snapshot: str) -> Mapping[str, Any]:
    return trace_corridor(
        run,
        osm_snapshot=snapshot,
        from_point=[HOSPITAL.lat, HOSPITAL.lon],
        to_point=[MACIA.lat, MACIA.lon],
    )


def test_the_corridor_follows_the_road_where_it_changes_name_and_suggests_both(
    tmp_path: Path,
) -> None:
    run, snapshot = b23_run(tmp_path)

    traced = hospital_to_macia(run, snapshot)

    assert traced["suggested_selection"] == {
        "names": ["Avinguda Diagonal"],
        "refs": ["B-23"],
        "connectors": "links",
    }
    assert traced["joins_at"] == [41.3763, 2.073], "where the ramp enters the B-23 (node E)"
    assert traced["leaves_at"] == [MACIA.lat, MACIA.lon]
    assert [s["class"] for s in traced["route"]] == [
        "tertiary",
        "motorway_link",
        "motorway",
        "primary",
        "primary",
    ]
    assert traced["total_m"] == pytest.approx(6600, abs=50)
    start, end = traced["snapped"]
    assert start["node_at"] == [41.3745, 2.072] and start["distance_m"] < 30
    assert end["distance_m"] == 0


def network_to_place_m(result: Mapping[str, Any], place: Any) -> float:
    """How close the OSM ways a built network was made of come to a place, node by node (the
    test environment has no pyproj to read the lanes back into degrees)."""
    osm = OsmMap.read(DIAGONAL_B23_OSM)
    return min(
        distance_m((place.lat, place.lon), osm.nodes[n])
        for way in osm_ways_of(result)
        for n in osm.ways[way].nodes
    )


def test_the_suggested_selection_builds_one_network_that_reaches_the_hospital(
    tmp_path: Path,
) -> None:
    run, snapshot = b23_run(tmp_path)
    traced = hospital_to_macia(run, snapshot)

    selected = select_streets(run, osm_snapshot=snapshot, **traced["suggested_selection"])
    built = built_from(run, selected)

    assert selected["pieces"] == 1
    assert len(NetEdge.components(NetEdge.read_all(Path(built["net_artifact"]["path"])))) == 1
    assert osm_ways_of(built) == {403, 404, 405, 406}
    assert network_to_place_m(built, HOSPITAL) < 300


@pytest.mark.parametrize(
    "outside",
    [
        pytest.param([41.3650, 2.0718], id="south-of-the-area"),
        pytest.param([41.3715, 2.0718], id="within-the-margin-of-its-edge"),
    ],
)
def test_a_point_outside_the_fetched_area_asks_for_a_box_that_holds_it(
    tmp_path: Path, outside: list[float]
) -> None:
    run, snapshot = b23_run(tmp_path)

    traced = trace_corridor(
        run, osm_snapshot=snapshot, from_point=outside, to_point=[MACIA.lat, MACIA.lon]
    )

    missing = traced["not_reached"]
    assert missing["point"] == outside
    assert missing["reason"] == "outside the fetched area"
    box = missing["fetch"]
    assert box["south"] < outside[0] - 0.002, "the point and a margin around it"
    assert (box["west"], box["north"], box["east"]) == (2.06, 41.398, 2.15), "and the area"


def test_a_point_no_road_takes_to_the_other_has_no_drivable_path(tmp_path: Path) -> None:
    run, snapshot = b23_run(tmp_path)
    island = [41.3942, 2.0720]

    traced = trace_corridor(
        run, osm_snapshot=snapshot, from_point=island, to_point=[MACIA.lat, MACIA.lon]
    )

    assert traced["not_reached"]["point"] == island
    assert traced["not_reached"]["reason"] == "no drivable path"
