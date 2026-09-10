from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BuildAndRunExperimentUseCase:
    """Coordinator use case: ExperimentRequest -> ExperimentPlan -> executed Report."""

    def execute(self) -> None:
        raise NotImplementedError
