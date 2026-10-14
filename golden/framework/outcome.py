"""The Expected outcome of a golden path (ADR-0043): what a correct study leaves, never the route.

Each part is optional; a part left empty is not compared. Every check carries its severity as data
(default hard), so turning a failure into a warning later changes a value, not the comparator.
Definitions hold plain values only, never agent output.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.entities.study import Study, StudyResolution


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
class ExpectedOutcome:
    resolution: ExpectedResolution | None = None
    network: NetworkExpectation | None = None


@dataclass(frozen=True, slots=True)
class ObservedOutcome:
    """What a finished study left. No free text, no counts, no ids outside an expectation."""

    resolution: StudyResolution | None
    network_id: str | None


def observe_outcome(study: Study) -> ObservedOutcome:
    return ObservedOutcome(study.resolution, study.network_ids[0] if study.network_ids else None)
