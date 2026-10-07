"""Output Composer promotion: an already-run `AgentRun[ReportDraft]` -> the `Report` (DoD §4.8;
ADR-0001, ADR-0025 §4).

Promotion order (ADR-0001):
  1. syntactic - the run stopped with a draft.
  2. semantic  - every claim carries evidence, and every ref resolves to evidence of the last
                 Expert answer. (The check of numbers against artifacts is E5.7 and goes here.)
  3. construct - `mode` and `basis` come from the last Expert round, and the fixed limitation line
                 is added when that round was forced by the limit; the prose is kept as written.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun
from resto.application.promotion import DraftRejected, require_draft
from resto.domain.entities.study import Study
from resto.domain.value_objects.drafts import ReportDraft
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.report import Claim, Report

FORCED_LIMITATION = (
    "The Expert reached the round limit and was forced to answer: this answer was not reached "
    "freely and is an extrapolation."
)
"""Added by code, never by the model, when the last round has `forced_by_limit` (ADR-0025 §4)."""


def compose_report(study: Study, run: AgentRun[ReportDraft]) -> Report:
    draft = require_draft(run, "composer")
    rounds = study.rounds
    if not rounds:
        raise ValueError("a report needs an Expert round to report on")
    last = rounds[-1]
    known = {e.ref for e in last.answer.evidence}
    for claim in draft.claims:
        if not claim.evidence_refs:
            raise DraftRejected(f"claim {claim.text!r} has no evidence")
        for ref in claim.evidence_refs:
            if ref not in known:
                raise DraftRejected(
                    f"claim {claim.text!r} cites {ref!r}, which is not evidence of the last "
                    "Expert answer"
                )
    forced = last.forced_by_limit or study.question.mode is Mode.FORCED
    return Report(
        summary=draft.summary,
        mode=Mode.FORCED if forced else Mode.FREE,
        basis=last.answer.basis,
        sections=draft.sections,
        claims=tuple(Claim(c.text, c.evidence_refs, c.value) for c in draft.claims),
        limitations=(FORCED_LIMITATION,) if last.forced_by_limit else (),
    )
