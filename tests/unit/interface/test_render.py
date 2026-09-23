"""Deterministic rendering of failed and awaiting_user studies (E5.11, ADR-0025 §3): three blocks,
the failing step named, what the user can do by `StepError.kind`, ambiguities or candidates."""

from __future__ import annotations

import pytest

from resto.domain.entities.study import Phase, Study, StudyStatus
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.step_record import (
    StepError,
    StepErrorKind,
    StepRecord,
    StepStatus,
)
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    ClarificationRequest,
    FromStep,
    ReusedExperiment,
    RunSimulationStep,
    StudyPlan,
)
from resto.interface.render import WHAT_TO_DO, render_study
from tests.unit.domain._samples import study as completed_study

QUESTION = Question(text="what if we close lane 1 of E12?", intent=Intent.RUN)
PLAN = StudyPlan(
    network_id="abc123",
    rationale="baseline stored, treatment to build",
    steps=(
        BuildScenarioStep("abc123", "t1", "treatment", ExperimentRole.TREATMENT, "closure"),
        RunSimulationStep(FromStep(0), depends_on=(0,)),
    ),
    reused=(ReusedExperiment("s-base", "base", ExperimentRole.BASELINE, "stored baseline"),),
)


def failed(kind: StepErrorKind, *details: str) -> Study:
    return Study(
        study_id="st-9",
        status=StudyStatus.FAILED,
        phases=(
            Phase(
                question=QUESTION,
                plan=PLAN,
                steps=(
                    StepRecord("plan", StepStatus.OK),
                    StepRecord(
                        "build_scenario",
                        StepStatus.FAILED,
                        error=StepError(kind, "the step failed", details),
                    ),
                    StepRecord("run_simulation", StepStatus.SKIPPED),
                ),
                experiments=(
                    Experiment(
                        "s-base", "base", ExperimentRole.BASELINE, "stored", ("r1", "r2"), True
                    ),
                ),
            ),
        ),
    )


@pytest.mark.parametrize("kind", list(StepErrorKind))
def test_a_failed_study_names_the_step_and_what_the_user_can_do(kind: StepErrorKind) -> None:
    text = render_study(failed(kind, "unknown lane 'E99_0'"))

    blocks = ("## What happened", "## What was done", "## What you can do")
    assert [text.index(b) for b in blocks] == sorted(text.index(b) for b in blocks)
    assert f"Step `build_scenario` of phase 0 (the question as asked) failed ({kind})" in text
    assert "- unknown lane 'E99_0'" in text
    assert text.rstrip().endswith(WHAT_TO_DO[kind])


def test_what_was_done_lists_reused_experiments_and_ok_steps() -> None:
    text = render_study(failed(StepErrorKind.USER_INPUT))

    assert "- `plan` ok" in text
    assert "experiment `base` (baseline, reused): scenario s-base, 2 result(s)" in text
    assert "A rerun of the same request reuses everything listed here." in text
    assert "run_simulation" not in text  # skipped steps were not done


def test_every_failure_kind_has_advice() -> None:
    assert set(WHAT_TO_DO) == set(StepErrorKind)


def test_an_ambiguous_question_lists_its_ambiguities() -> None:
    study = Study(
        study_id="st-a",
        status=StudyStatus.AWAITING_USER,
        phases=(Phase(question=Question("close it", Intent.RUN, ambiguities=("which edge?",))),),
    )

    text = render_study(study)

    assert "The question is ambiguous:\n- which edge?" in text
    assert "## What you can do" in text


def test_a_coordinator_clarification_lists_the_candidates() -> None:
    clarification = ClarificationRequest("two networks are labelled Gran Via", ("gv-1", "gv-2"))
    study = Study(
        study_id="st-c",
        status=StudyStatus.AWAITING_USER,
        phases=(Phase(question=QUESTION, clarification=clarification),),
    )

    text = render_study(study)

    assert "two networks are labelled Gran Via" in text
    assert "Candidates:\n- gv-1\n- gv-2" in text


def test_a_completed_study_is_not_rendered_here() -> None:
    with pytest.raises(ValueError):
        render_study(completed_study())
