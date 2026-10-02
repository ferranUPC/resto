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
    results, and so did not send to the Scenario Builder (ADR-0037 §5)."""

    scenario_id: str
    arm: str
    role: ExperimentRole
    purpose: str
    result_ids: tuple[str, ...] = ()
    reused: bool = False
