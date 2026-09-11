from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PlanStep:
    module: str
    inputs: Mapping[str, Any] = field(default_factory=dict)
    expected_artifacts: tuple[str, ...] = ()
    depends_on: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class StudyPlan:
    """Emitted by the Coordinator before its first tool call; measured against gold plans."""

    steps: tuple[PlanStep, ...]
    rationale: str
    reuse_decisions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("a StudyPlan requires at least one step")
        for i, step in enumerate(self.steps):
            if any(d >= i for d in step.depends_on):
                raise ValueError(f"step {i} depends on a step that is not earlier")
