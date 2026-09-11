from __future__ import annotations

from dataclasses import dataclass

from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.question import Mode


@dataclass(frozen=True, slots=True)
class Claim:
    text: str
    evidence_refs: tuple[str, ...]
    value: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_refs:
            raise ValueError("every claim must reference evidence")


@dataclass(frozen=True, slots=True)
class ReportSection:
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class Report:
    summary: str
    mode: Mode
    basis: Basis
    sections: tuple[ReportSection, ...] = ()
    claims: tuple[Claim, ...] = ()
    limitations: tuple[str, ...] = ()
