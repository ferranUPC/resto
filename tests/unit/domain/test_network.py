import pytest

from resto.domain.entities.network import Network
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import (
    BBox,
    GridNetwork,
    PlaceName,
    Polygon,
    RandomNetwork,
    SpiderNetwork,
)
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.domain._fixtures import artifact, file_recipe, good_sanity, square_ring


def test_network_id_is_the_content_hash_of_the_net_xml() -> None:
    net = Network(
        network_id="abc123",
        net_xml=artifact("dev-net.net.xml", "abc123", "net"),
        recipe=file_recipe(),
        sanity_report=good_sanity(),
    )
    assert net.content_hash == "abc123"
    assert net.sanity_report.passes()


def test_network_rejects_mismatched_id() -> None:
    with pytest.raises(ValueError):
        Network(
            network_id="other",
            net_xml=artifact("dev-net.net.xml", "abc123", "net"),
            recipe=file_recipe(),
            sanity_report=good_sanity(),
        )


def test_network_rejects_non_net_xml_path() -> None:
    with pytest.raises(ValueError):
        Network(
            network_id="abc123",
            net_xml=artifact("dev-net.txt", "abc123", "net"),
            recipe=file_recipe(),
            sanity_report=good_sanity(),
        )


def test_derived_network_must_match_recipe_base() -> None:
    recipe = NetworkRecipe(
        base_network_id="base1", plain_edits=(AddEdge("J7", "J9", lanes=2, speed=13.9),)
    )
    with pytest.raises(ValueError):
        Network(
            network_id="d1",
            net_xml=artifact("n.net.xml", "d1"),
            recipe=recipe,
            sanity_report=good_sanity(),
        )
    derived = Network(
        network_id="d1",
        net_xml=artifact("n.net.xml", "d1"),
        recipe=recipe,
        sanity_report=good_sanity(),
        derived_from="base1",
    )
    assert derived.recipe.is_derivation


@pytest.mark.parametrize("source", [BBox(41.38, 2.15, 41.40, 2.18), Polygon(ring=square_ring())])
def test_area_of_interest_requires_osm_snapshot(source: BBox | Polygon) -> None:
    with pytest.raises(ValueError, match="osm_snapshot"):
        NetworkRecipe(source=source)
    NetworkRecipe(source=source, osm_snapshot=artifact("area.osm", "s1", "osm"))


@pytest.mark.parametrize(
    "source", [GridNetwork(), SpiderNetwork(), RandomNetwork(seed=3)], ids=lambda s: s.kind
)
def test_generated_network_forbids_osm_snapshot(
    source: GridNetwork | SpiderNetwork | RandomNetwork,
) -> None:
    with pytest.raises(ValueError, match="osm_snapshot"):
        NetworkRecipe(source=source, osm_snapshot=artifact("area.osm", "s1", "osm"))
    assert NetworkRecipe(source=source).source == source


def test_recipe_stores_the_resolved_polygon_never_the_place_name() -> None:
    with pytest.raises(ValueError, match="PlaceName"):
        NetworkRecipe(
            source=PlaceName(query="Eixample"), osm_snapshot=artifact("a.osm", "s1", "osm")
        )


def test_derivation_forbids_osm_snapshot() -> None:
    with pytest.raises(ValueError, match="osm_snapshot"):
        NetworkRecipe(base_network_id="base1", osm_snapshot=artifact("a.osm", "s1", "osm"))


def test_sanity_report_fails_below_scc_threshold() -> None:
    report = SanityReport(
        largest_scc_ratio=0.90, zero_length_edges=0, all_reachable_from_fringe=True
    )
    assert not report.passes()
    assert report.passes(min_scc_ratio=0.85)
