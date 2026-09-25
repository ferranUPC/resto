"""The 20 rows of the DEV-NET/peak scenario matrix (work-plan E3.1; architecture §3's own example
table) and `build_draft`, which turns one `MatrixRow` into a `ScenarioDraft` the same way the
Scenario Builder agent would (E2.2/E2.3's writers, no LLM involved - these are hand-authored
ground truth, not a Builder-bank grading run, that is E2.7's job).

Locations: `B2C2`/`C2D2`/`A2B2`/`D2E2` (row-2 signalised corridor, interior edges - not fringe dead
ends), `B0C0`/`C0D0` (the designed 2->1 bottleneck), `A1B1`/`B1C1`/`C1D1` (plain row-1 edges, no
TLS, no bottleneck) - every location already appears in `eval/dev-net/README.md`'s own topology
description.

Windows are time of day (ADR-0028): the `peak` demand covers 08:00-09:00 (`[28800, 32400)`) and
every run starts SUMO at 08:00 (`BEGIN_S`). The matrix was first built on `[0, 3600)` and moved to
the morning by E3.8.

Every `lane_closure`/`edge_closure`/`speed_limit` row's window is exactly 08:00-08:05
(`[28800, 29100)`), not just aligned to the Runner's fixed 300s `EDGEDATA_PERIOD_S`
(`verify.effects._interval` only matches a window that lines up exactly with one edgedata interval
boundary, and intervals start at SUMO's `begin`) but starting at the demand's first departure
specifically - found empirically while first building this matrix: a window starting later in the
hour-long `peak` run (e.g. 08:05-08:10) can have a vehicle that entered the target edge just
before the window started and is still on it when the window opens, which registers nonzero
`sampledSeconds` with zero `entered` - a real, correct SUMO behaviour (the closure stops new
entries; it does not teleport a vehicle already mid-edge) that `verify_edge_flow`'s "zero flow
inside the window" check has no way to distinguish from the closure not working. `verify/`'s own
`lane_closure`/`edge_closure`/`speed_limit` tests already used the first 300 s for the same reason
(their own module docstrings say so); this generalises that constraint to every row here instead
of re-discovering it per row. Diversity across these rows comes from location and mechanism, not
window offset. `signal_program` rows are not edgedata-checked (`build.py`'s `_verify_effect`), so
their windows are free to vary and do; they are whole minutes (three-minute windows from 08:02),
the way a user would state them.

Every `demand_scale` intervention carries its `factor` in `params` - found empirically while
first building this matrix: `scenario_id_for` hashes `(network_id, task.demand_id, interventions,
context_tags)`, and `task.demand_id` is deliberately the *original* demand id regardless of which
derived demand a `demand_scale` mechanism produces (`build_scenario.py`'s own
`_effective_demand_id` docstring). Two `demand_scale` interventions with no other distinguishing
field (same window, same `target=None`) therefore hash identically regardless of `factor` unless
the factor itself is part of the intervention's own content - without it, S17/S18/S19 would
collide on one `scenario_id` and silently share whichever factor happened to be promoted first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from eval.scenario_matrix.tls_alt_program import ALT_PROGRAM_ID, write_alt_program
from resto.adapters.persistence.filesystem import artifact_ref
from resto.adapters.sumo.demand import SumoDemandTools
from resto.adapters.sumo.demand_scaling import SumoDemandScaler
from resto.adapters.sumo.writers.rerouter import RerouterWriter
from resto.adapters.sumo.writers.sumocfg import SumocfgFileWriter
from resto.adapters.sumo.writers.tls_program import TlsProgramWriter
from resto.adapters.sumo.writers.vss import VssWriter
from resto.application.ports.repositories import DemandRepository
from resto.application.ports.writers import SimulationSettings
from resto.application.use_cases.scale_demand import scale_demand
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import EdgeTarget, LaneTarget, TlsTarget
from resto.domain.value_objects.mechanism import RegenerateDemandMechanism
from resto.domain.value_objects.time_window import TimeWindow

# Every window is time of day (ADR-0028): the `peak` demand covers 08:00-09:00.
BEGIN_S = 28800.0
END_S = 32400.0
REVERT_SPEED_MPS = 13.89  # DEV-NET's default 50 km/h lane speed (eval/dev-net/README.md)


@dataclass(frozen=True, slots=True)
class MatrixRow:
    id: str
    mechanism: str
    description: str
    edge_id: str | None = None
    lane_index: int | None = None
    tls_id: str | None = None
    window: TimeWindow | None = None
    speed_mps: float | None = None
    factor: float | None = None


ROWS: tuple[MatrixRow, ...] = (
    MatrixRow("S00", "baseline", "no interventions"),
    MatrixRow(
        "S01", "lane_closure",
        "lane_closure B2C2 lane 0, 08:00-08:05",
        edge_id="B2C2", lane_index=0, window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S02", "lane_closure",
        "lane_closure C2D2 lane 0, 08:00-08:05",
        edge_id="C2D2", lane_index=0, window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S03", "lane_closure",
        "lane_closure B0C0 lane 0, 08:00-08:05 (bottleneck approach, lane 1 stays open)",
        edge_id="B0C0", lane_index=0, window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S04", "lane_closure",
        "lane_closure C1D1 lane 0, 08:00-08:05",
        edge_id="C1D1", lane_index=0, window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S05", "edge_closure",
        "edge_closure C0D0, 08:00-08:05 (bottleneck exit, single lane - full closure)",
        edge_id="C0D0", window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S06", "edge_closure",
        "edge_closure A1B1, 08:00-08:05",
        edge_id="A1B1", window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S07", "edge_closure",
        "edge_closure D2E2, 08:00-08:05",
        edge_id="D2E2", window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S08", "edge_closure",
        "edge_closure B2C2, 08:00-08:05",
        edge_id="B2C2", window=TimeWindow(28800.0, 29100.0),
    ),
    MatrixRow(
        "S09", "speed_limit",
        "speed_limit B2C2 lane 0 at 5 m/s, 08:00-08:05",
        edge_id="B2C2", lane_index=0, window=TimeWindow(28800.0, 29100.0), speed_mps=5.0,
    ),
    MatrixRow(
        "S10", "speed_limit",
        "speed_limit C1D1 lane 0 at 5 m/s, 08:00-08:05",
        edge_id="C1D1", lane_index=0, window=TimeWindow(28800.0, 29100.0), speed_mps=5.0,
    ),
    MatrixRow(
        "S11", "speed_limit",
        "speed_limit A2B2 lane 0 at 8 m/s, 08:00-08:05",
        edge_id="A2B2", lane_index=0, window=TimeWindow(28800.0, 29100.0), speed_mps=8.0,
    ),
    MatrixRow(
        "S12", "speed_limit",
        "speed_limit B0C0 lane 0 at 5 m/s, 08:00-08:05",
        edge_id="B0C0", lane_index=0, window=TimeWindow(28800.0, 29100.0), speed_mps=5.0,
    ),
    MatrixRow(
        "S13", "signal_program",
        "signal_program C2 -> program 1, 08:02-08:05",
        tls_id="C2", window=TimeWindow(28920.0, 29100.0),
    ),
    MatrixRow(
        "S14", "signal_program",
        "signal_program B2 -> program 1, 08:05-08:08",
        tls_id="B2", window=TimeWindow(29100.0, 29280.0),
    ),
    MatrixRow(
        "S15", "signal_program",
        "signal_program D2 -> program 1, 08:08-08:11",
        tls_id="D2", window=TimeWindow(29280.0, 29460.0),
    ),
    MatrixRow(
        "S16", "signal_program",
        "signal_program A2 -> program 1, 08:11-08:14",
        tls_id="A2", window=TimeWindow(29460.0, 29640.0),
    ),
    MatrixRow("S17", "demand_scale", "demand_scale x1.2 (heavier peak)", factor=1.2),
    MatrixRow("S18", "demand_scale", "demand_scale x0.8 (lighter peak)", factor=0.8),
    MatrixRow("S19", "demand_scale", "demand_scale x1.5 (much heavier peak)", factor=1.5),
)


def build_draft(
    row: MatrixRow,
    *,
    net_ref: ArtifactRef,
    peak_routes_ref: ArtifactRef,
    network: Network,
    demand: Demand,
    demands: DemandRepository,
    out_dir: Path,
) -> ScenarioDraft:
    """The `ScenarioDraft` for `row` - built by the same deterministic writers the Builder agent's
    tools call (`application/tools/scenario_builder.py`), just invoked directly."""
    row_dir = out_dir / row.id
    sumocfg_writer = SumocfgFileWriter()

    if row.mechanism == "baseline":
        sumocfg = sumocfg_writer.write(
            _settings(net_ref.path, (peak_routes_ref.path,), ()), row_dir, "scenario.sumocfg"
        )
        return ScenarioDraft(
            interventions=(), mechanisms=(), sumocfg=sumocfg, rationale=row.description
        )

    if row.mechanism == "lane_closure":
        assert row.edge_id is not None and row.lane_index is not None and row.window is not None
        intervention = Intervention(
            type=InterventionType.LANE_CLOSURE,
            target=LaneTarget(edge_id=row.edge_id, lane_index=row.lane_index),
            window=row.window,
        )
        mechanism, ref = RerouterWriter().write(intervention, row_dir)
        sumocfg = sumocfg_writer.write(
            _settings(net_ref.path, (peak_routes_ref.path,), (ref.path,)),
            row_dir, "scenario.sumocfg",
        )
        return ScenarioDraft(
            interventions=(intervention,), mechanisms=(mechanism,), sumocfg=sumocfg,
            additional_files=(ref,), rationale=row.description,
        )

    if row.mechanism == "edge_closure":
        assert row.edge_id is not None and row.window is not None
        intervention = Intervention(
            type=InterventionType.EDGE_CLOSURE, target=EdgeTarget(edge_id=row.edge_id),
            window=row.window,
        )
        mechanism, ref = RerouterWriter().write(intervention, row_dir)
        sumocfg = sumocfg_writer.write(
            _settings(net_ref.path, (peak_routes_ref.path,), (ref.path,)),
            row_dir, "scenario.sumocfg",
        )
        return ScenarioDraft(
            interventions=(intervention,), mechanisms=(mechanism,), sumocfg=sumocfg,
            additional_files=(ref,), rationale=row.description,
        )

    if row.mechanism == "speed_limit":
        assert (
            row.edge_id is not None
            and row.lane_index is not None
            and row.window is not None
            and row.speed_mps is not None
        )
        intervention = Intervention(
            type=InterventionType.SPEED_LIMIT,
            target=LaneTarget(edge_id=row.edge_id, lane_index=row.lane_index),
            window=row.window,
            params={"speed": row.speed_mps, "revert_speed": REVERT_SPEED_MPS},
        )
        mechanism, ref = VssWriter().write(intervention, row_dir)
        sumocfg = sumocfg_writer.write(
            _settings(net_ref.path, (peak_routes_ref.path,), (ref.path,)),
            row_dir, "scenario.sumocfg",
        )
        return ScenarioDraft(
            interventions=(intervention,), mechanisms=(mechanism,), sumocfg=sumocfg,
            additional_files=(ref,), rationale=row.description,
        )

    if row.mechanism == "signal_program":
        assert row.tls_id is not None and row.window is not None
        alt_program_path = write_alt_program(row_dir, row.tls_id, net_ref.path)
        intervention = Intervention(
            type=InterventionType.SIGNAL_PROGRAM, target=TlsTarget(tls_id=row.tls_id),
            window=row.window, params={"program_id": ALT_PROGRAM_ID},
        )
        mechanism, waut_ref = TlsProgramWriter().write(intervention, row_dir)
        alt_program_ref = artifact_ref(alt_program_path, "additional")
        sumocfg = sumocfg_writer.write(
            _settings(net_ref.path, (peak_routes_ref.path,), (alt_program_path, waut_ref.path)),
            row_dir, "scenario.sumocfg",
        )
        return ScenarioDraft(
            interventions=(intervention,), mechanisms=(mechanism,), sumocfg=sumocfg,
            additional_files=(alt_program_ref, waut_ref), rationale=row.description,
        )

    if row.mechanism == "demand_scale":
        assert row.factor is not None
        derived = scale_demand(
            demand, network, row.factor,
            scaler=SumoDemandScaler(), duarouter=SumoDemandTools(), demands=demands,
            out_dir=row_dir,
        )
        intervention = Intervention(
            type=InterventionType.DEMAND_SCALE, target=None, window=TimeWindow(BEGIN_S, END_S),
            params={"factor": row.factor},
        )
        regenerate_mechanism = RegenerateDemandMechanism(demand_id=derived.demand_id)
        sumocfg = sumocfg_writer.write(
            _settings(net_ref.path, (derived.routes.path,), ()), row_dir, "scenario.sumocfg"
        )
        return ScenarioDraft(
            interventions=(intervention,), mechanisms=(regenerate_mechanism,), sumocfg=sumocfg,
            rationale=row.description,
        )

    raise ValueError(f"unknown row mechanism {row.mechanism!r}")


def _settings(
    net_file: Path, route_files: tuple[Path, ...], additional_files: tuple[Path, ...]
) -> SimulationSettings:
    return SimulationSettings(
        net_file=net_file, route_files=route_files, additional_files=additional_files,
        begin=BEGIN_S, end=END_S,
    )
