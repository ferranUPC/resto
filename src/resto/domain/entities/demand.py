from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.calibration_round import CalibrationRound
from resto.domain.value_objects.demand_source import DemandSource
from resto.domain.value_objects.demand_spec import DemandSpec
from resto.domain.value_objects.fidelity import Fidelity


@dataclass(frozen=True, slots=True)
class Demand:
    """Trips (the demand itself) plus routes computed for one network.
    `demand_id` is the content hash of the trips artifact.

    `description` says what traffic the demand stands for and `labels` are free short tags
    (ADR-0035). Both are content, not identity: they stay out of `demand_id`, so the same trips
    stored with another description are a conflict."""

    demand_id: str
    network_id: str
    spec: DemandSpec
    trips: ArtifactRef
    routes: ArtifactRef
    description: str
    labels: frozenset[str] = frozenset()
    sources: tuple[DemandSource, ...] = ()
    fidelity: Fidelity | None = None
    calibration_rounds: tuple[CalibrationRound, ...] = ()
    derived_from: str | None = None

    def __post_init__(self) -> None:
        if self.demand_id != self.trips.content_hash:
            raise ValueError("demand_id must equal the content hash of the trips artifact")
        if self.derived_from == self.demand_id:
            raise ValueError("a demand cannot derive from itself")
        if not self.description.strip():
            raise ValueError("a demand must say what traffic it stands for")
        if any(not label.strip() for label in self.labels):
            raise ValueError("labels must not be blank")

    @property
    def is_calibrated(self) -> bool:
        return self.fidelity is not None and self.fidelity.within_tolerance
