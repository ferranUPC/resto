"""Deterministic rendering of failed and awaiting_user studies (E5.11, ADR-0025 §3): three blocks,
the failing step named, what the user can do by `StepError.kind`, ambiguities or candidates."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from resto.domain.entities.study import Phase, Study, StudyStatus
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.report import Claim, ReportSection
from resto.domain.value_objects.step_record import (
    StepError,
    StepErrorKind,
    StepRecord,
    StepStatus,
)
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    FromStep,
    ObtainNetworkStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.interface.render import WHAT_TO_DO, render_study, render_study_text
from tests.unit.domain._fixtures import study_with_rounds
from tests.unit.domain._samples import study as completed_study

FORCED_LIMITATION = "The Expert was forced to answer at the round limit."
QUESTION = Question(text="what if we close lane 1 of E12?", intent=Intent.RUN)
PLAN = StudyPlan(
    network_id=FromStep(0),
    rationale="treatment to build",
    steps=(
        ObtainNetworkStep("RIVERSIDE"),
        BuildScenarioStep(
            FromStep(0), "t1", "treatment", ExperimentRole.TREATMENT, "closure", depends_on=(0,)
        ),
        RunSimulationStep(FromStep(1), depends_on=(1,)),
    ),
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


def _completed(*, forced: bool = False, run_now: bool = True, two_phases: bool = True) -> Study:
    """A completed study; with `two_phases` the Expert first asked for a simulation."""
    reused = not run_now
    base = completed_study()
    assert base.report is not None
    first = tuple(replace(e, reused=e.reused or reused) for e in base.phases[0].experiments)
    extra = Experiment("s2", "extra", ExperimentRole.TREATMENT, "second look", ("res2",), reused)
    report = replace(
        base.report,
        limitations=("single seed", FORCED_LIMITATION) if forced else ("single seed",),
        claims=(Claim("delay +12 %", ("query_edgedata:r1", "ghost"), "12%"),),
    )
    return study_with_rounds(
        2 if two_phases else 1,
        last_forced=forced,
        question=base.question,
        answer=base.rounds[-1].answer,
        experiments=(first, (extra,)) if two_phases else (first,),
        report=report,
        study_id=base.study_id,
    )


def _with_report(**changes: Any) -> Study:
    study = _completed()
    assert study.report is not None
    return replace(study, report=replace(study.report, **changes))


def test_a_completed_study_renders_its_report_in_a_fixed_layout() -> None:
    text = render_study(_completed())

    headings = (
        "# Study st-1",
        "## Summary",
        "## Method",
        "## Claims",
        "## Evidence",
        "## Experiments",
        "## Mode and basis",
        "## Limitations",
    )
    positions = [text.index(h) for h in headings]
    assert positions == sorted(positions)
    assert "> what if we close lane 1 of E12 at peak?" in text
    assert "closing the lane shifts delay to the parallel corridor" in text
    assert "one baseline, one treatment" in text
    assert "- delay +12 % (value: 12%; evidence: `query_edgedata:r1`, `ghost`)" in text
    assert "free" in text.split("## Mode and basis")[1] and "observed" in text
    assert "- single seed" in text


def test_the_evidence_table_has_fixed_columns_and_resolves_each_ref() -> None:
    text = render_study(_completed())

    table = text.split("## Evidence")[1].split("## Experiments")[0]
    assert "| Ref | Kind | Description |" in table
    assert "| `query_edgedata:r1` | query | E12 0.91 |" in table
    assert "| `ghost` | unresolved | - |" in table


def test_the_evidence_table_keeps_its_columns_without_claims() -> None:
    study = _completed()
    assert study.report is not None
    bare = replace(study, report=replace(study.report, claims=()))

    assert "| Ref | Kind | Description |" in render_study(bare)


def test_the_experiments_table_lists_every_phase_and_tells_reused_from_run_now() -> None:
    text = render_study(_completed())

    table = text.split("## Experiments")[1].split("## Mode and basis")[0]
    assert "| Phase | Arm | Role | Scenario | Results | Origin |" in table
    assert "| 0 | base | baseline | s0 | 1 | reused |" in table
    assert "| 0 | treatment | treatment | s1 | 1 | run now |" in table
    assert "| 1 | extra | treatment | s2 | 1 | run now |" in table


def test_a_study_answered_from_stored_results_renders() -> None:
    study = _completed(run_now=False, two_phases=False)

    text = render_study(study)

    assert "run now" not in text.split("## Experiments")[1].split("## Mode")[0]
    assert text.count("reused") >= 2


def test_the_forced_by_limit_line_is_in_the_limitations() -> None:
    text = render_study(_completed(forced=True))

    assert f"- {FORCED_LIMITATION}" in text.split("## Limitations")[1]


def test_a_report_without_limitations_says_so() -> None:
    study = _completed()
    assert study.report is not None

    text = render_study(replace(study, report=replace(study.report, limitations=())))

    assert "None stated." in text.split("## Limitations")[1]


def test_a_claim_without_a_value_shows_only_its_evidence() -> None:
    study = _with_report(claims=(Claim("delay up", ("query_edgedata:r1",)),))

    assert "- delay up (evidence: `query_edgedata:r1`)" in render_study(study)


def test_headings_in_the_models_prose_sit_below_the_fixed_ones() -> None:
    study = _with_report(
        summary="# Evidence\nit grew",
        sections=(ReportSection("Method", "## Limitations\ntext\n```\n# kept\n```\n#tag"),),
    )

    text = render_study(study)

    assert "#### Evidence\nit grew" in text
    assert "##### Limitations\ntext" in text
    assert "```\n# kept\n```\n#tag" in text
    assert text.count("\n## Limitations\n") == 1
    assert text.count("\n## Evidence\n") == 1


def test_a_section_title_cannot_duplicate_a_fixed_heading_or_span_lines() -> None:
    study = _with_report(
        sections=(
            ReportSection("Evidence", "a"),
            ReportSection("Two\n## Claims", "b"),
            ReportSection("  ", "c"),
        )
    )

    text = render_study(study)

    assert "## Evidence (from the Composer)" in text
    assert "## Two ## Claims" in text
    assert "## Untitled section" in text
    assert text.count("\n## Evidence\n") == 1
    assert text.count("\n## Claims\n") == 1


def test_claim_text_keeps_to_one_line_and_does_not_break_the_tables() -> None:
    study = _with_report(
        claims=(Claim("delay\n## Evidence\n| x |", ("query_edgedata:r1",), "12\n%"),),
        limitations=("one\ntwo",),
    )

    text = render_study(study)

    assert "- delay ## Evidence \\| x \\| (value: 12 %; evidence: `query_edgedata:r1`)" in text
    assert "- one two" in text
    assert text.count("\n## Evidence\n") == 1


def test_experiment_cells_escape_pipes_and_newlines() -> None:
    study = _completed()
    phase = study.phases[0]
    odd = replace(phase.experiments[0], arm="a|b\nc", scenario_id="s|0")
    study = replace(study, phases=(replace(phase, experiments=(odd,)), *study.phases[1:]))

    assert "| 0 | a\\|b c | baseline | s\\|0 | 1 | reused |" in render_study(study)


# --- plain text (E5.4/06) ---

_FORBIDDEN = ("#", "|", "`")


def _long_ids(study: Study, base: str, treat: str) -> Study:
    """`study` with scenario ids of the given values on the first phase's two experiments."""
    phase = study.phases[0]
    a, b = phase.experiments
    experiments = (replace(a, scenario_id=base), replace(b, scenario_id=treat))
    return replace(study, phases=(replace(phase, experiments=experiments), *study.phases[1:]))


