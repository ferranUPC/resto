from typing import Any

import pytest

from resto.domain.entities.study import Study, StudyStatus
from resto.domain.value_objects.answer_value import Edges
from resto.domain.value_objects.expert_answer import Basis, Evidence, EvidenceKind, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.study_plan import PlanStep, StudyPlan

PLAN = StudyPlan(steps=(PlanStep(module="expert"),), rationale="results exist")
EVIDENCE = (Evidence(kind=EvidenceKind.QUERY, ref="query_edgedata(r1,E12)"),)


def _question(**kw):  # noqa: ANN003, ANN202
    base: dict[str, Any] = dict(text="what happens at peak?", intent=Intent.DESCRIBE)
    base.update(kw)
    return Question(**base)


def test_steps_require_a_plan() -> None:
    with pytest.raises(ValueError):
        Study(
            study_id="s",
            question=_question(),
            steps=(StepRecord(tool="ask_expert", status=StepStatus.OK),),
        )


def test_ambiguous_question_waits_for_the_user() -> None:
    q = _question(ambiguities=("which network?",))
    with pytest.raises(ValueError):
        Study(study_id="s", question=q, status=StudyStatus.RUNNING)
    Study(study_id="s", question=q, status=StudyStatus.AWAITING_USER)


def test_forced_mode_never_triggers_experiments() -> None:
    abstain = ExpertAnswer(
        answer="need a run",
        basis=Basis.EXTRAPOLATED,
        confidence=0.3,
        needs_simulation=True,
        proposed_experiment=_question(intent=Intent.COUNTERFACTUAL),
    )
    with pytest.raises(ValueError):
        Study(
            study_id="s",
            question=_question(mode=Mode.FORCED),
            plan=PLAN,
            rounds=(ExpertRound(question="q", answer=abstain, triggered_experiments=(0,)),),
        )


def test_max_rounds_is_enforced() -> None:
    answer = ExpertAnswer(
        answer="E12",
        basis=Basis.OBSERVED,
        confidence=0.9,
        evidence=EVIDENCE,
        values=(Edges(edge_ids=("E12",)),),
    )
    rounds = tuple(ExpertRound(question="q", answer=answer) for _ in range(4))
    with pytest.raises(ValueError):
        Study(study_id="s", question=_question(), plan=PLAN, rounds=rounds)
    study = Study(study_id="s", question=_question(), plan=PLAN, rounds=rounds[:2])
    assert study.rounds_left == 1


def test_answer_without_evidence_must_abstain() -> None:
    with pytest.raises(ValueError, match="evidence"):
        ExpertAnswer(
            answer="E12 is congested",
            basis=Basis.OBSERVED,
            confidence=0.9,
            values=(Edges(edge_ids=("E12",)),),
        )


def test_answer_without_typed_values_must_abstain() -> None:
    with pytest.raises(ValueError, match="typed value"):
        ExpertAnswer(
            answer="E12 is congested", basis=Basis.OBSERVED, confidence=0.9, evidence=EVIDENCE
        )
