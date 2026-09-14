"""Tools of the scenario_builder agent as typed Python functions (DoD §2.2; ADR-0007, ADR-0017).

E2.1 adds `write_sumocfg`; the mechanism writers (`write_rerouter`, `write_vss`, ...), the id
checks and the script tools arrive with E2.2 / E2.6. Each function is the one implementation,
offered in-process to the Builder or wrapped by an MCP server (ADR-0009).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from resto.application.ports.writers import SimulationSettings, SumocfgWriter
from resto.domain.value_objects.artifact_ref import ArtifactRef


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
