"""SUMO-side ports: everything that shells out to netconvert / duarouter / sumo / TraCI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.topology_modification import TopologyModification


class OsmSource(Protocol):
    def fetch(self, place_or_bbox: str, out_dir: Path) -> ArtifactRef: ...


class NetconvertRunner(Protocol):
    def build(
        self, osm: ArtifactRef | None, plain_dir: Path | None, options: Sequence[str], out_dir: Path
    ) -> ArtifactRef: ...
    def export_plain(self, net_xml: ArtifactRef, out_dir: Path) -> Path: ...


class PlainNetEditor(Protocol):
    """Applies one TopologyModification to the plain XML files in `plain_dir`."""

    def apply(self, plain_dir: Path, modification: TopologyModification) -> None: ...


class DemandTools(Protocol):
    def random_trips(
        self,
        net_xml: ArtifactRef,
        vph: float,
        window: tuple[float, float],
        seed: int,
        out_dir: Path,
    ) -> ArtifactRef: ...
    def duarouter(
        self, net_xml: ArtifactRef, trips: ArtifactRef, seed: int, out_dir: Path
    ) -> ArtifactRef: ...
    def route_sampler(
        self,
        candidates: ArtifactRef,
        edgedata_counts: ArtifactRef,
        options: Sequence[str],
        seed: int,
        out_dir: Path,
    ) -> ArtifactRef: ...


@dataclass(frozen=True, slots=True)
class RunOutput:
    """What one `sumo` execution left behind (ADR-0017). `artifacts` always includes the run cfg
    SUMO was started with (kind `sumocfg`); on success it also holds `edgedata`, `tripinfo`,
    `summary` and `statistics`, and `kpis` is read from the latter. `error` is SUMO's own
    message."""

    ok: bool
    error: str | None
    artifacts: tuple[ArtifactRef, ...]
    wall_clock_s: float
    kpis: Kpis | None = None

    def __post_init__(self) -> None:
        if self.ok and self.kpis is None:
            raise ValueError("a successful run must carry KPIs")
        if not self.ok and not self.error:
            raise ValueError("a failed run must carry the SUMO error message")


class SumoRunner(Protocol):
    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput: ...
    def run_online(
        self, sumocfg: ArtifactRef, script: ArtifactRef, seed: int, out_dir: Path
    ) -> RunOutput: ...
