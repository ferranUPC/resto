"""The comparator: an Expected outcome against what the run left, with a diff naming the part."""

from __future__ import annotations

from dataclasses import dataclass

from golden.framework.outcome import (
    ExpectedAnswer,
    ExpectedKpi,
    ExpectedOutcome,
    ObservedAnswer,
    ObservedOutcome,
    Severity,
)
from golden.framework.simulations import compare_simulations
from resto.domain.value_objects.answer_value import Quantity


@dataclass(frozen=True, slots=True)
class Mismatch:
    what: str
    expected: object
    observed: object
    severity: Severity = Severity.HARD

    def render(self) -> str:
        line = f"{self.what}: expected {self.expected}, observed {self.observed}"
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
        return "\n".join(m.render() for m in self.mismatches) or "outcomes match"


def _show(value: object) -> object:
    return getattr(value, "value", value)


def compare_outcome(expected: ExpectedOutcome, observed: ObservedOutcome) -> Diff:
    """Each part the expectation sets is compared; a part left empty is not."""
    found: list[Mismatch] = []
    if (r := expected.resolution) is not None and r.resolution is not observed.resolution:
        found.append(
            Mismatch("resolution", _show(r.resolution), _show(observed.resolution), r.severity)
        )
    if (n := expected.network) is not None and n.network_id != observed.network_id:
        found.append(Mismatch("network", n.network_id, observed.network_id, n.severity))
    if (s := expected.simulations) is not None:
        found += [
            Mismatch(what, want, got, s.severity)
            for what, want, got in compare_simulations(s, observed.simulations)
        ]
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
        return Mismatch(_kpi_label(kpi), want, "not given", kpi.severity)
    if any(kpi.accepts(v) for v in given):
        return None
    return Mismatch(_kpi_label(kpi), want, f"{given[0]:g} {kpi.measure.unit}", kpi.severity)


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
            found.append(Mismatch(f"answer, {name}", _show(wanted), _show(got), expected.severity))
    return found
