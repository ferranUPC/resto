from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from resto.domain.entities.traci_plan import TraciPlan
from resto.domain.value_objects.intervention import Intervention, Strategy


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    network_id: str
    demand_id: str
    sumocfg_path: Path
    additional_files: tuple[Path, ...]
    interventions: tuple[Intervention, ...]
    context_tags: frozenset[str]
    seed: int
    content_hash: str
    traci_plan: TraciPlan | None = None

    def __post_init__(self) -> None:
        has_dynamic = any(i.strategy is Strategy.DYNAMIC for i in self.interventions)
        if has_dynamic and self.traci_plan is None:
            raise ValueError("dynamic interventions require a traci_plan")
