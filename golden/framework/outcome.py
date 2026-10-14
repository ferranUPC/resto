"""The Expected outcome of a golden path (ADR-0043): what a correct study leaves, never the route.

Each part is optional; a part left empty is not compared. Every check carries its severity as data
(default hard), so turning a failure into a warning later changes a value, not the comparator.
Definitions hold plain values only, never agent output.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from resto.domain.entities.study import Study, StudyResolution
from resto.domain.value_objects.answer_value import AnswerValue, Measure
from resto.domain.value_objects.expert_answer import Basis

if TYPE_CHECKING:  # simulations.py imports Severity from here
    from golden.framework.simulations import ObservedSimulation, SimulationsExpectation


class Severity(StrEnum):
    """A hard mismatch fails the golden path; a warning is printed and changes nothing."""

    HARD = "hard"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ExpectedResolution:
    """How the study ends."""

    resolution: StudyResolution
    severity: Severity = Severity.HARD


@dataclass(frozen=True, slots=True)
class SameNetworkId:
    """The study used the network with this id (the first of `Study.network_ids`)."""

    network_id: str
    severity: Severity = Severity.HARD


# A union of small types; the topology variant arrives with E9.8 (ADR-0043 §4).
NetworkExpectation = SameNetworkId


@dataclass(frozen=True, slots=True)
class ExpectedKpi:
    """One value the Expert must give: a measure in its scope (network-wide, or an edge with its
    network, as `Quantity` requires), a `reference` from a solution by hand and a relative
    `tolerance`. A value passes when `|value - reference| <= tolerance * |reference|`."""

    measure: Measure
    reference: float
    tolerance: float
    edge_id: str | None = None
    network_id: str | None = None
    severity: Severity = Severity.HARD

    def __post_init__(self) -> None:
        if not math.isfinite(self.reference):
            raise ValueError("a KPI reference must be finite")
        if not math.isfinite(self.tolerance) or self.tolerance < 0:
            raise ValueError("a KPI tolerance must be a finite relative value >= 0")
        if self.measure.is_network_wide and (self.edge_id or self.network_id):
            raise ValueError(f"{self.measure} is network-wide: it names no edge or network")
        if not self.measure.is_network_wide and not (self.edge_id and self.network_id):
            raise ValueError(f"{self.measure} is per edge: name the edge and its network")

    def accepts(self, value: float) -> bool:
        limit = self.tolerance * abs(self.reference)
        return abs(value - self.reference) <= limit * (1 + 1e-9)


@dataclass(frozen=True, slots=True)
class ExpectedAnswer:
    """The final Expert answer: its KPIs, plus `basis` and `forced_by_limit` when the golden path
    fixes them (`None` is not compared)."""

    kpis: tuple[ExpectedKpi, ...] = ()
    basis: Basis | None = None
    forced_by_limit: bool | None = None
    severity: Severity = Severity.HARD


@dataclass(frozen=True, slots=True)
class ExpectedOutcome:
    resolution: ExpectedResolution | None = None
    network: NetworkExpectation | None = None
    simulations: SimulationsExpectation | None = None
    answer: ExpectedAnswer | None = None


@dataclass(frozen=True, slots=True)
class ObservedAnswer:
    """The typed values and flags of the last Expert round that did not abstain. Never the prose."""

    values: tuple[AnswerValue, ...]
    basis: Basis
    forced_by_limit: bool


@dataclass(frozen=True, slots=True)
class ObservedOutcome:
    """What a finished study left. No free text, no counts, no ids outside an expectation."""

    resolution: StudyResolution | None
    network_id: str | None
    simulations: tuple[ObservedSimulation, ...] = ()
    answer: ObservedAnswer | None = None


def _final_answer(study: Study) -> ObservedAnswer | None:
    for held in reversed(study.rounds):
        if not held.answer.needs_simulation:
            a = held.answer
            return ObservedAnswer(a.values, a.basis, held.forced_by_limit)
    return None


def observe_outcome(
    study: Study, simulations: tuple[ObservedSimulation, ...] = ()
) -> ObservedOutcome:
    network_id = study.network_ids[0] if study.network_ids else None
    return ObservedOutcome(study.resolution, network_id, simulations, _final_answer(study))
