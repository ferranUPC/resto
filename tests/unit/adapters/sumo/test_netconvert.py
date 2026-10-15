"""`SubprocessNetconvertRunner` with real SUMO 1.27.1 (E6.1/02): a generated network loads and
rebuilds to the same `content_hash` from its recipe, in another directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.sumo import NetBuildError
from resto.domain.value_objects.network_source import (
    GeneratedNetwork,
    GridNetwork,
    RandomNetwork,
    SpiderNetwork,
)

SMALL: dict[str, GeneratedNetwork] = {
    "grid": GridNetwork(x_number=3, y_number=2, x_length=120.0, y_length=80.0),
    "spider": SpiderNetwork(arm_number=4, circle_number=2, space_radius=90.0, omit_center=True),
    "rand": RandomNetwork(seed=7, iterations=15),
}


@pytest.mark.parametrize("kind", SMALL)
def test_a_generated_network_loads_in_sumo_and_replays_to_the_same_hash(
    kind: str, tmp_path: Path
) -> None:
    runner = SubprocessNetconvertRunner()

    first = runner.generate(SMALL[kind], tmp_path / "first")
    again = runner.generate(SMALL[kind], tmp_path / "again")

    assert first.kind == "net"
    assert first.path.name.endswith(".net.xml")
    assert SumolibNetworkQuery(first.path).edges_in_bbox((-1e5, -1e5, 1e5, 1e5))
    assert first.content_hash == again.content_hash


def test_a_grid_follows_the_requested_size(tmp_path: Path) -> None:
    net = SubprocessNetconvertRunner().generate(SMALL["grid"], tmp_path)

    query = SumolibNetworkQuery(net.path)
    # junction ids are letter (x) + number (y); a 3 x 2 grid has B0 and B1 but no C2 or A2
    assert query.has_edge("B0B1") or query.has_edge("B1B0")
    assert not query.has_edge("A2A1") and not query.has_edge("A1A2")


def test_different_random_seeds_give_different_networks(tmp_path: Path) -> None:
    runner = SubprocessNetconvertRunner()

    a = runner.generate(RandomNetwork(seed=1, iterations=15), tmp_path / "a")
    b = runner.generate(RandomNetwork(seed=2, iterations=15), tmp_path / "b")

    assert a.content_hash != b.content_hash


def test_exporting_plain_xml_and_building_it_again_keeps_the_hash(tmp_path: Path) -> None:
    runner = SubprocessNetconvertRunner()
    net = runner.generate(SMALL["grid"], tmp_path / "net")

    plain = runner.export_plain(net, tmp_path / "plain")
    rebuilt = runner.build(None, plain, (), tmp_path / "rebuilt")

    assert rebuilt.content_hash == net.content_hash


def test_a_build_that_netconvert_rejects_names_the_tool(tmp_path: Path) -> None:
    empty = tmp_path / "plain"
    empty.mkdir()

    with pytest.raises(NetBuildError, match="netconvert"):
        SubprocessNetconvertRunner().build(None, empty, (), tmp_path / "out")
