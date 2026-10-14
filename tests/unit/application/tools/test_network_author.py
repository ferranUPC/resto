"""Generated-network tools of the Network Author (E6.1/02; ADR-0033, ADR-0045): typed parameters
with SUMO's defaults, range checks before SUMO runs, and a real `netgenerate` behind them."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from resto.adapters.sumo.netconvert import SubprocessNetconvertRunner
from resto.application.tools.network_author import (
    AuthorRun,
    build_network_author_tools,
    generate_grid,
    generate_random,
    generate_spider,
)


class RefusingRunner:
    """A runner that fails the test if SUMO would have been asked to build anything."""

    def generate(self, source: object, out_dir: Path) -> object:
        raise AssertionError(f"SUMO must not run for {source!r}")


def run_in(tmp_path: Path) -> AuthorRun:
    return AuthorRun(runner=SubprocessNetconvertRunner(), out_dir=tmp_path)


def test_generate_grid_builds_a_network_and_reports_the_source_it_used(tmp_path: Path) -> None:
    result = generate_grid(run_in(tmp_path), x_number=3, y_number=2)

    assert result["source"] == {
        "kind": "grid",
        "x_number": 3,
        "y_number": 2,
        "x_length": 100.0,
        "y_length": 100.0,
    }
    assert Path(result["net_artifact"]["path"]).name == "network.net.xml"
    assert result["net_artifact"]["content_hash"]


def test_the_same_request_gives_the_same_artifact(tmp_path: Path) -> None:
    first = generate_random(run_in(tmp_path), seed=5, iterations=15)
    again = generate_random(run_in(tmp_path), seed=5, iterations=15)

    assert first == again
    assert first["source"]["seed"] == 5


def test_two_different_requests_do_not_overwrite_each_other(tmp_path: Path) -> None:
    small = generate_grid(run_in(tmp_path), x_number=2, y_number=2)
    bigger = generate_grid(run_in(tmp_path), x_number=3, y_number=3)

    assert small["net_artifact"]["path"] != bigger["net_artifact"]["path"]
    assert small["net_artifact"]["content_hash"] != bigger["net_artifact"]["content_hash"]


def test_generate_spider_builds_a_network(tmp_path: Path) -> None:
    result = generate_spider(run_in(tmp_path), arm_number=4, circle_number=2, omit_center=True)

    assert result["source"]["omit_center"] is True
    assert result["net_artifact"]["content_hash"]


@pytest.mark.parametrize(
    ("call", "parameter"),
    [
        (lambda run: generate_grid(run, x_number=1), "x_number"),
        (lambda run: generate_grid(run, y_length=-5.0), "y_length"),
        (lambda run: generate_spider(run, arm_number=2), "arm_number"),
        (lambda run: generate_spider(run, space_radius=0.0), "space_radius"),
        (lambda run: generate_random(run, seed=-1), "seed"),
        (lambda run: generate_random(run, seed=1, min_distance=300.0), "max_distance"),
    ],
)
def test_a_parameter_out_of_range_is_rejected_before_sumo_runs_and_named(
    call: Callable[[AuthorRun], Mapping[str, Any]], parameter: str, tmp_path: Path
) -> None:
    run = AuthorRun(runner=RefusingRunner(), out_dir=tmp_path)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=parameter):
        call(run)


def test_the_tools_offer_typed_parameters_with_sumos_defaults_and_no_free_options(
    tmp_path: Path,
) -> None:
    tools = {t.name: t for t in build_network_author_tools(run_in(tmp_path))}

    assert set(tools) == {"generate_grid", "generate_spider", "generate_random"}
    grid = tools["generate_grid"].input_schema["properties"]
    assert set(grid) == {"x_number", "y_number", "x_length", "y_length"}
    assert "SUMO: 5" in grid["x_number"]["description"]
    assert tools["generate_random"].input_schema["required"] == ["seed"]


def test_a_bound_tool_builds_the_network(tmp_path: Path) -> None:
    tools = {t.name: t for t in build_network_author_tools(run_in(tmp_path))}

    result = tools["generate_grid"].fn(x_number=2, y_number=2)

    assert result["net_artifact"]["content_hash"]
