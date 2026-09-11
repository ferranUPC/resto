"""SUMO-side ports: everything that shells out to netconvert / duarouter / sumo / TraCI."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef
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


class SumoRunner(Protocol):
    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput: ...
    def run_online(
        self, sumocfg: ArtifactRef, script: ArtifactRef, seed: int, out_dir: Path
    ) -> RunOutput: ...


class RunOutput(Protocol):
    ok: bool
    error: str | None
    artifacts: tuple[ArtifactRef, ...]
    wall_clock_s: float
