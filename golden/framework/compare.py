"""The comparator: expected phases against observed ones, with a diff that names the phase."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from golden.framework.expected import ExpectedPhase, ExpectedTrace
from golden.framework.observed import ObservedPhase
from golden.framework.outcome import ExpectedOutcome, ObservedOutcome, Severity
from resto.application.ports.tracing import TraceEvent
from resto.domain.entities.study import StudyResolution

_ATTRIBUTES = ("arms", "reused", "basis", "forced_by_limit", "round")


@dataclass(frozen=True, slots=True)
class Mismatch:
    phase: int | None
    what: str
    expected: object
    observed: object
    severity: Severity = Severity.HARD

    def render(self) -> str:
        where = "study" if self.phase is None else f"phase {self.phase}"
        line = f"{where}, {self.what}: expected {self.expected}, observed {self.observed}"
        return line if self.severity is Severity.HARD else f"{self.severity.value}: {line}"


@dataclass(frozen=True, slots=True)
class Diff:
    mismatches: tuple[Mismatch, ...]

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def failures(self) -> tuple[Mismatch, ...]:
        return tuple(m for m in self.mismatches if m.severity is Severity.HARD)

    @property
    def warnings(self) -> tuple[Mismatch, ...]:
        return tuple(m for m in self.mismatches if m.severity is not Severity.HARD)

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
    resolution: StudyResolution | None = None,
    events: Sequence[TraceEvent] | None = None,
) -> Diff:
    """`events` is needed only when the expectation sets `allowed_events`."""
    found: list[Mismatch] = []
    if expected.allowed_events is not None:
        if events is None:
            raise ValueError("the expected trace sets allowed_events, so compare needs the events")
        extra = sorted(
            {type(e).__name__ for e in events if not isinstance(e, expected.allowed_events)}
        )
        if extra:
            allowed = sorted(t.__name__ for t in expected.allowed_events)
            found.append(Mismatch(None, "events", f"only {allowed}", f"also {extra}"))
    if expected.resolution is not None and expected.resolution is not resolution:
        found.append(Mismatch(None, "resolution", _show(expected.resolution), _show(resolution)))
    for k, want in enumerate(expected.phases):
        if k >= len(observed):
            found.append(Mismatch(k, "phase", "present", "missing"))
        else:
            found += _phase(k, want, observed[k])
    for k in range(len(expected.phases), len(observed)):
        found.append(Mismatch(k, "phase", "absent", "extra"))
    return Diff(tuple(found))


def compare_outcome(expected: ExpectedOutcome, observed: ObservedOutcome) -> Diff:
    """Each part the expectation sets is compared; a part left empty is not."""
    found: list[Mismatch] = []
    if (r := expected.resolution) is not None and r.resolution is not observed.resolution:
        found.append(
            Mismatch(
                None, "resolution", _show(r.resolution), _show(observed.resolution), r.severity
            )
        )
    if (n := expected.network) is not None and n.network_id != observed.network_id:
        found.append(Mismatch(None, "network", n.network_id, observed.network_id, n.severity))
    return Diff(tuple(found))
