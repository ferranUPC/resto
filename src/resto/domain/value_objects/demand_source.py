from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from resto.domain.value_objects.artifact_ref import ArtifactRef


@dataclass(frozen=True, slots=True)
class ParametersSource:
    kind: Literal["parameters"] = "parameters"


@dataclass(frozen=True, slots=True)
class HistoricalDbSource:
    query: Mapping[str, Any] = field(default_factory=dict)
    kind: Literal["historical_db"] = "historical_db"


@dataclass(frozen=True, slots=True)
class ExternalDatasetSource:
    """Data the Demand Generator found outside, frozen as an artifact so the demand is
    reproducible even if the URL changes."""

    url: str
    snapshot: ArtifactRef
    transformation: str
    kind: Literal["external_dataset"] = "external_dataset"

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("an ExternalDatasetSource requires a url")


DemandSource = ParametersSource | HistoricalDbSource | ExternalDatasetSource
