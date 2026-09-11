from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExperimentRole(StrEnum):
    BASELINE = "baseline"
    TREATMENT = "treatment"
    COMPARISON = "comparison"


@dataclass(frozen=True, slots=True)
class Experiment:
    """One scenario and its seeded runs, inside a Study."""

    scenario_id: str
    role: ExperimentRole
    purpose: str
    result_ids: tuple[str, ...] = ()
