"""Loop closure (E5.3; ADR-0023, ADR-0025): across rounds the study never simulates a (scenario,
seed) that already has an ok result. The counter is `world.runner.calls` read through
`World.simulations()`; it is not a wrapper on `run_simulation`, which hides the deduplication.

Not redundant (GLOSSARY.md): the load check (seed 0, one per built scenario), a rerun of a failed
result, and the missing seeds of a partly stored scenario."""

from dataclasses import replace
from pathlib import Path

from resto.domain.constants import DEFAULT_SEEDS
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.arm import Arm
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.question import Intent, Mode, Question
from resto.domain.value_objects.step_record import StepStatus
from tests.unit.application._world import (
    BASE_SID,
    BASELINE_PLAN,
    CLOSURE,
    CLOSURE_SID,
    DESCRIBE_CHANGE,
    PROPOSED,
    TREATMENT_PLAN,
    WHAT_IF,
    WHAT_IF_PLAN,
    World,
    abstains,
    answers,
    plan,
    tools,
)
from tests.unit.domain._fixtures import build_step, run_step


def _ok(*names: str) -> list[tuple[str, StepStatus]]:
    return [(name, StepStatus.OK) for name in names]


def _pairs(sid: str) -> set[tuple[str, int]]:
    return {(sid, seed) for seed in DEFAULT_SEEDS}


def test_results_stored_before_the_study_are_never_simulated_again(tmp_path: Path) -> None:
    world = World(tmp_path, question=WHAT_IF, plans=(WHAT_IF_PLAN,), expert=(answers(),))
    world.store_scenario(())  # the base, all seeds

    study = world.run()

    simulations = world.simulations()
    assert study.status is StudyStatus.COMPLETED
    assert len(simulations.study_runs) == len(DEFAULT_SEEDS)
    assert set(simulations.study_runs) == _pairs(CLOSURE_SID)
    assert len(set(simulations.study_runs)) == len(simulations.study_runs)  # no pair repeats
    assert simulations.load_checks == ((CLOSURE_SID, 0),)  # the built scenario only
    base, treatment = study.phases[0].experiments
    assert (base.reused, treatment.reused) == (True, False)


def test_an_arm_realised_in_phase_0_is_reused_when_phase_1_touches_it_again(
    tmp_path: Path,
) -> None:
    """A plan may not re-realise an arm name, so phase 1 names the same scenario under a new arm."""
    shutdown = Question(
        text="shut lane 1 of E12",
        intent=Intent.RUN,
        arms=(Arm("shutdown", interventions=(CLOSURE,)),),
    )
    again = plan(build_step("shutdown", (CLOSURE,), role=ExperimentRole.TREATMENT), run_step(0))
    world = World(
        tmp_path,
        question=WHAT_IF,
        plans=(WHAT_IF_PLAN, again),
        expert=(abstains(shutdown), answers()),
    )

    study = world.run()

    simulations = world.simulations()
    assert study.status is StudyStatus.COMPLETED and len(study.phases) == 2
    assert len(simulations.study_runs) == 2 * len(DEFAULT_SEEDS)
    assert set(simulations.study_runs) == _pairs(BASE_SID) | _pairs(CLOSURE_SID)
    assert len(set(simulations.study_runs)) == len(simulations.study_runs)
    assert set(simulations.load_checks) == {(BASE_SID, 0), (CLOSURE_SID, 0)}
    assert len(simulations.load_checks) == 2  # built once each, not again in phase 1
    treatment = study.phases[0].experiments[1]
    (second,) = study.phases[1].experiments
    assert second.reused is True
    assert second.scenario_id == treatment.scenario_id and second.result_ids == treatment.result_ids


def test_an_experiment_whose_scenario_is_already_stored_runs_nothing(tmp_path: Path) -> None:
    runner_log_at_phase_1: list[int] = []

    def plan_phase_1(question: object, context: object) -> object:
        runner_log_at_phase_1.append(len(world.runner.calls))
        return TREATMENT_PLAN

    world = World(
        tmp_path,
        question=DESCRIBE_CHANGE,
        plans=(BASELINE_PLAN, plan_phase_1),
        expert=(abstains(PROPOSED), answers()),
    )
    _, closure_ids = world.store_scenario((CLOSURE,))  # the proposed experiment, stored

    study = world.run()

    assert study.status is StudyStatus.COMPLETED and len(study.phases) == 2  # phase 1 is planned
    (treatment,) = study.phases[1].experiments
    assert treatment.reused is True and treatment.result_ids == closure_ids
    simulations = world.simulations()
    assert simulations.study_runs == tuple((BASE_SID, seed) for seed in DEFAULT_SEEDS)  # phase 0
    assert len(world.runner.calls) == runner_log_at_phase_1[0]  # unchanged after the proposal
    assert all(sid != CLOSURE_SID for sid, _ in simulations.load_checks + simulations.study_runs)


def test_forced_mode_only_forbids_abstaining_so_the_treatment_is_predicted_not_simulated(
    tmp_path: Path,
) -> None:
    """GP-4 (ADR-0038 §4, not the frozen §5 row "no simulation"): forced mode forbids only the
    Expert's abstention. The plan still simulates the base; the treatment it was not planned to
    run comes out as a predicted scenario."""
    world = World(
        tmp_path,
        question=replace(DESCRIBE_CHANGE, mode=Mode.FORCED),
        plans=(BASELINE_PLAN,),
        expert=(answers(),),
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED and len(study.phases) == 1
    assert tools(study) == _ok(
        "plan", "obtain_network", "build_scenario", "run_simulation", "ask_expert", "compose_report"
    )
    assert len(world.planner.calls) == 1
    assert len(world.expert.calls) == 1 and world.expert.calls[0][0].mode is Mode.FORCED
    simulations = world.simulations()
    assert simulations.study_runs == tuple((BASE_SID, seed) for seed in DEFAULT_SEEDS)
    assert {sid for sid, _ in simulations.load_checks} == {BASE_SID}
    (task,) = (call[0] for call in world.note_writer.calls)
    predicted = [s for s in task.scenarios if s.scenario_id == CLOSURE_SID]
    assert [s.simulated for s in predicted] == [False]


def test_a_question_whose_two_arms_are_stored_costs_no_simulation(tmp_path: Path) -> None:
    """GP-5: with both arms of the contrast already stored, the plan builds and runs nothing."""
    world = World(tmp_path, question=WHAT_IF, plans=(WHAT_IF_PLAN,), expert=(answers(),))
    _, base_ids = world.store_scenario(())
    _, closure_ids = world.store_scenario((CLOSURE,))

    study = world.run()

    assert study.status is StudyStatus.COMPLETED and len(study.phases) == 1
    # The steps are still recorded; each build and run finds its result stored and does no work.
    assert tools(study) == _ok(
        "plan",
        "obtain_network",
        "build_scenario",
        "run_simulation",
        "build_scenario",
        "run_simulation",
        "ask_expert",
        "compose_report",
    )
    assert world.runner.calls == []
    assert world.builder.calls == []
    assert len(world.planner.calls) == 1 and len(world.expert.calls) == 1
    base, treatment = study.phases[0].experiments
    assert (base.reused, treatment.reused) == (True, True)
    assert (base.result_ids, treatment.result_ids) == (base_ids, closure_ids)
