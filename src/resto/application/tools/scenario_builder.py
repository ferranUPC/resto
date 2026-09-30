"""Tools of the scenario_builder agent as typed Python functions (DoD §2.2; ADR-0007, ADR-0017).

`edge_exists`/`lane_exists` are the Builder's own id checks against NetworkMCP (a `NetworkQuery`
bound to the scenario's network — the same port NetworkMCP wraps, ADR-0009); `write_rerouter`/
`write_vss`/`write_tls_program` wrap the deterministic writers of `adapters/sumo/writers/`
(ADR-0007) — `write_rerouter` now also handles `edge_closure` (E2.3): the writer dispatches on
the intervention's target type, the tool wrapper does not need to know which. `scale_demand`
(E2.3) wraps `use_cases/scale_demand.py` the same way, for the network-wide `demand_scale` case.
Each tool is declared once with `tool` (ADR-0033); the ones that write files take a
`BuilderRun` as `ctx`. `write_taz` and the script tools (`write_traci_script`, `lint_script`,
`dry_run`) arrive with E2.6. Each function is the one implementation, offered in-process to the
Builder or wrapped by an MCP server (ADR-0009).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from resto.application.ports.llm import Tool
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.repositories import DemandRepository, NetworkRepository
from resto.application.ports.sumo import DemandScaler, DemandTools
from resto.application.ports.writers import AdditionalFileWriter, SimulationSettings, SumocfgWriter
from resto.application.tools.declaration import tool
from resto.application.use_cases.scale_demand import scale_demand as scale_demand_use_case
from resto.domain.entities.demand import Demand
from resto.domain.entities.network import Network
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.tasks import ScenarioTask


@dataclass(frozen=True, slots=True)
class BuilderCollaborators:
    """Everything the Builder's tools need that does not depend on the task: repositories, the
    query factory, the writers, the SUMO tools and the root output directory. Built once in the
    composition root; a new mechanism's collaborator is one more field here."""

    networks: NetworkRepository
    demands: DemandRepository
    network_query_factory: Callable[[Path], NetworkQuery]
    rerouter_writer: AdditionalFileWriter
    vss_writer: AdditionalFileWriter
    tls_program_writer: AdditionalFileWriter
    sumocfg_writer: SumocfgWriter
    demand_scaler: DemandScaler
    duarouter: DemandTools
    out_dir: Path


@dataclass(frozen=True, slots=True)
class BuilderRequest:
    """What one Builder run is bound to: the task's interventions and the network, demand, files,
    simulated window and output directory derived from it (`builder_request`)."""

    interventions: Sequence[Intervention]
    query: NetworkQuery
    network: Network
    demand: Demand
    net_file: Path
    route_files: Sequence[Path]
    begin: float
    end: float | None
    out_dir: Path


def builder_request(collaborators: BuilderCollaborators, task: ScenarioTask) -> BuilderRequest:
    """Derives the per-request values from the task. The simulated interval is the demand's
    window; each request writes into its own directory, named after the scenario id it asks for.

    Raises:
        LookupError: the task's network or demand is not in the repositories.
    """
    network = collaborators.networks.get(task.network_id)
    demand = collaborators.demands.get(task.demand_id)
    if network is None or demand is None:
        raise LookupError(f"network {task.network_id!r} or demand {task.demand_id!r} missing")
    requested = scenario_id_for(
        task.network_id, task.demand_id, task.interventions, task.context_tags
    )
    return BuilderRequest(
        interventions=task.interventions,
        query=collaborators.network_query_factory(network.net_xml.path),
        network=network,
        demand=demand,
        net_file=network.net_xml.path,
        route_files=(demand.routes.path,),
        begin=demand.spec.window.start,
        end=demand.spec.window.end,
        out_dir=collaborators.out_dir / requested,
    )


_EdgeId = Annotated[str, Field(description="Edge id, e.g. 'A0A1'.")]
_InterventionIndex = Annotated[
    int, Field(description="Index into this task's interventions list (0-based).")
]
_DemandScaleIndex = Annotated[
    int,
    Field(
        description=(
            "Index into this task's interventions list (0-based); must be a demand_scale "
            "intervention, whose params['scale'] is the multiplicative factor to apply."
        )
    ),
]


