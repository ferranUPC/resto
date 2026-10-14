"""The order of a study's steps, phase by phase (ADR-0043: the golden paths no longer assert it).

What each phase traced, in which order, with which arms and which reuse, and how the Expert's
rounds were numbered. The golden paths assert only the outcome; this is where the route is held.
"""

from dataclasses import replace
from pathlib import Path

from resto.domain.entities.study import Study, StudyResolution
from resto.domain.events import PhaseStarted, PlanMade
from resto.domain.value_objects.expert_answer import Basis
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.step_record import StepStatus
from tests.unit.application._world import (
    BASELINE_PLAN,
    CLOSURE,
    DESCRIBE,
    DESCRIBE_CHANGE,
    PROPOSED,
    TREATMENT_PLAN,
    WHAT_IF,
    WHAT_IF_PLAN,
    World,
    abstains,
    answers,
    tools,
)

BUILD_AND_RUN = ("plan", "obtain_network", "build_scenario", "run_simulation")
BASELINE_STEPS = (*BUILD_AND_RUN, "ask_expert", "compose_report")
TWO_ARM_STEPS = (
    *BUILD_AND_RUN,
    "build_scenario",
    "run_simulation",
    "ask_expert",
    "compose_report",
)


def _ok(*names: str) -> list[tuple[str, StepStatus]]:
    return [(name, StepStatus.OK) for name in names]


def _arms(study: Study, phase: int = 0) -> list[str]:
    return [e.arm for e in study.phases[phase].experiments]


def _reused(study: Study, phase: int = 0) -> list[bool]:
    return [e.reused for e in study.phases[phase].experiments]


def _answer(study: Study, phase: int = 0) -> tuple[Basis, bool, int]:
    held = study.phases[phase].round
    assert held is not None
    return held.answer.basis, held.forced_by_limit, study.rounds.index(held) + 1


def test_a_baseline_obtains_builds_runs_asks_and_composes_in_that_order(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))

    study = world.run()

    assert study.resolution is StudyResolution.COMPLETED and len(study.phases) == 1
    assert tools(study) == _ok(*BASELINE_STEPS)
    assert _arms(study) == ["base"] and _reused(study) == [False]
    assert _answer(study) == (Basis.OBSERVED, False, 1)


def test_a_stored_baseline_keeps_every_step_and_marks_the_arm_reused(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    world.store_scenario()

    study = world.run()

    assert tools(study) == _ok(*BASELINE_STEPS)
    assert _arms(study) == ["base"] and _reused(study) == [True]
    assert _answer(study) == (Basis.OBSERVED, False, 1)


def test_a_contrast_builds_and_runs_each_arm_in_one_phase_before_asking(tmp_path: Path) -> None:
    world = World(tmp_path, question=WHAT_IF, plans=(WHAT_IF_PLAN,), expert=(answers(),))

    study = world.run()

    assert len(study.phases) == 1
    assert tools(study) == _ok(*TWO_ARM_STEPS)
    assert _arms(study) == ["base", "treatment"] and _reused(study) == [False, False]
    assert _answer(study) == (Basis.OBSERVED, False, 1)


def test_a_contrast_with_both_arms_stored_keeps_the_steps_and_reuses_both(tmp_path: Path) -> None:
    world = World(tmp_path, question=WHAT_IF, plans=(WHAT_IF_PLAN,), expert=(answers(),))
    world.store_scenario(())
    world.store_scenario((CLOSURE,))

    study = world.run()

    assert tools(study) == _ok(*TWO_ARM_STEPS)
    assert _arms(study) == ["base", "treatment"] and _reused(study) == [True, True]


def test_an_arm_the_expert_asks_for_is_a_second_phase_and_a_second_round(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        question=DESCRIBE_CHANGE,
        plans=(BASELINE_PLAN, TREATMENT_PLAN),
        expert=(abstains(PROPOSED), answers()),
    )

    study = world.run()

    assert len(study.phases) == 2
    assert tools(study, 0) == _ok(*BUILD_AND_RUN, "ask_expert")
    assert tools(study, 1) == _ok(*BUILD_AND_RUN, "ask_expert", "compose_report")
    assert _arms(study, 0) == ["base"] and _arms(study, 1) == ["treatment"]
    assert _reused(study, 0) == [False] and _reused(study, 1) == [False]
    assert _answer(study, 1) == (Basis.OBSERVED, False, 2)


def test_forced_mode_runs_the_base_alone_and_answers_in_one_round(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        question=replace(DESCRIBE_CHANGE, mode=Mode.FORCED),
        plans=(BASELINE_PLAN,),
        expert=(answers(),),
    )

    study = world.run()

    assert len(study.phases) == 1
    assert tools(study) == _ok(*BASELINE_STEPS)
    assert _arms(study) == ["base"]
    assert _answer(study) == (Basis.OBSERVED, False, 1)


def test_an_ambiguous_request_opens_one_empty_phase_and_plans_nothing(tmp_path: Path) -> None:
    world = World(tmp_path, question=replace(DESCRIBE, ambiguities=("which peak?",)))

    study = world.run()

    assert study.resolution is StudyResolution.AWAITING_USER
    assert len(study.phases) == 1 and tools(study) == []
    assert study.phases[0].plan is None and study.phases[0].round is None
    kinds = [type(e) for e in world.tracer.events]
    assert PhaseStarted in kinds and PlanMade not in kinds
    assert world.builder.calls == [] and world.runner.calls == [] and world.expert.calls == []
