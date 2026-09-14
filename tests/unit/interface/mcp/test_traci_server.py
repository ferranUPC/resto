"""TraciMCP server (E1.2): registers the 8 primitives only, over a live TraCI session."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
import traci

from resto import traci_api
from resto.interface.mcp.traci_server import build_server

DEV_NET = Path(__file__).resolve().parents[4] / "eval" / "dev-net" / "dev-net.net.xml"
LOW_ROUTES = DEV_NET.parent / "demand" / "low.rou.xml"

SUMO_CMD = [
    "sumo",
    "--net-file",
    str(DEV_NET),
    "--route-files",
    str(LOW_ROUTES),
    "--seed",
    "1",
    "--no-step-log",
    "--time-to-teleport",
    "300",
]


@pytest.fixture
def session() -> Iterator[None]:
    traci_api.start(SUMO_CMD)
    yield
    traci_api.close()


def test_build_server_registers_only_the_eight_primitives(session: None) -> None:
    server = build_server()

    tools = asyncio.run(server.list_tools())

    assert {t.name for t in tools} == {
        "close_lane",
        "open_lane",
        "set_speed",
        "set_tls_program",
        "get_edge_occupancy",
        "get_edge_speed",
        "get_vehicle_count",
        "step",
    }


def test_build_server_does_not_expose_at_time_when_or_run(session: None) -> None:
    server = build_server()

    tools = asyncio.run(server.list_tools())

    assert {"at_time", "when", "run"}.isdisjoint({t.name for t in tools})


def test_build_server_call_tool_executes_the_primitive_against_the_live_session(
    session: None,
) -> None:
    server = build_server()

    asyncio.run(server.call_tool("set_speed", {"edge_id": "A0A1", "speed": 5.0}))

    assert traci.lane.getMaxSpeed("A0A1_0") == pytest.approx(5.0)
