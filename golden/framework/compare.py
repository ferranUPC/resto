"""The comparator: expected phases against observed ones, with a diff that names the phase."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from golden.framework.expected import ExpectedPhase, ExpectedTrace
from golden.framework.observed import ObservedPhase
from golden.framework.outcome import (
    ExpectedAnswer,
    ExpectedKpi,
    ExpectedOutcome,
    ObservedAnswer,
    ObservedOutcome,
    Severity,
)
from resto.application.ports.tracing import TraceEvent
from resto.domain.entities.study import StudyResolution
from resto.domain.value_objects.answer_value import Quantity

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
    if (a := expected.answer) is not None:
        found += _answer(a, observed.answer)
    return Diff(tuple(found))


def _kpi_label(kpi: ExpectedKpi) -> str:
    where = f" on {kpi.network_id}/{kpi.edge_id}" if kpi.edge_id else ""
    return f"answer, {kpi.measure.value}{where}"


def _kpi(kpi: ExpectedKpi, answer: ObservedAnswer | None) -> Mismatch | None:
    want = f"{kpi.reference:g} {kpi.measure.unit} +-{kpi.tolerance:.0%}"
    given = [
        v.value
        for v in (answer.values if answer else ())
        if isinstance(v, Quantity)
        and (v.measure, v.edge_id, v.network_id) == (kpi.measure, kpi.edge_id, kpi.network_id)
    ]
    if not given:
        return Mismatch(None, _kpi_label(kpi), want, "not given", kpi.severity)
    if any(kpi.accepts(v) for v in given):
        return None
    return Mismatch(None, _kpi_label(kpi), want, f"{given[0]:g} {kpi.measure.unit}", kpi.severity)


def _answer(expected: ExpectedAnswer, observed: ObservedAnswer | None) -> list[Mismatch]:
    """The KPIs, `basis` and `forced_by_limit` the golden path sets. With no final answer
    (the study never got one) every set item is reported as missing."""
    found = [m for k in expected.kpis if (m := _kpi(k, observed)) is not None]
    for name in ("basis", "forced_by_limit"):
        wanted = getattr(expected, name)
        if wanted is None:
            continue
        got = getattr(observed, name) if observed is not None else None
        if wanted != got:
            found.append(
                Mismatch(None, f"answer, {name}", _show(wanted), _show(got), expected.severity)
            )
    return found
