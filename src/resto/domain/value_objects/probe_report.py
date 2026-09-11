from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.artifact_ref import ArtifactRef


@dataclass(frozen=True, slots=True)
class ProbeReport:
    """Outcome of the Network Author's `probe_run`: light random demand on the network."""

    teleports: int
    collisions: int
    not_arrived: int
    hot_edges: tuple[str, ...]
    evidence: ArtifactRef

    def __post_init__(self) -> None:
        if min(self.teleports, self.collisions, self.not_arrived) < 0:
            raise ValueError("probe counters must be >= 0")
