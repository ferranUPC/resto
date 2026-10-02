"""The Executor looks a scenario up by the hash of its typed request before calling the Scenario
Builder (ADR-0037 §5): ok results found means `reused` and no LLM call."""

from pathlib import Path

from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from tests.unit.application._world import (
    BASE_SID,
    BASELINE_PLAN,
    CLOSURE,
    CLOSURE_SID,
    PROPOSED,
    World,
    answers,
    plan,
    run_of,
)
from tests.unit.domain._fixtures import artifact, build_step, run_step

BOTH_ARMS = plan(
    build_step(),
    run_step(0),
    build_step("treatment", (CLOSURE,), role=ExperimentRole.TREATMENT),
    run_step(2),
)


def test_a_scenario_with_ok_results_is_reused_without_calling_the_builder(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    _, ids = world.store_scenario()

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert world.builder.calls == [] and world.runner.calls == []
    assert study.phases[0].experiments == (
        Experiment(BASE_SID, "base", ExperimentRole.BASELINE, "arm base", ids, reused=True),
    )


def test_a_scenario_without_ok_results_goes_through_the_builder(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), expert=(answers(),))
    world.store_scenario(seeds=())  # stored, but no run ever finished ok

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert len(world.builder.calls) == 1
    (experiment,) = study.phases[0].experiments
    assert experiment.scenario_id == BASE_SID and not experiment.reused
    assert len(experiment.result_ids) == 3  # the runs happened now


def test_the_hash_before_the_builder_call_is_the_one_it_stores(tmp_path: Path) -> None:
    """If the two differed, the second identical request would call the Builder again."""
    world = World(
        tmp_path,
        question=PROPOSED,
        plans=(BOTH_ARMS, BOTH_ARMS),
        expert=(answers(), answers()),
    )

    first = world.run()
    world.parser.items.append(run_of(PROPOSED, tokens=50))
    second = world.run()

    assert [(e.scenario_id, e.reused) for e in first.phases[0].experiments] == [
        (BASE_SID, False),
        (CLOSURE_SID, False),
    ]
    assert [(e.scenario_id, e.reused) for e in second.phases[0].experiments] == [
        (BASE_SID, True),
        (CLOSURE_SID, True),
    ]
    assert len(world.builder.calls) == 2  # both from the first study


def test_when_the_hashes_differ_the_builder_runs_and_the_duplicate_is_found(
    tmp_path: Path,
) -> None:
    """The Builder accepts fewer interventions than asked, so its id is another one: the one it
    lands on already exists with ok results."""
    narrowed = ScenarioDraft(
        interventions=(),
        mechanisms=(),
        sumocfg=artifact("s.sumocfg", "c1", "sumocfg"),
        rationale="implemented without the closure",
    )
    world = World(
        tmp_path,
        question=PROPOSED,
        plans=(BOTH_ARMS,),
        builder=(run_of(narrowed, tokens=100),),
        expert=(answers(),),
    )
    world.store_scenario()

    study = world.run()

    assert len(world.builder.calls) == 1  # the base arm was reused, the treatment was built
    base, treatment = study.phases[0].experiments
    assert base.reused
    assert treatment.scenario_id == BASE_SID
    assert treatment.scenario_id != CLOSURE_SID
    assert not treatment.reused
    assert world.runner.calls == []  # the duplicate's results were already there
