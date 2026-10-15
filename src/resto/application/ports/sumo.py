"""SUMO-side ports: everything that shells out to netconvert / duarouter / sumo / TraCI."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.applied_action import AppliedAction
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.drafts import UnresolvedIssue
from resto.domain.value_objects.kpis import Kpis
from resto.domain.value_objects.network_source import GeneratedNetwork
from resto.domain.value_objects.topology_modification import TopologyModification
from resto.domain.value_objects.traci_script import TraciScript


class NetBuildError(RuntimeError):
    """`netconvert` or `netgenerate` could not build the network; the message is SUMO's own."""


class UnresolvableEdit(Exception):
    """A typed edit that cannot be applied (an edge or junction that does not exist, an id already
    taken). `issue` is what goes into `NetworkDraft.unresolved[]`: the edit is reported, never
    approximated (DoD §4.5)."""

    def __init__(self, issue: UnresolvedIssue) -> None:
        super().__init__(f"{issue.element_kind} {issue.element_id!r}: {issue.issue}")
        self.issue = issue


class NetconvertRunner(Protocol):
    """Builds `.net.xml` files. Each method raises `NetBuildError` when SUMO refuses."""

    def generate(self, source: GeneratedNetwork, out_dir: Path) -> ArtifactRef:
        """`netgenerate` for a grid, spider or random network (a random one uses its own seed)."""
        ...

    def build(
        self, osm: ArtifactRef | None, plain_dir: Path | None, options: Sequence[str], out_dir: Path
    ) -> ArtifactRef: ...
    def export_plain(self, net_xml: ArtifactRef, out_dir: Path) -> Path: ...


class PlainNetEditor(Protocol):
    """Applies one TopologyModification to the plain XML files in `plain_dir`.

    Raises `UnresolvableEdit` when the edit cannot be applied; the files are left untouched."""

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


class DemandScaler(Protocol):
    """Deterministic trip-count scaling for the `demand_scale` intervention (work-plan E2.3):
    no `randomTrips`/calibration involved, just a reproducible resample of an existing trips
    file. Routing the result is `DemandTools.duarouter`'s job, not this port's."""

    def scale(self, trips: ArtifactRef, factor: float, out_dir: Path) -> ArtifactRef: ...


@dataclass(frozen=True, slots=True)
class RunOutput:
    """What one `sumo` execution left behind (ADR-0017). `artifacts` always includes the run cfg
    SUMO was started with (kind `sumocfg`); on success it also holds `edgedata`, `tripinfo`,
    `summary` and `statistics`, and `kpis` is read from the latter. `error` is SUMO's own
    message. An online run also lists `script.py` (kind `script`) among its artifacts and returns
    the actions its script applied."""

    ok: bool
    error: str | None
    artifacts: tuple[ArtifactRef, ...]
    wall_clock_s: float
    kpis: Kpis | None = None
    applied_actions: tuple[AppliedAction, ...] = ()

    def __post_init__(self) -> None:
        if self.ok and self.kpis is None:
            raise ValueError("a successful run must carry KPIs")
        if not self.ok and not self.error:
            raise ValueError("a failed run must carry the SUMO error message")


@dataclass(frozen=True, slots=True)
class DryRunOutcome:
    """What rehearsing a script against SUMO gave: ok, or SUMO's error (or the Python traceback)."""

    ok: bool
    error: str | None

    def __post_init__(self) -> None:
        if not self.ok and not self.error:
            raise ValueError("a failed dry run must carry the error message")


class SumoRunner(Protocol):
    def sumo_version(self) -> str:
        """The SUMO version this runner runs, known before a run because the result id hashes it."""
        ...

    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput: ...
    def run_online(
        self, sumocfg: ArtifactRef, script: TraciScript, seed: int, out_dir: Path
    ) -> RunOutput: ...
    def dry_run(self, sumocfg: ArtifactRef, script: TraciScript, out_dir: Path) -> DryRunOutcome:
        """Rehearses `script` on `sumocfg` (seed 0): 50 steps of the real script, then every
        condition evaluated once and every action applied once. Stores nothing; `out_dir` is
        scratch space."""
        ...
