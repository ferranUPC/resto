"""The two specialist steps through `execute_study` with the scripted agents (ADR-0037 §2, §3): a
specialist ends in a found id or in a draft that code promotes."""

from pathlib import Path

from resto.application.ports.llm import StopReason
from resto.domain.entities.study import StudyStatus
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.outcomes import Found
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.step_record import StepErrorKind, StepStatus
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.tasks import ObtainDemandTask, ObtainNetworkTask
from tests.unit.application._world import (
    BASELINE_PLAN,
    CALIBRATION_ROUNDS,
    CLOSURE,
    NETWORK_ROUNDS,
    WHAT_IF,
    World,
    answers,
    failed_kind,
    run_of,
    tools,
)
from tests.unit.domain._fixtures import DEMAND, NET, demand_draft, network_draft

NETWORK_ONLY = Question(
    text="tell me about RIVERSIDE",
    intent=Intent.DESCRIBE,
    network_ref="RIVERSIDE",
    network_only=True,
)


def _obtain_plan(
    *,
    network_ref: str = "RIVERSIDE",
    max_rounds: int | None = None,
    max_calibration_rounds: int | None = None,
) -> object:
    """Obtain the network and the demand, then build and run the base arm on what they produced."""
    return run_of(
        StudyPlan(
            network_id=FromStep(0),
            rationale="as needed",
            steps=(
                ObtainNetworkStep(network_ref, max_rounds=max_rounds),
                ObtainDemandStep(
                    network_id=FromStep(0),
                    seed=1,
                    demand_ref="the peak",
                    max_calibration_rounds=max_calibration_rounds,
                    depends_on=(0,),
                ),
                BuildScenarioStep(
                    network_id=FromStep(0),
                    demand_id=FromStep(1),
                    arm="base",
                    role=ExperimentRole.BASELINE,
                    purpose="reference",
                    depends_on=(0, 1),
                ),
                RunSimulationStep(scenario_id=FromStep(2), depends_on=(2,)),
            ),
        )
    )


def test_a_specialist_that_finds_an_id_continues_the_study(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(_obtain_plan(),), expert=(answers(),))

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert [t for t, _ in tools(study)][:5] == [
        "plan",
        "obtain_network",
        "obtain_demand",
        "build_scenario",
        "run_simulation",
    ]
    assert world.promoted_networks == []  # nothing to promote: the ids were found
    network_task = world.author.calls[0][0]
    assert network_task == ObtainNetworkTask(network_ref="RIVERSIDE", max_rounds=NETWORK_ROUNDS)
    demand_task = world.generator.calls[0][0]
    assert demand_task == ObtainDemandTask(
        network_id=NET, seed=1, max_calibration_rounds=CALIBRATION_ROUNDS, demand_ref="the peak"
    )
    (experiment,) = study.phases[0].experiments
    assert world.scenarios.get(experiment.scenario_id).demand_id == DEMAND  # type: ignore[union-attr]
    assert study.network_ids == (NET,)


def test_a_step_that_sets_its_rounds_overrides_the_configured_limits(tmp_path: Path) -> None:
    plan = _obtain_plan(max_rounds=2, max_calibration_rounds=4)
    world = World(tmp_path, plans=(plan,), expert=(answers(),))

    world.run()

    assert world.author.calls[0][0].max_rounds == 2
    assert world.generator.calls[0][0].max_calibration_rounds == 4


def test_a_specialist_that_returns_a_draft_has_it_promoted_by_code(tmp_path: Path) -> None:
    world = World(
        tmp_path,
        plans=(_obtain_plan(),),
        author=(run_of(network_draft(), tokens=100),),
        generator=(run_of(demand_draft(), tokens=100),),
        expert=(answers(),),
    )

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert world.promoted_networks == [
        ObtainNetworkTask(network_ref="RIVERSIDE", max_rounds=NETWORK_ROUNDS)
    ]
    obtained = study.phases[0].steps[1]
    assert obtained.produced_ids == ("obtained-1",)  # the id code gave it, not the agent
    assert study.network_ids == ("obtained-1",)
    assert study.phases[0].steps[2].produced_ids == ("obtained-demand",)
    assert obtained.usage.input_tokens == 100


def test_a_network_only_question_runs_as_a_one_step_plan(tmp_path: Path) -> None:
    only_network = run_of(
        StudyPlan(
            network_id=FromStep(0),
            rationale="network only",
            steps=(ObtainNetworkStep("RIVERSIDE"),),
        )
    )
    world = World(tmp_path, question=NETWORK_ONLY, plans=(only_network,), expert=(answers(),))

    study = world.run()

    assert study.status is StudyStatus.COMPLETED
    assert tools(study) == [
        ("plan", StepStatus.OK),
        ("obtain_network", StepStatus.OK),
        ("ask_expert", StepStatus.OK),
        ("compose_report", StepStatus.OK),
    ]
    assert study.phases[0].experiments == ()
    assert world.generator.calls == [] and world.builder.calls == []
    assert study.network_ids == (NET,)


def test_a_found_network_that_is_not_stored_fails_the_step(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), author=(run_of(Found("nope")),))

    study = world.run()

    assert study.status is StudyStatus.FAILED
    assert failed_kind(study) is StepErrorKind.AGENT
    assert study.phases[0].failed_step.tool == "obtain_network"  # type: ignore[union-attr]
    assert world.builder.calls == []


def test_a_found_demand_must_be_stored_for_the_resolved_network(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(_obtain_plan(),), generator=(run_of(Found("nope")),))

    study = world.run()

    assert study.status is StudyStatus.FAILED
    assert failed_kind(study) is StepErrorKind.AGENT
    assert study.phases[0].failed_step.tool == "obtain_demand"  # type: ignore[union-attr]
    assert world.builder.calls == []


def test_a_specialist_cut_by_its_budget_fails_the_step_as_budget(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(BASELINE_PLAN,), author=(run_of(None, stop=StopReason.BUDGET),))

    study = world.run()

    assert study.status is StudyStatus.FAILED
    assert failed_kind(study) is StepErrorKind.BUDGET
    assert study.phases[0].failed_step.tool == "obtain_network"  # type: ignore[union-attr]


def test_the_demand_task_carries_the_study_window_derived_from_the_question(
    tmp_path: Path,
) -> None:
    world = World(tmp_path, question=WHAT_IF, plans=(_obtain_plan(),), expert=(answers(),))

    world.run()

    assert world.generator.calls[0][0].window == CLOSURE.window


def test_the_demand_task_has_no_window_when_no_intervention_has_one(tmp_path: Path) -> None:
    world = World(tmp_path, plans=(_obtain_plan(),), expert=(answers(),))

    world.run()

    assert world.generator.calls[0][0].window is None
