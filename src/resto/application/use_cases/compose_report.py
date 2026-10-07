"""Output Composer promotion: an already-run `AgentRun[ReportDraft]` -> the `Report` (DoD §4.8;
ADR-0001, ADR-0025 §4).

Promotion order (ADR-0001):
  1. syntactic - the run stopped with a draft.
  2. semantic  - every claim carries evidence, and every ref resolves to evidence of the last
                 Expert answer. (The check of numbers against artifacts is E5.7 and goes here.)
  3. construct - `basis` comes from the last Expert round; `mode` is forced when that round was
                 forced by the limit or the question itself asked for forced mode; the fixed
                 limitation line is added only when the limit forced the round; the prose is kept
                 as written.
"""

from __future__ import annotations

from resto.application.ports.llm import AgentRun
from resto.application.promotion import DraftRejected, require_draft
from resto.domain.entities.study import Study
from resto.domain.value_objects.drafts import ReportDraft
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.report import Claim, Report

FORCED_LIMITATION = (
    "The study reached the round limit, so the Expert answered without being able to request "
    "another simulation."
)
"""Added by code, never by the model, when the last round has `forced_by_limit` (ADR-0025 §4)."""


def compose_report(study: Study, run: AgentRun[ReportDraft]) -> Report:
    """Promotes the Composer's draft to the `Report` of `study`.

    `mode` is `Mode.FORCED` when the last round was forced by the round limit or the question
    itself asked for forced mode: either way the Expert could not request another simulation. It
    says nothing about `basis` (observed, inferred or extrapolated), which comes from the last
    answer's data coverage. Only the limit adds `FORCED_LIMITATION`.

    Raises:
        DraftRejected: a claim has no evidence, or cites a ref the last answer does not hold.
        ValueError: the study has no Expert round.
    """
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
