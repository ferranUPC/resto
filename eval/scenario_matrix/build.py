"""Builds the DEV-NET/peak scenario matrix (work-plan E3.1) and writes `matrix-report.md`.

Run from the repo root inside the `resto` conda env (`SUMO_HOME` unset):

    python -m eval.scenario_matrix.build

For each `eval.scenario_matrix.rows.ROWS` row: builds the `ScenarioDraft` (`rows.build_draft`,
E2.2/E2.3's deterministic writers, no LLM - ADR-0001's promotion split still applies, just with a
hand-authored draft standing in for what the Builder agent would have produced), promotes it
through the real `build_scenario` use case, then runs it with the real `SubprocessSumoRunner` at
seeds 1/2/3 through `run_simulation`. Every store goes through `DatabaseMCP` proper (a real MCP
`ClientSession` over `InMemoryTransport`, `adapters/persistence/mcp_client.py` - the same adapter
the conformance suite runs through), backed by the `SqliteDatabase` reference implementation
persisted to `matrix.db` next to this file - not the repository classes called in-process, so this
script exercises the actual contract, matching the work-plan's own "stored via DatabaseMCP".

Idempotent: `build_scenario`/`run_simulation`/`scale_demand` all dedupe on content/request hashes,
and `SqliteDatabase`'s `_idempotent_store` no-ops a byte-identical repeat row - re-running this
script after the first successful run touches no SUMO process again ("zero redundant
simulations", architecture §1).

Where cheap (the row's own seed-1 edgedata/KPIs, no extra SUMO run needed), each row's actual
observable effect is re-checked with `verify.effects` (E2.4) before it counts as built - the point
of this matrix is to be *known-good* ground truth, so a row whose intervention silently did
nothing must fail the build, not quietly end up in the DB. `signal_program` rows are not checked
this way (that would need a second run with a TLS-switch log, `verify.effects.
run_with_tls_switch_log` - E2.4's own test suite already covers `signal_program` correctness, so
duplicating that cost per matrix row would not buy new confidence).
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

from mcp.client._memory import InMemoryTransport
from verify.effects import (
    count_scheduled_vehicles,
    verify_demand_scale,
    verify_edge_flow,
    verify_speed_limit,
)

from eval.scenario_matrix.rows import ROWS, MatrixRow, build_draft
from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.adapters.sumo.outputs import parse_edgedata
from resto.adapters.sumo.runner import SubprocessSumoRunner
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.use_cases.build_scenario import build_scenario
from resto.application.use_cases.run_simulation import run_simulation
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.entities.simulation_result import RunStatus, SimulationResult
from resto.domain.value_objects.demand_spec import DemandProfile, DemandSpec
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.sanity_report import SanityReport
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import ScenarioTask
from resto.domain.value_objects.time_window import TimeWindow
from resto.interface.mcp.database_server import build_server

MATRIX_DIR = Path(__file__).resolve().parent
DEV_NET_DIR = MATRIX_DIR.parent / "dev-net"
DB_PATH = MATRIX_DIR / "matrix.db"
RUNS_DIR = MATRIX_DIR / "runs"
REPORT_PATH = MATRIX_DIR / "matrix-report.md"
SEEDS = (1, 2, 3)
CONTEXT_TAGS = frozenset({"peak"})


class MatrixBuildError(RuntimeError):
    """A row's promotion, simulation, or effect check failed - the matrix must not be marked
    built while any row is silently wrong."""


def _dev_net_network() -> Network:
    net_ref = artifact_ref(DEV_NET_DIR / "dev-net.net.xml", "net")
    return Network(
        network_id=net_ref.content_hash,
        net_xml=net_ref,
        recipe=NetworkRecipe(
            source=NetworkSource(kind="file", value=str(DEV_NET_DIR / "generate.sh"))
        ),
        sanity_report=SanityReport(
            largest_scc_ratio=1.0, zero_length_edges=0, all_reachable_from_fringe=True
        ),
        label="dev-net",
    )


def _peak_demand(network_id: str) -> Demand:
    trips_ref = artifact_ref(DEV_NET_DIR / "demand" / "peak.trips.xml", "trips")
    routes_ref = artifact_ref(DEV_NET_DIR / "demand" / "peak.rou.xml", "routes")
    return Demand(
        demand_id=trips_ref.content_hash,
        network_id=network_id,
        spec=DemandSpec(
            profile=DemandProfile.PEAK, window=TimeWindow(0.0, 3600.0), seed=1,
            vehicles_per_hour=1200.0,
        ),
        trips=trips_ref,
        routes=routes_ref,
    )


def _verify_effect(row: MatrixRow, seed1: SimulationResult, peak_trips: Path) -> None:
    """Re-checks the row's own DoD §4.5 effect against its seed-1 result. Raises
    `MatrixBuildError` if the intervention did not observably do what the row claims."""
    if row.mechanism in ("baseline", "signal_program"):
        return
    assert seed1.kpis is not None
    edgedata_path = next(a.path for a in seed1.artifacts if a.kind == "edgedata")
    edgedata = parse_edgedata(edgedata_path)

    if row.mechanism in ("lane_closure", "edge_closure"):
        assert row.edge_id is not None and row.window is not None
        result = verify_edge_flow(edgedata, row.edge_id, row.window)
    elif row.mechanism == "speed_limit":
        assert row.edge_id is not None and row.window is not None and row.speed_mps is not None
        result = verify_speed_limit(edgedata, row.edge_id, row.window, row.speed_mps)
    elif row.mechanism == "demand_scale":
        assert row.factor is not None
        expected = round(count_scheduled_vehicles(peak_trips) * row.factor)
        result = verify_demand_scale(seed1.kpis.departed, expected)
    else:
        raise AssertionError(f"unhandled mechanism {row.mechanism!r}")

    if not result.ok:
        raise MatrixBuildError(
            f"{row.id} ({row.mechanism}) failed its effect check: {result.reason}"
        )


def build_matrix() -> list[dict[str, object]]:
    network = _dev_net_network()
    demand = _peak_demand(network.network_id)
    net_ref = network.net_xml
    peak_routes_ref = demand.routes

    backend = SqliteDatabase(str(DB_PATH))
    server = build_server(backend)
    db = McpClientDatabase(lambda: InMemoryTransport(server))
    runner = SubprocessSumoRunner()
    report_rows: list[dict[str, object]] = []
    try:
        db.networks.store(network)
        db.demands.store(demand)

        for row in ROWS:
            row_dir = RUNS_DIR / row.id
            draft = build_draft(
                row, net_ref=net_ref, peak_routes_ref=peak_routes_ref, network=network,
                demand=demand, demands=db.demands, out_dir=row_dir / "build",
            )
            run = AgentRun(
                output=draft, tool_calls=(), usage=Usage(), stop_reason=StopReason.OUTPUT
            )
            task = ScenarioTask(
                network_id=network.network_id, demand_id=demand.demand_id, context_tags=CONTEXT_TAGS
            )
            scenario = build_scenario(
                task, run,
                networks=db.networks, demands=db.demands, scenarios=db.scenarios,
                network_query_factory=lambda p: SumolibNetworkQuery(p),
                runner=runner, out_dir=row_dir / "load_check",
            )

            results: dict[int, SimulationResult] = {}
            for seed in SEEDS:
                results[seed] = run_simulation(
                    scenario, seed, runner=runner, results=db.results, out_dir=row_dir / "runs"
                )
                if results[seed].status is not RunStatus.OK:
                    raise MatrixBuildError(
                        f"{row.id} seed {seed} failed: {results[seed].error}"
                    )

            _verify_effect(row, results[1], demand.trips.path)

            departed = [r.kpis.departed for r in results.values() if r.kpis is not None]
            delay = [r.kpis.mean_delay for r in results.values() if r.kpis is not None]
            report_rows.append(
                {
                    "id": row.id,
                    "mechanism": row.mechanism,
                    "description": row.description,
                    "scenario_id": scenario.scenario_id[:12],
                    "seeds": SEEDS,
                    "departed_mean": statistics.mean(departed),
                    "delay_mean": statistics.mean(delay),
                }
            )
            print(f"{row.id:<5} {row.mechanism:<14} ok  scenario_id={scenario.scenario_id[:12]}")
    finally:
        db.close()
        backend.close()

    return report_rows


def _write_report(report_rows: list[dict[str, object]]) -> None:
    lines = [
        "# DEV-NET/peak scenario matrix (work-plan E3.1)",
        "",
        f"Built by `python -m eval.scenario_matrix.build` from `eval/scenario_matrix/rows.py` "
        f"({len(report_rows)} rows x {len(SEEDS)} seeds = {len(report_rows) * len(SEEDS)} "
        "`SimulationResult`s), stored via DatabaseMCP in `matrix.db`. Each row's own DoD §4.5 "
        "effect is re-checked against its seed-1 result before it counts as built (skipped for "
        "`signal_program`, `baseline` - see `build.py`'s module docstring).",
        "",
        "| scenario_id | mechanism | description | mean departed (3 seeds) | mean delay (s) |",
        "|---|---|---|---|---|",
    ]
    for row in report_rows:
        lines.append(
            f"| {row['id']} (`{row['scenario_id']}`) | {row['mechanism']} | {row['description']} "
            f"| {row['departed_mean']:.1f} | {row['delay_mean']:.1f} |"
        )
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    report_rows = build_matrix()
    _write_report(report_rows)
    print(f"\n{len(report_rows)} scenarios built, {REPORT_PATH} written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
