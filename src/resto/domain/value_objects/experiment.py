from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExperimentRole(StrEnum):
    BASELINE = "baseline"
    TREATMENT = "treatment"
    COMPARISON = "comparison"


@dataclass(frozen=True, slots=True)
class Experiment:
    """One scenario and its seeded runs, inside a Study. `reused` marks a scenario whose stored
    results the plan reused instead of running it now (ADR-0025 §1)."""

    scenario_id: str
    role: ExperimentRole
    purpose: str
    result_ids: tuple[str, ...] = ()
    reused: bool = False
