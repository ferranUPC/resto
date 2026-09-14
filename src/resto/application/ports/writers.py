"""One deterministic writer per SUMO static mechanism; exposed to the Builder agent as tools."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention
from resto.domain.value_objects.mechanism import StaticFileMechanism


class AdditionalFileWriter(Protocol):
    def supports(self, intervention: Intervention) -> bool: ...
    def write(self, intervention: Intervention, out_dir: Path) -> StaticFileMechanism: ...


@dataclass(frozen=True, slots=True)
class SimulationSettings:
    """Everything a scenario cfg says about *what* to simulate (ADR-0017): inputs, time window,
    teleport policy. Never the seed, never output files - those belong to one run and the Runner
    adds them to a derived run cfg. Paths may be given absolute or relative; the writer stores
    them relative to the cfg it writes."""

    net_file: Path
    route_files: tuple[Path, ...]
    additional_files: tuple[Path, ...] = ()
    begin: float = 0.0
    end: float | None = None
    step_length: float = 1.0
    time_to_teleport: float = 300.0

    def __post_init__(self) -> None:
        if not self.route_files:
            raise ValueError("a simulation needs at least one route file")
        if self.begin < 0:
            raise ValueError("begin must be >= 0")
        if self.end is not None and self.end <= self.begin:
            raise ValueError("end must be after begin")
        if self.step_length <= 0:
            raise ValueError("step_length must be > 0")


class SumocfgWriter(Protocol):
    def write(self, settings: SimulationSettings, out_dir: Path, name: str) -> ArtifactRef: ...