@dataclass(slots=True)
class BuilderRun:
    """What the file-writing tools are bound to: the collaborators, the request, and what the run
    has produced so far. The two lists change as tools run, so the class is not frozen.
    `write_sumocfg` reads that state: it lists every additional file written earlier and uses the
    scaled routes once `scale_demand` ran. The first parameter (`ctx`) of those tools; the model
    never sees it."""

    collaborators: BuilderCollaborators
    request: BuilderRequest
    written_additional_files: list[Path] = field(default_factory=list)
    scaled_routes: list[Path] = field(default_factory=list)


@tool(
    name="edge_exists",
    description="Whether `edge_id` exists on the scenario's network.",
)
def edge_exists(ctx: NetworkQuery, edge_id: _EdgeId) -> bool:
    """Whether `edge_id` exists on the scenario's network.

    Example: edge_exists(ctx, "A0A1") -> True
    """
    return ctx.has_edge(edge_id)


@tool(
    name="lane_exists",
    description="Whether lane `lane_index` of `edge_id` exists on the scenario's network.",
)
def lane_exists(
    ctx: NetworkQuery,
    edge_id: _EdgeId,
    lane_index: Annotated[int, Field(description="0-based lane index on that edge.")],
) -> bool:
    """Whether lane `lane_index` of `edge_id` exists on the scenario's network.

    Example: lane_exists(ctx, "A0A1", 0) -> True
    """
    return ctx.has_lane(edge_id, lane_index)


@tool(
    name="write_rerouter",
    description="Writes the rerouter `.add.xml` for a static `lane_closure` intervention.",
)
def write_rerouter(ctx: BuilderRun, intervention_index: _InterventionIndex) -> Mapping[str, Any]:
    """Writes the rerouter `.add.xml` for a static `lane_closure` intervention.

    Also handles `edge_closure`: the writer dispatches on the intervention's target type.

    Returns `{"file_kind": "rerouter", "path": <abs path>, "content_hash": <sha256>}` — use this
    to fill both this intervention's entry in `ScenarioDraft.mechanisms` (a `StaticFileMechanism`)
    and its file in `ScenarioDraft.additional_files` (an `ArtifactRef`, kind `"additional"`).

    Raises:
        ValueError: the intervention is not a static `lane_closure` on a lane or an
            `edge_closure` on an edge.
    """
    return _write_additional_file(ctx, ctx.collaborators.rerouter_writer, intervention_index)


@tool(
    name="write_vss",
    description=(
        "Writes the `variableSpeedSign` `.add.xml` for a static `speed_limit` intervention."
    ),
)
def write_vss(ctx: BuilderRun, intervention_index: _InterventionIndex) -> Mapping[str, Any]:
    """Writes the `variableSpeedSign` `.add.xml` for a static `speed_limit` intervention.

    The intervention's `params` must already carry `speed` and `revert_speed` (m/s) - set by
    whoever assembled the intervention (the Coordinator's `ScenarioTask`); the Builder does not
    look the original speed up itself.

    Returns `{"file_kind": "vss", "path": <abs path>, "content_hash": <sha256>}` — use this
    to fill both this intervention's entry in `ScenarioDraft.mechanisms` (a `StaticFileMechanism`)
    and its file in `ScenarioDraft.additional_files` (an `ArtifactRef`, kind `"additional"`).

    Raises:
        ValueError: the intervention is not a static `speed_limit` on a lane, or is missing
            `speed`/`revert_speed`.
    """
    return _write_additional_file(ctx, ctx.collaborators.vss_writer, intervention_index)


@tool(
    name="write_tls_program",
    description=(
        "Writes the WAUT program-switch `.add.xml` for a static `signal_program` intervention."
    ),
)
def write_tls_program(ctx: BuilderRun, intervention_index: _InterventionIndex) -> Mapping[str, Any]:
    """Writes the WAUT program-switch `.add.xml` for a static `signal_program` intervention.

    The intervention's `params` must already carry `program_id` (and, optionally,
    `original_program_id`) — the target `tlLogic` program must already exist on the network; this
    tool does not author it.

    Returns `{"file_kind": "tls_program", "path": <abs path>, "content_hash": <sha256>}` — use this
    to fill both this intervention's entry in `ScenarioDraft.mechanisms` (a `StaticFileMechanism`)
    and its file in `ScenarioDraft.additional_files` (an `ArtifactRef`, kind `"additional"`).

    Raises:
        ValueError: the intervention is not a static `signal_program` on a `TlsTarget`, or is
            missing `params['program_id']`.
    """
    return _write_additional_file(ctx, ctx.collaborators.tls_program_writer, intervention_index)


