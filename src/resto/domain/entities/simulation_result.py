from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.constants import SUMO_VERSION
from resto.domain.value_objects.applied_action import AppliedAction
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.kpis import Kpis


class RunMode(StrEnum):
    BATCH = "batch"
    ONLINE = "online"


class RunStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """One seeded execution of a Scenario. `result_id` = hash(scenario_id, seed, mode,
    sumo_version); `content_hash` covers the produced artifacts (reproducibility check)."""

    result_id: str
    scenario_id: str
    seed: int
    mode: RunMode
    status: RunStatus
    content_hash: str
    artifacts: tuple[ArtifactRef, ...] = ()
    kpis: Kpis | None = None
    applied_actions: tuple[AppliedAction, ...] = ()
    error: str | None = None
    wall_clock_s: float | None = None
    sumo_version: str = SUMO_VERSION

    def __post_init__(self) -> None:
        if self.sumo_version != SUMO_VERSION:
            raise ValueError(f"results must come from SUMO {SUMO_VERSION}")
        if self.status is RunStatus.FAILED and not self.error:
            raise ValueError("a failed run must carry the SUMO error message")
        if self.status is RunStatus.OK and self.kpis is None:
            raise ValueError("a successful run must carry KPIs")
        if self.mode is RunMode.BATCH and self.applied_actions:
            raise ValueError("batch runs cannot apply actions")
