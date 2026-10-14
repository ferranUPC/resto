"""Inspection, sanity and probe tools of the Network Author (E6.1/05; ADR-0033, ADR-0045).

The seam is the bound tool, run against real small networks and the real SUMO. A unit test of the
analysis stands only where `netconvert` cannot build the case: it never writes a zero-length edge.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from resto.adapters.sumo.network_probe import SumoNetworkProber
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.application.network_analysis import sanity_report
from resto.application.ports.network_probe import NetworkProber
from resto.application.tools.network_inspection import (
    MAX_SUSPECTS,
    InspectionRun,
    build_network_inspection_tools,
)
from resto.domain.value_objects.sanity_report import SanityReport
from tests.unit.application.tools._networks import (
    grid_net,
    jammed_net,
    one_way_chain,
    star_net,
    two_loops,
)


def inspection_run(out_dir: Path) -> InspectionRun:
    return InspectionRun(
        open_network=SumolibNetworkQuery,
        prober=SumoNetworkProber(SubprocessSumoRunner()),
        out_dir=out_dir,
    )


def tools_in(out_dir: Path) -> dict[str, Any]:
    bound = build_network_inspection_tools(inspection_run(out_dir))
    return {t.name: t.fn for t in bound}


def test_sanity_check_passes_on_a_healthy_network(tmp_path: Path) -> None:
    net = grid_net(tmp_path)

    report = tools_in(tmp_path)["sanity_check"](net_path=str(net))

    assert report == {
        "largest_scc_ratio": 1.0,
        "zero_length_edges": 0,
        "all_reachable_from_fringe": True,
        "passes": True,
    }


def test_sanity_check_fails_on_a_network_that_cannot_be_driven_around(tmp_path: Path) -> None:
    net = one_way_chain(tmp_path, length=4)

    report = tools_in(tmp_path)["sanity_check"](net_path=str(net))

    assert report["largest_scc_ratio"] == pytest.approx(0.25)
    assert report["passes"] is False


def test_sanity_check_finds_the_part_that_no_vehicle_can_reach(tmp_path: Path) -> None:
    net = two_loops(tmp_path)

    report = tools_in(tmp_path)["sanity_check"](net_path=str(net))

    assert report["largest_scc_ratio"] == pytest.approx(0.6)
    assert report["all_reachable_from_fringe"] is False
    assert report["passes"] is False


class StubNetwork:
    """Three connected edges, one of them with no length: the case `netconvert` will not build."""

    LENGTHS = {"a": 50.0, "b": 0.0, "c": 0.1}
    NEXT = {"a": ["b"], "b": ["c"], "c": ["a"]}

    def edge_ids(self) -> Sequence[str]:
        return list(self.LENGTHS)

    def get_edge(self, edge_id: str) -> Mapping[str, Any]:
        return {"id": edge_id, "length": self.LENGTHS[edge_id]}

    def get_neighbours(self, edge_id: str) -> Sequence[str]:
        return self.NEXT[edge_id]


def test_the_sanity_report_counts_zero_length_edges() -> None:
    report = sanity_report(StubNetwork())  # type: ignore[arg-type]

    assert report == SanityReport(
        largest_scc_ratio=1.0, zero_length_edges=2, all_reachable_from_fringe=True
    )
    assert not report.passes()


def test_inspect_network_summarises_a_grid(tmp_path: Path) -> None:
    net = grid_net(tmp_path)

    summary = tools_in(tmp_path)["inspect_network"](net_path=str(net))

    assert summary["edges"] == 24
    assert summary["junctions"] == 9
    assert summary["traffic_lights"] == 0
    assert summary["total_length_m"] == pytest.approx(2118.4, abs=0.1)
    assert summary["connected_components"] == 1
    assert summary["speeds_mps"]["max"] == pytest.approx(13.89)
    assert summary["suspects"] == []
    assert "passenger" in summary["vehicle_classes"]


def test_inspect_network_counts_the_separate_components(tmp_path: Path) -> None:
    net = two_loops(tmp_path)

    summary = tools_in(tmp_path)["inspect_network"](net_path=str(net))

    assert summary["connected_components"] == 2


def test_inspect_network_stays_bounded_when_many_edges_are_suspect(tmp_path: Path) -> None:
    net = star_net(tmp_path, spokes=MAX_SUSPECTS + 8)

    summary = tools_in(tmp_path)["inspect_network"](net_path=str(net))

    assert summary["edges"] == MAX_SUSPECTS + 8
    assert summary["suspect_count"] == MAX_SUSPECTS + 8
    assert len(summary["suspects"]) == MAX_SUSPECTS
    assert summary["suspect_count"] > MAX_SUSPECTS


def test_inspect_edge_describes_one_edge(tmp_path: Path) -> None:
    net = grid_net(tmp_path)
    tools = tools_in(tmp_path)

    edge = tools["inspect_edge"](net_path=str(net), edge_id="A0A1")

    assert edge["id"] == "A0A1"
    assert edge["length"] == pytest.approx(89.6, abs=0.1)
    assert edge["lane_count"] == 1
    assert len(edge["lanes"]) == 1
    assert edge["successors"]
    assert "shape" not in edge


def test_inspect_edge_names_an_edge_that_does_not_exist(tmp_path: Path) -> None:
    net = grid_net(tmp_path)

    with pytest.raises(KeyError, match="nope"):
        tools_in(tmp_path)["inspect_edge"](net_path=str(net), edge_id="nope")


def test_probe_run_on_a_healthy_network_reports_no_trouble(tmp_path: Path) -> None:
    net = grid_net(tmp_path)

    report = tools_in(tmp_path)["probe_run"](net_path=str(net), vehicles=30)

    assert report["teleports"] == 0
    assert report["collisions"] == 0
    assert report["not_arrived"] == 0
    assert report["hot_edges"] == []
    assert Path(report["evidence"]["path"]).is_file()


def test_probe_run_on_a_jammed_network_reports_the_teleports(tmp_path: Path) -> None:
    net = jammed_net(tmp_path)

    report = tools_in(tmp_path)["probe_run"](net_path=str(net), vehicles=20)

    assert report["teleports"] > 0
    assert report["hot_edges"]


def test_probe_run_with_the_same_seed_gives_the_same_report(tmp_path: Path) -> None:
    net = jammed_net(tmp_path)
    probe = tools_in(tmp_path)["probe_run"]

    first = probe(net_path=str(net), vehicles=20, seed=3)
    again = probe(net_path=str(net), vehicles=20, seed=3)

    assert {k: v for k, v in first.items() if k != "evidence"} == {
        k: v for k, v in again.items() if k != "evidence"
    }


def test_probe_run_writes_only_under_its_own_directory(tmp_path: Path) -> None:
    out_dir = tmp_path / "author"
    out_dir.mkdir()
    net = grid_net(out_dir)
    before = {p for p in tmp_path.rglob("*")}

    tools_in(out_dir)["probe_run"](net_path=str(net), vehicles=10)

    created = {p for p in tmp_path.rglob("*")} - before
    assert created
    assert all(out_dir in p.parents for p in created)


def test_nothing_that_probe_run_uses_can_reach_a_results_store() -> None:
    """A probe is a check on a draft, not a result (ADR-0045 §1): neither the tool's context nor
    the prober is given a repository, so there is nothing for `probe_run` to write a result to."""
    holders = (InspectionRun, SumoNetworkProber)
    for holder in holders:
        params = inspect.signature(holder).parameters.values()
        assert not [p for p in params if "Repository" in str(p.annotation)], holder
    probe_params = inspect.signature(NetworkProber.probe).parameters.values()
    assert not [p for p in probe_params if "Repository" in str(p.annotation)]


def test_probe_run_says_so_when_no_vehicle_can_go_anywhere(tmp_path: Path) -> None:
    net = one_way_chain(tmp_path, length=1)

    with pytest.raises(ValueError, match="no routable"):
        tools_in(tmp_path)["probe_run"](net_path=str(net))


def test_a_network_outside_the_working_directory_is_refused(tmp_path: Path) -> None:
    out_dir = tmp_path / "author"
    out_dir.mkdir()
    elsewhere = grid_net(tmp_path)

    with pytest.raises(ValueError, match="outside"):
        tools_in(out_dir)["sanity_check"](net_path=str(elsewhere))


def test_the_tools_are_declared_once_with_typed_parameters(tmp_path: Path) -> None:
    bound = {t.name: t for t in build_network_inspection_tools(inspection_run(tmp_path))}

    assert set(bound) == {"inspect_network", "inspect_edge", "sanity_check", "probe_run"}
    assert bound["inspect_edge"].input_schema["required"] == ["net_path", "edge_id"]
    probe = bound["probe_run"].input_schema["properties"]
    assert set(probe) == {"net_path", "seed", "vehicles", "duration_s"}
