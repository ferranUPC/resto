from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.artifact_ref import ArtifactRef


@dataclass(frozen=True, slots=True)
class EdgeFidelity:
    edge_id: str
    target: float
    achieved: float

    @property
    def relative_error(self) -> float:
        if self.target == 0:
            return 0.0 if self.achieved == 0 else float("inf")
        return abs(self.achieved - self.target) / self.target


@dataclass(frozen=True, slots=True)
class Fidelity:
    """Target vs achieved counts at the control edges, backed by the edgedata of the last
    calibration run."""

    per_edge: tuple[EdgeFidelity, ...]
    tolerance: float
    evidence: ArtifactRef

    def __post_init__(self) -> None:
        if not self.per_edge:
            raise ValueError("Fidelity requires at least one control edge")
        if not 0 < self.tolerance < 1:
            raise ValueError("tolerance must be a fraction in (0, 1)")

    @property
    def max_relative_error(self) -> float:
        return max(e.relative_error for e in self.per_edge)

    @property
    def within_tolerance(self) -> bool:
        return self.max_relative_error <= self.tolerance
