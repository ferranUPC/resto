"""Latency benchmark of every MCP tool against DEV-NET (work-plan E1.6; DoD §4.9 threshold:
single call < 1 s on DEV-NET, < 5 s on REAL-NET).

Times each tool through the real `MCPServer.call_tool` dispatch (the same entry point
`tests/unit/interface/mcp/test_*_server.py` exercises, and what a client's `tools/call` reaches
after transport deserialization) rather than the bare port/repository call underneath, so a
number here includes the tool's own (de)serialization, not just its business logic:

- **NetworkMCP** (E1.1): the 7 read-only queries against `eval/dev-net/dev-net.net.xml`.
- **DatabaseMCP** (E1.3): the 17 required-capability tools against the SQLite reference backend,
  seeded with one of each aggregate (`tests.unit.domain._samples` - the same sample entities the
  round-trip suite already uses, reused here rather than duplicated). `query_edgedata` points at
  a real, committed edgedata-output file (`eval/dev-net/demand/_runs/low_seed1.edgedata.xml`) so
  it exercises the real XML parse, not a stub path.
- **TraciMCP** (E1.2, Stretch server over the same primitives): the 8 `traci_api` primitives
  against a live SUMO session running DEV-NET's `low` demand profile.

Run from the repo root inside the `resto` conda env (`SUMO_HOME` unset):

    python -m eval.benchmarks.latency [--reps N] [--out PATH]

Writes a Markdown report (mean/median/max per tool, milliseconds) to `--out` (default
`eval/benchmarks/latency-report.md`) and exits 1 if any tool's slowest single call is >= the 1 s
DEV-NET threshold.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.unit.domain._samples import demand, expert_note, network, scenario

from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo import traci_api
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.schemas import ADAPTERS, adapter_for
from resto.domain.constants import SUMO_VERSION
from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.kpis import Kpis
from resto.interface.mcp.database_server import build_server as build_database_server
from resto.interface.mcp.network_server import build_server as build_network_server
from resto.interface.mcp.traci_server import build_server as build_traci_server

DEV_NET_DIR = Path(__file__).resolve().parents[1] / "dev-net"
DEV_NET = DEV_NET_DIR / "dev-net.net.xml"
LOW_ROUTES = DEV_NET_DIR / "demand" / "low.rou.xml"
LOW_EDGEDATA = DEV_NET_DIR / "demand" / "_runs" / "low_seed1.edgedata.xml"

DEFAULT_REPS = 50
THRESHOLD_S = 1.0  # DoD §4.9: single call < 1 s on DEV-NET

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


@dataclass(frozen=True, slots=True)
class ToolTiming:
    server: str
    tool: str
    samples_s: tuple[float, ...]

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.samples_s) * 1000

    @property
    def median_ms(self) -> float:
        return statistics.median(self.samples_s) * 1000

    @property
    def max_ms(self) -> float:
        return max(self.samples_s) * 1000

    @property
    def within_threshold(self) -> bool:
        return max(self.samples_s) < THRESHOLD_S


async def _time_tool(
    server: Any, server_name: str, tool: str, arguments: dict[str, Any], reps: int
) -> ToolTiming:
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        await server.call_tool(tool, arguments)
        samples.append(time.perf_counter() - t0)
    return ToolTiming(server_name, tool, tuple(samples))


async def _bench_calls(
    server: Any, server_name: str, calls: list[tuple[str, dict[str, Any]]], reps: int
) -> list[ToolTiming]:
    return [await _time_tool(server, server_name, tool, args, reps) for tool, args in calls]


async def _bench_network_mcp(reps: int) -> list[ToolTiming]:
    query = SumolibNetworkQuery(DEV_NET)
    server = build_network_server(query)
    calls: list[tuple[str, dict[str, Any]]] = [
        ("get_edge", {"edge_id": "A0A1"}),
        ("get_lanes", {"edge_id": "A0A1"}),
        ("get_neighbours", {"edge_id": "A0A1"}),
        ("shortest_path", {"from_edge": "A0A1", "to_edge": "B0B1"}),
        ("edges_in_bbox", {"xmin": 0.0, "ymin": 0.0, "xmax": 400.0, "ymax": 400.0}),
        ("capacity_estimate", {"edge_id": "A0A1"}),
        ("get_tls", {"tls_id": "A2"}),
    ]
    return await _bench_calls(server, "NetworkMCP", calls, reps)


def _simulation_result_with_real_edgedata() -> SimulationResult:
    """A `SimulationResult` whose edgedata artifact points at a real, committed SUMO
    edgedata-output file rather than `_samples.simulation_result()`'s placeholder path -
    `query_edgedata` parses that file on every call (`adapters/persistence/sqlite/edgedata.py`),
    so timing it against a non-existent path would understate real latency."""
    scn = scenario()
    return SimulationResult(
        result_id="bench-res1",
        scenario_id=scn.scenario_id,
        seed=1,
        mode=RunMode.BATCH,
        status=RunStatus.OK,
        content_hash="bench-rc1",
        artifacts=(ArtifactRef(path=LOW_EDGEDATA, content_hash="bench-ed1", kind="edgedata"),),
        kpis=Kpis(mean_delay=42.0, mean_travel_time=300.0, teleports=0, departed=500, arrived=498),
        wall_clock_s=1.0,
    )


async def _bench_database_mcp(reps: int) -> list[ToolTiming]:
    backend = SqliteDatabase(":memory:")
    server = build_database_server(backend)
    try:
        net, dem, scn, note = network(), demand(), scenario(), expert_note()
        result = _simulation_result_with_real_edgedata()
        intervention_adapter = adapter_for(Intervention)
        interventions_json = [
            intervention_adapter.dump_python(i, mode="json") for i in scn.interventions
        ]
        calls: list[tuple[str, dict[str, Any]]] = [
            ("store_network", {"network_data": ADAPTERS["Network"].dump_python(net, mode="json")}),
            ("get_network", {"network_id": net.network_id}),
            ("list_networks", {}),
            ("find_network", {"label": net.label}),
            ("store_demand", {"demand_data": ADAPTERS["Demand"].dump_python(dem, mode="json")}),
            ("get_demand", {"demand_id": dem.demand_id}),
            ("list_demands", {"network_id": dem.network_id}),
            (
                "store_scenario",
                {"scenario_data": ADAPTERS["Scenario"].dump_python(scn, mode="json")},
            ),
            ("get_scenario", {"scenario_id": scn.scenario_id}),
            (
                "find_similar_scenario",
                {
                    "network_id": scn.network_id,
                    "demand_id": scn.demand_id,
                    "interventions": interventions_json,
                    "context_tags": list(scn.context_tags),
                    "limit": 10,
                },
            ),
            (
                "store_result",
                {"result_data": ADAPTERS["SimulationResult"].dump_python(result, mode="json")},
            ),
            ("get_result", {"result_id": result.result_id}),
            ("list_results", {"scenario_id": result.scenario_id}),
            (
                "query_edgedata",
                {"result_id": result.result_id, "edge_ids": ["B0C0", "C0D0"], "window": None},
            ),
            ("store_note", {"note_data": ADAPTERS["ExpertNote"].dump_python(note, mode="json")}),
            (
                "search_notes",
                {"query": note.text, "network_id": note.network_id, "filters": {}, "limit": 10},
            ),
            ("update_note_status", {"note_id": note.note_id, "status": "confirmed"}),
        ]
        return await _bench_calls(server, "DatabaseMCP", calls, reps)
    finally:
        backend.close()


async def _bench_traci_mcp(reps: int) -> list[ToolTiming]:
    traci_api.start(SUMO_CMD)
    try:
        for _ in range(50):  # let vehicles enter so get_* reads aren't all-zero
            traci_api.step()
        server = build_traci_server()
        calls: list[tuple[str, dict[str, Any]]] = [
            ("get_edge_occupancy", {"edge_id": "B0C0"}),
            ("get_edge_speed", {"edge_id": "B0C0"}),
            ("get_vehicle_count", {"edge_id": "B0C0"}),
            ("close_lane", {"lane_id": "B0C0_1"}),
            ("open_lane", {"lane_id": "B0C0_1"}),
            ("set_speed", {"edge_id": "C0D0", "speed": 10.0}),
            ("set_tls_program", {"tls_id": "A2", "program_id": "0"}),
            ("step", {"n": 1}),
        ]
        return await _bench_calls(server, "TraciMCP", calls, reps)
    finally:
        traci_api.close()


def _render_report(all_timings: list[ToolTiming], reps: int) -> str:
    lines = [
        "# MCP tool latency benchmark — DEV-NET",
        "",
        "Work-plan E1.6 · DoD §4.9 threshold: single call < 1 s on DEV-NET "
        "(< 5 s on REAL-NET — REAL-NET does not exist yet, see work-plan E6).",
        "",
        f"Generated {datetime.now(UTC).isoformat(timespec='seconds')} · {reps} reps/tool · "
        f"SUMO {SUMO_VERSION} · `eval/dev-net/dev-net.net.xml`",
        "",
    ]
    by_server: dict[str, list[ToolTiming]] = {}
    for t in all_timings:
        by_server.setdefault(t.server, []).append(t)

    for server_name, timings in by_server.items():
        lines += [
            f"## {server_name}",
            "",
            "| Tool | mean (ms) | median (ms) | max (ms) | < 1 s |",
            "|---|---|---|---|---|",
        ]
        for t in timings:
            mark = "✅" if t.within_threshold else "❌"
            lines.append(
                f"| `{t.tool}` | {t.mean_ms:.2f} | {t.median_ms:.2f} | {t.max_ms:.2f} | {mark} |"
            )
        lines.append("")

    failures = [t for t in all_timings if not t.within_threshold]
    worst = max(all_timings, key=lambda t: t.max_ms)
    lines += ["## Summary", ""]
    if failures:
        lines.append(
            f"**{len(failures)}/{len(all_timings)} tools exceeded the 1 s DEV-NET threshold**: "
            + ", ".join(f"`{t.server}.{t.tool}` ({t.max_ms:.0f} ms)" for t in failures)
        )
    else:
        lines.append(
            f"All {len(all_timings)} tools stayed under the 1 s DEV-NET threshold across "
            f"{reps} reps each (slowest: `{worst.server}.{worst.tool}`, {worst.max_ms:.2f} ms max)."
        )
    lines.append("")
    return "\n".join(lines)


async def _run(reps: int) -> list[ToolTiming]:
    timings: list[ToolTiming] = []
    timings += await _bench_network_mcp(reps)
    timings += await _bench_database_mcp(reps)
    timings += await _bench_traci_mcp(reps)
    return timings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS)
    parser.add_argument(
        "--out", type=Path, default=Path(__file__).resolve().parent / "latency-report.md"
    )
    args = parser.parse_args()

    timings = asyncio.run(_run(args.reps))
    report = _render_report(timings, args.reps)
    args.out.write_text(report)
    print(report)

    if any(not t.within_threshold for t in timings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
