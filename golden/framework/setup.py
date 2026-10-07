"""The `Setup` protocol: how a golden path is run."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from golden.framework.expected import GoldenPath
from resto.application.ports.tracing import TraceEvent
from resto.domain.entities.study import Study


@dataclass(frozen=True, slots=True)
class Run:
    """A finished study and the events its tracer saw."""

    study: Study
    events: Sequence[TraceEvent]


class Setup(Protocol):
    @property
    def repetitions(self) -> int:
        """How many times each golden path runs; the traces of the repetitions must be equal."""
        ...

    def run(self, path: GoldenPath) -> Run: ...