def _write_additional_file(
    run: BuilderRun, writer: AdditionalFileWriter, intervention_index: int
) -> Mapping[str, Any]:
    intervention = run.request.interventions[intervention_index]
    mechanism, ref = writer.write(intervention, run.request.out_dir)
    run.written_additional_files.append(Path(ref.path))
    return {
        "file_kind": mechanism.file_kind,
        "path": str(ref.path),
        "content_hash": ref.content_hash,
    }


@tool(
    name="scale_demand",
    description="Regenerates `demand` at `factor` times its current volume, routed over `network`.",
)
def scale_demand(ctx: BuilderRun, intervention_index: _DemandScaleIndex) -> Mapping[str, Any]:
    """Regenerates the demand at the intervention's `scale` times its current volume, routed over
    the network.

    No LLM involved — deterministic resample + `duarouter` (`use_cases/scale_demand.py`); this
    is the Builder tool that flattens the result to a JSON-shaped dict, same pattern as
    `write_rerouter`/`write_vss`/`write_tls_program`.

    Returns `{"demand_id": ..., "routes_path": <abs path>}` — `demand_id` fills the intervention's
    `RegenerateDemandMechanism.demand_id` and becomes the `Scenario`'s actual `demand_id`;
    `routes_path` is what `write_sumocfg` uses in place of the original demand's routes.

    Raises:
        ValueError: the scale is not positive, or the demand and network do not match.
    """
    request = ctx.request
    collaborators = ctx.collaborators
    factor = float(request.interventions[intervention_index].params["scale"])
    derived = scale_demand_use_case(
        request.demand,
        request.network,
        factor,
        scaler=collaborators.demand_scaler,
        duarouter=collaborators.duarouter,
        demands=collaborators.demands,
        out_dir=request.out_dir,
    )
    ctx.scaled_routes[:] = [derived.routes.path]
    return {"demand_id": derived.demand_id, "routes_path": str(derived.routes.path)}


@tool(
    name="write_sumocfg",
    description="Write the scenario's sumocfg once every intervention has been handled.",
)
def write_sumocfg(ctx: BuilderRun) -> Mapping[str, Any]:
    """Writes the scenario's `.sumocfg`: what to simulate, never the seed or the outputs
    (the Runner adds those per run). Paths are stored relative to the cfg.

    Takes no arguments: the network file and the simulated window come from the network and demand
    the Coordinator already picked, the additional files are every one written so far in this run
    (the agent cannot forget to list one), and the routes are the original demand's unless
    `scale_demand` ran (a `demand_scale` intervention is network-wide, so at most one such call
    matters per run).

    Returns `{"path": <abs path>, "content_hash": <sha256>, "kind": "sumocfg"}`.

    Raises:
        ValueError: no route file, or an inconsistent time window.
    """
    request = ctx.request
    settings = SimulationSettings(
        net_file=request.net_file,
        route_files=tuple(ctx.scaled_routes or request.route_files),
        additional_files=tuple(ctx.written_additional_files),
        begin=request.begin,
        end=request.end,
    )
    ref = ctx.collaborators.sumocfg_writer.write(settings, request.out_dir, "scenario.sumocfg")
    return {"path": str(ref.path), "content_hash": ref.content_hash, "kind": ref.kind}


def build_scenario_builder_tools(
    collaborators: BuilderCollaborators, request: BuilderRequest
) -> tuple[Tool, ...]:
    """The Builder's tool set, bound to one request's network/demand/task/output directory.

    Each tool still names one mechanism, so the choice stays visible in the trace (ADR-0007).
    """
    run = BuilderRun(collaborators, request)
    return (
        edge_exists.bind(request.query),
        lane_exists.bind(request.query),
        write_rerouter.bind(run),
        write_vss.bind(run),
        write_tls_program.bind(run),
        scale_demand.bind(run),
        write_sumocfg.bind(run),
    )
