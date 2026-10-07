"""The comparator: expected phases against observed ones, with a diff that names the phase."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from golden.framework.expected import ExpectedPhase, ExpectedTrace
from golden.framework.observed import ObservedPhase
from resto.domain.entities.study import StudyStatus

_ATTRIBUTES = ("arms", "reused", "basis", "forced_by_limit", "round")


@dataclass(frozen=True, slots=True)
class Mismatch:
    phase: int | None
    what: str
    expected: object
    observed: object

    def render(self) -> str:
        where = "study" if self.phase is None else f"phase {self.phase}"
        return f"{where}, {self.what}: expected {self.expected}, observed {self.observed}"


@dataclass(frozen=True, slots=True)
class Diff:
    mismatches: tuple[Mismatch, ...]

    @property
    def ok(self) -> bool:
        return not self.mismatches

    def render(self) -> str:
        return "\n".join(m.render() for m in self.mismatches) or "traces match"


def _show(value: object) -> object:
    return getattr(value, "value", value)


def _phase(k: int, expected: ExpectedPhase, observed: ObservedPhase) -> list[Mismatch]:
    found: list[Mismatch] = []
    want = tuple((s.tool, s.status.value) for s in expected.steps)
    got = tuple((tool, status.value) for tool, status in observed.steps)
    if want != got:
        found.append(Mismatch(k, "steps (tool, status)", want, got))
    for name in _ATTRIBUTES:
        wanted = getattr(expected, name)
        if wanted is not None and wanted != getattr(observed, name):
            found.append(Mismatch(k, name, _show(wanted), _show(getattr(observed, name))))
    return found


def compare(
    expected: ExpectedTrace,
    observed: Sequence[ObservedPhase],
    study_status: StudyStatus | None = None,
) -> Diff:
    found: list[Mismatch] = []
    if expected.status is not None and expected.status is not study_status:
        found.append(Mismatch(None, "status", _show(expected.status), _show(study_status)))
    for k, want in enumerate(expected.phases):
        if k >= len(observed):
            found.append(Mismatch(k, "phase", "present", "missing"))
        else:
            found += _phase(k, want, observed[k])
    for k in range(len(expected.phases), len(observed)):
        found.append(Mismatch(k, "phase", "absent", "extra"))
    return Diff(tuple(found))