def _plain(study: Study) -> str:
    """A completed study with the model's prose reduced to words, so the whole text is checkable
    for Markdown syntax."""
    assert study.report is not None
    report = replace(
        study.report,
        summary="Delay grows.",
        sections=(ReportSection("Method", "One baseline, one treatment."),),
        claims=(Claim("delay +12 %", ("query_edgedata:r1", "ghost"), "12%"),),
    )
    return render_study_text(replace(study, report=report))


def test_the_plain_text_of_a_completed_study_has_the_fixed_layout() -> None:
    text = render_study_text(_completed())

    headings = (
        "STUDY st-1  (completed)",
        "Question: what if we close lane 1 of E12 at peak?",
        "SUMMARY",
        "METHOD",
        "CLAIMS",
        "EVIDENCE",
        "EXPERIMENTS",
        "MODE AND BASIS",
        "LIMITATIONS",
    )
    positions = [text.index(h) for h in headings]
    assert positions == sorted(positions)
    assert "closing the lane shifts delay to the parallel corridor" in text
    assert "one baseline, one treatment" in text
    assert "  - delay +12 % [value: 12%] [evidence: query_edgedata:r1, ghost]" in text
    assert "  free, observed" in text
    assert "  - single seed" in text


def test_the_plain_text_has_no_markdown_syntax_outside_the_models_prose() -> None:
    text = _plain(_completed(forced=True))

    assert not any(c in text for c in _FORBIDDEN)


def test_the_plain_text_keeps_the_content_of_the_markdown() -> None:
    study = _completed()
    text = render_study_text(study)

    assert "  query_edgedata:r1  query       E12 0.91" in text
    assert "  ghost              unresolved  -" in text
    assert "phase 0  base       baseline   scenario s0  1 result  reused" in text
    assert "phase 0  treatment  treatment  scenario s1  1 result  run now" in text
    assert "phase 1  extra      treatment  scenario s2  1 result  run now" in text


def test_a_study_without_experiments_run_now_renders_in_plain_text() -> None:
    text = render_study_text(_completed(run_now=False, two_phases=False))

    experiments = text.split("EXPERIMENTS")[1].split("MODE AND BASIS")[0]
    assert "run now" not in experiments
    assert experiments.count("reused") == 2


def test_the_forced_by_limit_line_is_in_the_plain_text_limitations() -> None:
    text = render_study_text(_completed(forced=True))

    assert f"  - {FORCED_LIMITATION}" in text.split("LIMITATIONS")[1]


