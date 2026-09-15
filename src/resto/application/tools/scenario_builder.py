"""Tools of the scenario_builder agent as typed Python functions (DoD §2.2; ADR-0007, ADR-0017).

`edge_exists`/`lane_exists` are the Builder's own id checks against NetworkMCP (a `NetworkQuery`
bound to the scenario's network — the same port NetworkMCP wraps, ADR-0009); `write_rerouter`/
`write_vss` wrap the deterministic writers of `adapters/sumo/writers/` (ADR-0007). `write_taz`/
`write_tls_program` and the script tools (`write_traci_script`, `lint_script`, `dry_run`) arrive
with E2.3/E2.6. Each function is the one implementation, offered in-process to the Builder or
wrapped by an MCP server (ADR-0009).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from resto.application.ports.llm import Tool
from resto.application.ports.network_query import NetworkQuery
from resto.application.ports.writers import AdditionalFileWriter, SimulationSettings, SumocfgWriter
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention


def edge_exists(query: NetworkQuery, edge_id: str) -> bool:
    """Whether `edge_id` exists on the scenario's network.

    Example: edge_exists(query, "A0A1") -> True
    """
    return query.has_edge(edge_id)


def lane_exists(query: NetworkQuery, edge_id: str, lane_index: int) -> bool:
    """Whether lane `lane_index` of `edge_id` exists on the scenario's network.

    Example: lane_exists(query, "A0A1", 0) -> True
    """
    return query.has_lane(edge_id, lane_index)


def write_rerouter(
    writer: AdditionalFileWriter, intervention: Intervention, out_dir: Path
) -> Mapping[str, Any]:
    """Writes the rerouter `.add.xml` for a static `lane_closure` intervention.

    Returns `{"file_kind": "rerouter", "path": <abs path>, "content_hash": <sha256>}` — use this
    to fill both this intervention's entry in `ScenarioDraft.mechanisms` (a `StaticFileMechanism`)
    and its file in `ScenarioDraft.additional_files` (an `ArtifactRef`, kind `"additional"`).

    Raises:
        ValueError: `intervention` is not a static `lane_closure` on a lane.
    """
    return _write_additional_file(writer, intervention, out_dir)


def write_vss(
    writer: AdditionalFileWriter, intervention: Intervention, out_dir: Path
) -> Mapping[str, Any]:
    """Writes the `variableSpeedSign` `.add.xml` for a static `speed_limit` intervention.

    `intervention.params` must already carry `speed` and `revert_speed` (m/s) - set by whoever
    assembled the intervention (the Coordinator's `ScenarioTask`); the Builder does not look the
    original speed up itself.

    Returns `{"file_kind": "vss", "path": <abs path>, "content_hash": <sha256>}` — use this
    to fill both this intervention's entry in `ScenarioDraft.mechanisms` (a `StaticFileMechanism`)
    and its file in `ScenarioDraft.additional_files` (an `ArtifactRef`, kind `"additional"`).

    Raises:
        ValueError: `intervention` is not a static `speed_limit` on a lane, or is missing
            `speed`/`revert_speed`.
    """
    return _write_additional_file(writer, intervention, out_dir)


def _write_additional_file(
    writer: AdditionalFileWriter, intervention: Intervention, out_dir: Path
) -> Mapping[str, Any]:
    mechanism, ref = writer.write(intervention, out_dir)
    return {
        "file_kind": mechanism.file_kind,
        "path": str(ref.path),
        "content_hash": ref.content_hash,
    }


def write_sumocfg(
    writer: SumocfgWriter,
    net_file: Path,
    route_files: Sequence[Path],
    out_dir: Path,
    *,
    additional_files: Sequence[Path] = (),
    begin: float = 0.0,
    end: float | None = None,
    step_length: float = 1.0,
    time_to_teleport: float = 300.0,
    name: str = "scenario.sumocfg",
) -> ArtifactRef:
    """Writes the scenario's `.sumocfg`: what to simulate, never the seed or the outputs
    (the Runner adds those per run). Paths are stored relative to the cfg.

    Example: write_sumocfg(writer, net, [routes], out_dir, additional_files=[closure],
        begin=0, end=3600) -> ArtifactRef(path=out_dir/"scenario.sumocfg", kind="sumocfg")

    Raises:
        ValueError: no route file, or an inconsistent time window.
    """
    settings = SimulationSettings(
        net_file=Path(net_file),
        route_files=tuple(Path(p) for p in route_files),
        additional_files=tuple(Path(p) for p in additional_files),
        begin=begin,
        end=end,
        step_length=step_length,
        time_to_teleport=time_to_teleport,
    )
    return writer.write(settings, Path(out_dir), name)


_EDGE_EXISTS_SCHEMA = {
    "type": "object",
    "properties": {"edge_id": {"type": "string", "description": "Edge id, e.g. 'A0A1'."}},
    "required": ["edge_id"],
}
_LANE_EXISTS_SCHEMA = {
    "type": "object",
    "properties": {
        "edge_id": {"type": "string", "description": "Edge id, e.g. 'A0A1'."},
        "lane_index": {"type": "integer", "description": "0-based lane index on that edge."},
    },
    "required": ["edge_id", "lane_index"],
}
_INTERVENTION_INDEX_SCHEMA = {
    "type": "object",
    "properties": {
        "intervention_index": {
            "type": "integer",
            "description": "Index into this task's interventions list (0-based).",
        }
    },
    "required": ["intervention_index"],
}


def build_scenario_builder_tools(
    *,
    query: NetworkQuery,
    interventions: Sequence[Intervention],
    net_file: Path,
    route_files: Sequence[Path],
    begin: float,
    end: float | None,
    rerouter_writer: AdditionalFileWriter,
    vss_writer: AdditionalFileWriter,
    sumocfg_writer: SumocfgWriter,
    out_dir: Path,
) -> tuple[Tool, ...]:
    """The Builder's E2.2 Minimal tool set, bound to one network/task/output directory.

    `write_sumocfg` takes no arguments: `net_file`/`route_files`/`begin`/`end` come from the
    network and demand the Coordinator already picked (not something the Builder decides), and
    the additional files are every one `write_rerouter`/`write_vss` produced so far in this run —
    the agent cannot forget to list one.
    """
    written_additional_files: list[Path] = []

    def _edge_exists(edge_id: str) -> bool:
        return edge_exists(query, edge_id)

    def _lane_exists(edge_id: str, lane_index: int) -> bool:
        return lane_exists(query, edge_id, lane_index)

    def _write_rerouter(intervention_index: int) -> Mapping[str, Any]:
        result = write_rerouter(rerouter_writer, interventions[intervention_index], out_dir)
        written_additional_files.append(Path(result["path"]))
        return result

    def _write_vss(intervention_index: int) -> Mapping[str, Any]:
        result = write_vss(vss_writer, interventions[intervention_index], out_dir)
        written_additional_files.append(Path(result["path"]))
        return result

    def _write_sumocfg() -> Mapping[str, Any]:
        ref = write_sumocfg(
            sumocfg_writer,
            net_file,
            route_files,
            out_dir,
            additional_files=tuple(written_additional_files),
            begin=begin,
            end=end,
        )
        return {"path": str(ref.path), "content_hash": ref.content_hash, "kind": ref.kind}

    return (
        Tool(
            name="edge_exists",
            description=(edge_exists.__doc__ or "").strip().splitlines()[0],
            fn=_edge_exists,
            input_schema=_EDGE_EXISTS_SCHEMA,
        ),
        Tool(
            name="lane_exists",
            description=(lane_exists.__doc__ or "").strip().splitlines()[0],
            fn=_lane_exists,
            input_schema=_LANE_EXISTS_SCHEMA,
        ),
        Tool(
            name="write_rerouter",
            description=(write_rerouter.__doc__ or "").strip().splitlines()[0],
            fn=_write_rerouter,
            input_schema=_INTERVENTION_INDEX_SCHEMA,
        ),
        Tool(
            name="write_vss",
            description=(write_vss.__doc__ or "").strip().splitlines()[0],
            fn=_write_vss,
            input_schema=_INTERVENTION_INDEX_SCHEMA,
        ),
        Tool(
            name="write_sumocfg",
            description="Write the scenario's sumocfg once every intervention has been handled.",
            fn=_write_sumocfg,
            input_schema={"type": "object", "properties": {}},
        ),
    )
