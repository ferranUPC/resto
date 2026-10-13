from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExperimentRole(StrEnum):
    BASELINE = "baseline"
    TREATMENT = "treatment"
    COMPARISON = "comparison"


@dataclass(frozen=True, slots=True)
class Experiment:
    """One scenario and its seeded runs, inside a Study. `arm` is the question's arm it realises
    (ADR-0027); `reused` marks a scenario the Executor found by the hash of its request, with ok
    results, and so did not send to the Scenario Builder (ADR-0037 §5). `step_index` is the index
    in its phase's plan of the `build_scenario` step that built it: a run whose scenario comes from
    that step (`FromStep`) joins this experiment."""

    scenario_id: str
    arm: str
    role: ExperimentRole
    purpose: str
    step_index: int
    result_ids: tuple[str, ...] = ()
    reused: bool = False

    def __post_init__(self) -> None:
        if self.step_index < 0:
            raise ValueError("an experiment's step_index is a plan step index >= 0")
