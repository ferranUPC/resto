import pytest

from resto.domain.entities.network import Network
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.domain._fixtures import artifact, file_recipe, good_sanity


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


def test_place_source_requires_osm_snapshot() -> None:
    with pytest.raises(ValueError):
        NetworkRecipe(source=NetworkSource(kind="place", value="Sant Cugat"))


def test_sanity_report_fails_below_scc_threshold() -> None:
    report = SanityReport(
        largest_scc_ratio=0.90, zero_length_edges=0, all_reachable_from_fringe=True
    )
    assert not report.passes()
    assert report.passes(min_scc_ratio=0.85)
