from pathlib import Path

import pytest

from resto.domain.entities.network import Network
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.sanity_report import SanityReport


def test_network_accepts_valid_net_xml_path() -> None:
    network = Network(
        network_id="net-1",
        net_xml_path=Path("dev-net.net.xml"),
        source=NetworkSource(kind="file", value="dev-net.osm"),
        content_hash="abc123",
        sanity_report=SanityReport(
            largest_scc_ratio=0.98, zero_length_edges=0, all_reachable_from_fringe=True
        ),
    )
    assert network.sanity_report is not None
    assert network.sanity_report.passes


def test_network_rejects_non_xml_path() -> None:
    with pytest.raises(ValueError):
        Network(
            network_id="net-1",
            net_xml_path=Path("dev-net.txt"),
            source=NetworkSource(kind="file", value="dev-net.osm"),
            content_hash="abc123",
        )


def test_sanity_report_fails_below_scc_threshold() -> None:
    report = SanityReport(
        largest_scc_ratio=0.90, zero_length_edges=0, all_reachable_from_fringe=True
    )
    assert not report.passes
