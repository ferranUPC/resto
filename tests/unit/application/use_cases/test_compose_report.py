"""`compose_report` promotion (E5.4; ADR-0001, ADR-0025 §4): the Composer's draft carries only prose
and claims; code adds mode, basis and the limitation line from the last Expert round, and rejects a
claim whose refs do not resolve to evidence of the last answer."""

from __future__ import annotations

import pytest

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.promotion import DraftRejected, RunWithoutDraft
from resto.application.use_cases.compose_report import FORCED_LIMITATION, compose_report
from resto.domain.value_objects.drafts import ClaimDraft, ReportDraft
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.report import ReportSection
from resto.domain.value_objects.step_record import Usage
from tests.unit.domain._fixtures import study_with_rounds


def _draft(*refs: str) -> ReportDraft:
    return ReportDraft(
        summary="E12 is the bottleneck",
        sections=(ReportSection("Method", "one baseline"),),
        claims=(ClaimDraft(text="delay +12 %", evidence_refs=refs or ("q1",), value="12%"),),
    )


def _run(draft: ReportDraft | None, stop: StopReason = StopReason.OUTPUT) -> AgentRun[ReportDraft]:
    return AgentRun(output=draft, tool_calls=(), usage=Usage(), stop_reason=stop)


def test_a_valid_draft_keeps_its_prose_and_claims() -> None:
    draft = _draft("q1", "/runs/r1/edgedata.xml")
    report = compose_report(study_with_rounds(), _run(draft))
    assert report.summary == draft.summary
    assert report.sections == draft.sections
    assert [(c.text, c.evidence_refs, c.value) for c in report.claims] == [
        ("delay +12 %", ("q1", "/runs/r1/edgedata.xml"), "12%")
    ]


@pytest.mark.parametrize("basis", list(Basis))
def test_basis_comes_from_the_last_round(basis: Basis) -> None:
    assert compose_report(study_with_rounds(basis=basis), _run(_draft())).basis is basis


def test_mode_comes_from_the_last_round() -> None:
    free = compose_report(study_with_rounds(), _run(_draft()))
    forced = compose_report(
        study_with_rounds(question=Question("q", Intent.DESCRIBE, Mode.FORCED)), _run(_draft())
    )
    assert (free.mode, forced.mode) == (Mode.FREE, Mode.FORCED)


def test_the_limitation_line_appears_if_and_only_if_the_last_round_was_forced_by_the_limit() -> (
    None
):
    assert compose_report(study_with_rounds(), _run(_draft())).limitations == ()
    forced = compose_report(study_with_rounds(3, last_forced=True), _run(_draft()))
    assert forced.limitations == (FORCED_LIMITATION,)
    assert forced.mode is Mode.FORCED


def test_the_limitation_states_only_the_round_limit_not_the_basis() -> None:
    assert "round limit" in FORCED_LIMITATION
    assert "extrapolat" not in FORCED_LIMITATION
    observed = compose_report(
        study_with_rounds(3, last_forced=True, basis=Basis.OBSERVED), _run(_draft())
    )
    assert (observed.basis, observed.limitations) == (Basis.OBSERVED, (FORCED_LIMITATION,))


def test_a_forced_question_is_forced_without_the_limitation_line() -> None:
    report = compose_report(
        study_with_rounds(question=Question("q", Intent.DESCRIBE, Mode.FORCED)), _run(_draft())
    )
    assert (report.mode, report.limitations) == (Mode.FORCED, ())


def test_a_claim_without_evidence_is_rejected() -> None:
    bad = ReportDraft(summary="s", claims=(ClaimDraft(text="t", evidence_refs=()),))
    with pytest.raises(DraftRejected, match="evidence"):
        compose_report(study_with_rounds(), _run(bad))


def test_a_ref_that_is_not_evidence_of_the_last_answer_is_rejected() -> None:
    with pytest.raises(DraftRejected, match="q9"):
        compose_report(study_with_rounds(), _run(_draft("q1", "q9")))


def test_a_run_without_a_draft_is_refused() -> None:
    with pytest.raises(RunWithoutDraft):
        compose_report(study_with_rounds(), _run(None, StopReason.BUDGET))
