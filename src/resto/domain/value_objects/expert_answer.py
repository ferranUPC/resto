from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from resto.domain.value_objects.answer_value import AnswerValue
from resto.domain.value_objects.question import Question


class Basis(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    EXTRAPOLATED = "extrapolated"


class EvidenceKind(StrEnum):
    ARTIFACT = "artifact"
    QUERY = "query"


@dataclass(frozen=True, slots=True)
class Evidence:
    kind: EvidenceKind
    ref: str
    excerpt: str = ""

    def __post_init__(self) -> None:
        if not self.ref:
            raise ValueError("Evidence requires a resolvable ref")


@dataclass(frozen=True, slots=True)
class ExpertAnswer:
    """`values` is the answer itself, typed; `answer` is the prose justification. When they
    disagree, `values` is authoritative (ADR-0019)."""

    answer: str
    basis: Basis
    confidence: float
    evidence: tuple[Evidence, ...] = ()
    values: tuple[AnswerValue, ...] = ()
    needs_simulation: bool = False
    proposed_experiment: Question | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        if self.needs_simulation and self.proposed_experiment is None:
            raise ValueError("needs_simulation requires a proposed_experiment")
        if not self.needs_simulation and not self.evidence:
            raise ValueError("an answer must carry evidence unless it abstains")
        if not self.needs_simulation and not self.values:
            raise ValueError("an answer must carry at least one typed value unless it abstains")