def test_a_report_without_limitations_or_claims_says_so_in_plain_text() -> None:
    study = _with_report(limitations=(), claims=())

    text = render_study_text(study)

    assert "  None stated." in text.split("LIMITATIONS")[1]
    assert "  No claims." in text.split("CLAIMS")[1]


def test_plain_text_ids_are_cut_to_eight_characters() -> None:
    study = _long_ids(_completed(), "2b6cb38a1111", "6b06b10a2222")
    study = replace(study, study_id="ded4f627aaaa")

    text = render_study_text(study)

    assert "STUDY ded4f627  (completed)" in text
    assert "scenario 2b6cb38a  " in text and "scenario 6b06b10a  " in text
    assert "2b6cb38a1" not in text


def test_plain_text_ids_are_extended_only_when_two_collide() -> None:
    study = _long_ids(_completed(), "2b6cb38a1111", "2b6cb38a2222")

    text = render_study_text(study)

    assert "scenario 2b6cb38a1  " in text and "scenario 2b6cb38a2  " in text
    assert "scenario s2  " in text  # the third one is short and untouched


def test_the_markdown_keeps_full_ids() -> None:
    study = _long_ids(_completed(), "2b6cb38a1111", "6b06b10a2222")

    assert "2b6cb38a1111" in render_study(study)


def test_plain_text_columns_line_up_whatever_the_content() -> None:
    study = _completed()
    phase = study.phases[0]
    odd = replace(phase.experiments[0], arm="a-very-long-arm-name", scenario_id="s" * 20)
    study = replace(
        study, phases=(replace(phase, experiments=(odd, *phase.experiments[1:])), *study.phases[1:])
    )

    text = render_study_text(study)

    rows = [x for x in text.splitlines() if x.startswith("  phase ")]
    assert len(rows) == 3
    for column in ("scenario s", "1 result"):
        assert len({r.index(column) for r in rows}) == 1
    origins = [r.index("reused" if "reused" in r else "run now") for r in rows]
    assert len(set(origins)) == 1


def test_plain_text_fields_stay_on_one_line_and_titles_cannot_mimic_headings() -> None:
    study = _with_report(
        sections=(ReportSection("Evidence", "a"), ReportSection("Two\n## Claims", "b")),
        claims=(Claim("delay\nup", ("query_edgedata:r1",), "12\n%"),),
        limitations=("one\ntwo",),
    )

    text = render_study_text(study)

    assert "EVIDENCE (from the Composer)\na" in text
    assert "TWO ## CLAIMS\nb" in text
    assert "  - delay up [value: 12 %] [evidence: query_edgedata:r1]" in text
    assert "  - one two" in text
    assert text.count("\nEVIDENCE\n") == 1


@pytest.mark.parametrize("kind", list(StepErrorKind))
def test_a_failed_study_renders_the_three_blocks_in_plain_text(kind: StepErrorKind) -> None:
    text = render_study_text(failed(kind, "unknown lane 'E99_0'"))

    blocks = ("WHAT HAPPENED", "WHAT WAS DONE", "WHAT YOU CAN DO")
    assert [text.index(b) for b in blocks] == sorted(text.index(b) for b in blocks)
    assert text.startswith("STUDY st-9  (failed)\nQuestion: what if we close lane 1 of E12?\n")
    assert f"Step build_scenario of phase 0 (the question as asked) failed ({kind})" in text
    assert "  - unknown lane 'E99_0'" in text
    assert "  - plan ok" in text
    assert "  - experiment base (baseline, reused): scenario s-base, 2 result(s)" in text
    assert text.rstrip().endswith(WHAT_TO_DO[kind])
    assert not any(c in text for c in _FORBIDDEN)


def test_an_awaiting_user_study_renders_the_three_blocks_in_plain_text() -> None:
    study = Study(
        study_id="st-a",
        status=StudyStatus.AWAITING_USER,
        phases=(Phase(question=Question("close it", Intent.RUN, ambiguities=("which edge?",))),),
    )

    text = render_study_text(study)

    assert text.startswith("STUDY st-a  (awaiting_user)\nQuestion: close it\n")
    assert "WHAT HAPPENED\nThe question is ambiguous:\n  - which edge?" in text
    assert "WHAT WAS DONE\nNothing was run: the study stopped before planning." in text
    assert "WHAT YOU CAN DO\nAsk again" in text
    assert not any(c in text for c in _FORBIDDEN)


def test_a_study_still_running_has_no_plain_text() -> None:
    study = replace(_completed(), status=StudyStatus.RUNNING, report=None)

    with pytest.raises(ValueError):
        render_study_text(study)


def test_plain_text_failure_fields_stay_on_one_line() -> None:
    study = failed(StepErrorKind.USER_INPUT, "unknown\nlane")
    phase = study.phases[0]
    step = replace(
        phase.steps[1],
        error=StepError(StepErrorKind.USER_INPUT, "the\nstep failed", ("unknown\nlane",)),
    )
    steps = (phase.steps[0], step, phase.steps[2])
    study = replace(study, phases=(replace(phase, steps=steps),))

    text = render_study_text(study)

    assert "failed (user_input): the step failed\n  - unknown lane\n" in text
