"""The `Setup` protocol: how a golden path is run."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from golden.framework.compare import Diff, Mismatch, compare_outcome
from golden.framework.expected import GoldenPath
from golden.framework.outcome import ObservedOutcome, observe_outcome
from golden.framework.simulations import NO_FACTS, Stored, observe_simulations
from resto.application.ports.tracing import TraceEvent
from resto.domain.entities.study import Study


@dataclass(frozen=True, slots=True)
class Run:
    """A finished study and the events its tracer saw."""

    study: Study
    events: Sequence[TraceEvent]
    stored: Stored = NO_FACTS


class Setup(Protocol):
    @property
    def repetitions(self) -> int:
        """How many times each golden path runs; every repetition must meet the expected outcome."""
        ...

    @property
    def compare_repetitions(self) -> bool:
        """Whether the repetitions must also equal each other. True only for a deterministic
        setup (the fake), where a difference exposes hidden nondeterminism; a real model varies
        between repetitions and is judged only against the expected outcome."""
        ...

    def run(self, path: GoldenPath) -> Run: ...


def _observed(run: Run) -> ObservedOutcome:
    return observe_outcome(run.study, observe_simulations(run.study, run.stored))


def _outcome_repetition_diffs(runs: Sequence[Run]) -> list[Mismatch]:
    """Every repetition against the first, on the observed outcome and not on raw events."""
    reference = _observed(runs[0])
    found: list[Mismatch] = []
    for i, run in enumerate(runs[1:], start=1):
        again = _observed(run)
        if again != reference:
            found.append(Mismatch(f"repetition {i} differs from repetition 0", reference, again))
    return found


def check(setup: Setup, path: GoldenPath) -> Diff:
    """Run `path` `setup.repetitions` times; every repetition must meet the expected outcome and
    equal the others when the setup asks for it (`compare_repetitions`)."""
    runs = [setup.run(path) for _ in range(setup.repetitions)]
    found: list[Mismatch] = []
    for i, run in enumerate(runs):
        diff = compare_outcome(path.expected, _observed(run))
        found += [replace(m, what=f"repetition {i}: {m.what}") for m in diff.mismatches]
    if setup.compare_repetitions:
        found += _outcome_repetition_diffs(runs)
    return Diff(tuple(found))
