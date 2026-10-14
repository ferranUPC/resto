"""The `Setup` protocol: how a golden path is run."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from golden.framework.compare import Diff, Mismatch, compare, compare_outcome
from golden.framework.expected import GoldenPath
from golden.framework.observed import observe
from golden.framework.outcome import ExpectedOutcome, observe_outcome
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
        """How many times each golden path runs; every repetition must meet the expected trace."""
        ...

    @property
    def compare_repetitions(self) -> bool:
        """Whether the repetitions must also equal each other. True only for a deterministic
        setup (the fake), where a difference exposes hidden nondeterminism; a real model varies
        between repetitions and is judged only against the expected trace."""
        ...

    def run(self, path: GoldenPath) -> Run: ...


def _repetition_diffs(runs: Sequence[Run]) -> list[Mismatch]:
    """Every repetition against the first: observed phases per phase, then the raw events, which
    expose a difference the compared attributes do not cover."""
    found: list[Mismatch] = []
    first = runs[0]
    reference = observe(first.study, first.events)
    for i, run in enumerate(runs[1:], start=1):
        again = observe(run.study, run.events)
        before = len(found)
        for k in range(max(len(reference), len(again))):
            a = reference[k] if k < len(reference) else None
            b = again[k] if k < len(again) else None
            if a != b:
                found.append(Mismatch(k, f"repetition {i} differs from repetition 0", a, b))
        if len(found) == before and list(run.events) != list(first.events):
            found.append(
                Mismatch(0, f"events of repetition {i} differ from repetition 0", "equal", "not")
            )
    return found


def _outcome_repetition_diffs(runs: Sequence[Run]) -> list[Mismatch]:
    """Every repetition against the first, on the observed outcome and not on raw events."""
    reference = observe_outcome(runs[0].study)
    found: list[Mismatch] = []
    for i, run in enumerate(runs[1:], start=1):
        again = observe_outcome(run.study)
        if again != reference:
            found.append(
                Mismatch(None, f"repetition {i} differs from repetition 0", reference, again)
            )
    return found


def check(setup: Setup, path: GoldenPath) -> Diff:
    """Run `path` `setup.repetitions` times; every repetition must meet the expected trace and
    equal the others when the setup asks for it (`compare_repetitions`)."""
    runs = [setup.run(path) for _ in range(setup.repetitions)]
    found: list[Mismatch] = []
    expected = path.expected
    for i, run in enumerate(runs):
        if isinstance(expected, ExpectedOutcome):
            diff = compare_outcome(expected, observe_outcome(run.study))
        else:
            diff = compare(
                expected, observe(run.study, run.events), run.study.resolution, run.events
            )
        found += [replace(m, what=f"repetition {i}: {m.what}") for m in diff.mismatches]
    if setup.compare_repetitions:
        if isinstance(expected, ExpectedOutcome):
            found += _outcome_repetition_diffs(runs)
        else:
            found += _repetition_diffs(runs)
    return Diff(tuple(found))
