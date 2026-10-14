import dataclasses
from typing import get_args

import pytest

from resto.domain.entities.study import Phase
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.step_record import StepRecord, StepStatus
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
    PlanStep,
    RerouteDemandStep,
    RunSimulationStep,
    StudyPlan,
)
from resto.domain.value_objects.topology_modification import AddEdge

BASELINE = ExperimentRole.BASELINE


def _build(network_id: str | FromStep = "n1", demand_id: str | FromStep = "d1", **kw):  # noqa: ANN003, ANN202
    kw.setdefault("arm", "base")
    return BuildScenarioStep(
        network_id=network_id, demand_id=demand_id, role=BASELINE, purpose="reference", **kw
    )


def _gp11_plan() -> StudyPlan:
    """GP-11: derive a network with a new edge, reroute the demand, build and run both sides."""
    return StudyPlan(
        network_id=FromStep(0),
        rationale="treatment is the derived network",
        steps=(
            ObtainNetworkStep(network_ref="RIVERSIDE"),
            DeriveNetworkStep(
                base_network_id=FromStep(0),
                modifications=(AddEdge("J7", "J9", 1, 13.9),),
                depends_on=(0,),
            ),
            RerouteDemandStep(demand_id="d1", network_id=FromStep(1), depends_on=(1,)),
            BuildScenarioStep(
                network_id=FromStep(1),
                demand_id=FromStep(2),
                arm="new-edge",
                role=ExperimentRole.TREATMENT,
                purpose="new edge J7-J9",
                depends_on=(1, 2),
            ),
            RunSimulationStep(scenario_id=FromStep(3), depends_on=(3,)),
        ),
    )


def test_a_plan_with_no_steps_is_rejected() -> None:
    with pytest.raises(ValueError, match="obtain_network"):
        StudyPlan(
            network_id="n1",
            rationale="no steps",
            steps=(),
        )


def test_a_plan_without_obtain_network_is_rejected() -> None:
    with pytest.raises(ValueError, match="obtain_network"):
        StudyPlan(network_id="n1", rationale="r", steps=(_build(),))


def test_a_network_only_question_is_a_plan_of_one_obtain_network_step() -> None:
    plan = StudyPlan(
        network_id=FromStep(0), rationale="network only", steps=(ObtainNetworkStep("RIVERSIDE"),)
    )
    assert plan.arms == ()


def test_obtain_network_requires_its_reference() -> None:
    with pytest.raises(ValueError, match="reference"):
        ObtainNetworkStep(network_ref=" ")


def test_obtain_demand_takes_the_network_by_from_step() -> None:
    step = ObtainDemandStep(network_id=FromStep(0), seed=1, depends_on=(0,))
    assert step.inputs == ((FromStep(0), "network"),)
    assert step.produces == "demand"
    with pytest.raises(ValueError, match="depends_on"):
        ObtainDemandStep(network_id=FromStep(0), seed=1)
    with pytest.raises(ValueError, match="blank"):
        ObtainDemandStep(network_id=FromStep(0), seed=1, demand_ref=" ", depends_on=(0,))


def test_a_plan_rejects_a_demand_step_that_names_the_network_by_id() -> None:
    with pytest.raises(ValueError, match="by FromStep"):
        StudyPlan(
            network_id=FromStep(0),
            rationale="r",
            steps=(ObtainNetworkStep("RIVERSIDE"), ObtainDemandStep(network_id="n1", seed=1)),
        )


def test_a_demand_step_must_follow_a_network_step() -> None:
    with pytest.raises(ValueError, match="a network is expected"):
        StudyPlan(
            network_id=FromStep(0),
            rationale="r",
            steps=(
                ObtainNetworkStep("RIVERSIDE"),
                ObtainDemandStep(network_id=FromStep(0), seed=1, depends_on=(0,)),
                ObtainDemandStep(network_id=FromStep(1), seed=1, depends_on=(1,)),
            ),
        )


def test_a_multi_step_plan_with_from_step_is_valid() -> None:
    assert len(_gp11_plan().steps) == 5


def test_every_from_step_is_declared_in_depends_on() -> None:
    with pytest.raises(ValueError, match="depends_on"):
        RunSimulationStep(scenario_id=FromStep(0))
    with pytest.raises(ValueError, match="depends_on"):
        _build(network_id=FromStep(0), demand_id=FromStep(1), depends_on=(0,))


def test_depends_on_points_to_earlier_steps() -> None:
    with pytest.raises(ValueError, match="not earlier"):
        StudyPlan(
            network_id="n1",
            rationale="r",
            steps=(
                ObtainNetworkStep("RIVERSIDE"),
                RunSimulationStep(scenario_id=FromStep(1), depends_on=(1,)),
            ),
        )


def test_from_step_must_point_to_a_step_that_produces_the_expected_id() -> None:
    with pytest.raises(ValueError, match="a network is expected"):
        StudyPlan(
            network_id="n1",
            rationale="r",
            steps=(
                ObtainNetworkStep("RIVERSIDE"),
                _build(),
                _build(network_id=FromStep(1), depends_on=(1,)),
            ),
        )


def test_plan_network_id_may_come_from_a_network_step() -> None:
    obtain = ObtainNetworkStep(network_ref="Eixample")
    StudyPlan(network_id=FromStep(0), rationale="GP-8 obtains the network", steps=(obtain,))
    with pytest.raises(ValueError, match="not a step of this plan"):
        StudyPlan(network_id=FromStep(1), rationale="r", steps=(obtain,))
    with pytest.raises(ValueError, match="a network is expected"):
        StudyPlan(network_id=FromStep(1), rationale="r", steps=(obtain, _build()))


def test_deriving_a_network_needs_a_modification() -> None:
    with pytest.raises(ValueError, match="modification"):
        DeriveNetworkStep(base_network_id="n1", modifications=())


def test_explicit_seeds_are_non_empty_and_distinct() -> None:
    assert RunSimulationStep(scenario_id="s1").seeds is None
    with pytest.raises(ValueError):
        RunSimulationStep(scenario_id="s1", seeds=())
    with pytest.raises(ValueError):
        RunSimulationStep(scenario_id="s1", seeds=(1, 1))


def test_role_and_purpose_are_declared() -> None:
    with pytest.raises(ValueError, match="purpose"):
        BuildScenarioStep(network_id="n1", demand_id="d1", arm="base", role=BASELINE, purpose=" ")


def test_each_arm_is_realised_once_per_plan() -> None:
    with pytest.raises(ValueError, match="once per plan"):
        StudyPlan(
            network_id="n1",
            rationale="r",
            steps=(ObtainNetworkStep("RIVERSIDE"), _build(), _build()),
        )
    assert _gp11_plan().arms == ("new-edge",)


def test_a_build_step_names_its_arm() -> None:
    with pytest.raises(ValueError, match="arm"):
        _build(arm="")


def test_a_step_refs_are_the_ids_it_names_directly_by_kind() -> None:
    derive = DeriveNetworkStep(base_network_id="n0", modifications=(AddEdge("J7", "J9", 1, 13.9),))

    assert ObtainNetworkStep(network_ref="RIVERSIDE").refs() == ()
    assert derive.refs() == (("network", "n0"),)
    assert ObtainDemandStep(network_id="n1", seed=1).refs() == (("network", "n1"),)
    assert RerouteDemandStep(demand_id="d1", network_id="n2").refs() == (
        ("demand", "d1"),
        ("network", "n2"),
    )
    assert _build("n1", "d1").refs() == (("network", "n1"), ("demand", "d1"))
    assert RunSimulationStep(scenario_id="s1").refs() == (("scenario", "s1"),)


def test_ids_named_through_from_step_are_not_refs() -> None:
    assert _build(FromStep(0), "d1", depends_on=(0,)).refs() == (("demand", "d1"),)
    assert RunSimulationStep(scenario_id=FromStep(3), depends_on=(3,)).refs() == ()


# --- apply: a step's effect on its phase ------------------------------------------------------

APPLIED_PLAN = StudyPlan(
    network_id=FromStep(0),
    rationale="two arms on one demand",
    steps=(
        ObtainNetworkStep(network_ref="RIVERSIDE"),
        ObtainDemandStep(network_id=FromStep(0), seed=1, depends_on=(0,)),
        _build(FromStep(0), FromStep(1), arm="base", depends_on=(0, 1)),
        _build(FromStep(0), FromStep(1), arm="closed", depends_on=(0, 1)),
        RunSimulationStep(scenario_id=FromStep(3), depends_on=(3,)),
        RunSimulationStep(scenario_id=FromStep(2), depends_on=(2,)),
    ),
)
NETWORK = StepRecord("obtain_network", StepStatus.OK, produced_ids=("net1",))
DEMAND = StepRecord("obtain_demand", StepStatus.OK, produced_ids=("dem1",))
BUILT_BASE = StepRecord("build_scenario", StepStatus.OK, produced_ids=("scen-base",))
BUILT_CLOSED = StepRecord("build_scenario", StepStatus.OK, produced_ids=("scen-closed",))
RAN = StepRecord("run_simulation", StepStatus.OK, produced_ids=("r1", "r2"))
BASE = Experiment("scen-base", "base", BASELINE, "reference", step_index=2)
CLOSED = Experiment("scen-closed", "closed", BASELINE, "reference", step_index=3)


def _phase(*records: StepRecord, experiments: tuple[Experiment, ...] = ()) -> Phase:
    """The phase of APPLIED_PLAN with `records` recorded after its planning."""
    planned = StepRecord("plan", StepStatus.OK)
    question = Question(text="what happens at peak?", intent=Intent.DESCRIBE)
    return Phase(question, APPLIED_PLAN, steps=(planned, *records), experiments=experiments)


def test_a_step_that_builds_no_scenario_and_runs_nothing_leaves_its_phase_as_it_is() -> None:
    derive, reroute = _gp11_plan().steps[1:3]
    phase = _phase(NETWORK)

    for step in (APPLIED_PLAN.steps[0], APPLIED_PLAN.steps[1], derive, reroute):
        assert step.apply(phase, DEMAND, ()) == phase
        with pytest.raises(ValueError, match="reuse"):
            step.apply(phase, DEMAND, ("r1",))


def test_a_build_step_adds_the_experiment_of_its_arm_with_its_step_index() -> None:
    phase = _phase(NETWORK, DEMAND)

    assert APPLIED_PLAN.steps[2].apply(phase, BUILT_BASE, ()).experiments == (BASE,)


def test_a_build_step_that_found_its_scenario_stored_reuses_its_results() -> None:
    phase = _phase(NETWORK, DEMAND)

    (experiment,) = APPLIED_PLAN.steps[2].apply(phase, BUILT_BASE, ("r1",)).experiments

    assert (experiment.result_ids, experiment.reused) == (("r1",), True)


def test_a_build_step_produces_one_scenario() -> None:
    two = StepRecord("build_scenario", StepStatus.OK, produced_ids=("s1", "s2"))
    with pytest.raises(ValueError, match="one scenario"):
        APPLIED_PLAN.steps[2].apply(_phase(NETWORK, DEMAND), two, ())


def test_a_run_joins_the_experiment_of_the_step_that_built_its_scenario() -> None:
    built = (NETWORK, DEMAND, BUILT_BASE, BUILT_CLOSED)
    phase = _phase(*built, experiments=(BASE, CLOSED))

    ran = APPLIED_PLAN.steps[4].apply(phase, RAN, ())

    assert ran.experiments == (BASE, dataclasses.replace(CLOSED, result_ids=("r1", "r2")))


def test_a_run_adds_its_results_to_those_its_experiment_reused_without_repeats() -> None:
    reused = dataclasses.replace(CLOSED, result_ids=("r1",), reused=True)
    phase = _phase(NETWORK, DEMAND, BUILT_BASE, BUILT_CLOSED, experiments=(BASE, reused))

    (_, closed) = APPLIED_PLAN.steps[4].apply(phase, RAN, ("r1",)).experiments

    assert closed.result_ids == ("r1", "r2")


def test_a_run_reuses_only_results_it_holds() -> None:
    phase = _phase(NETWORK, DEMAND, BUILT_BASE, BUILT_CLOSED, experiments=(BASE, CLOSED))
    with pytest.raises(ValueError, match="reuse"):
        APPLIED_PLAN.steps[4].apply(phase, RAN, ("r9",))


def test_a_run_on_a_stored_scenario_joins_no_experiment() -> None:
    phase = _phase(NETWORK, DEMAND, BUILT_BASE, experiments=(BASE,))

    assert RunSimulationStep(scenario_id="scen-stored").apply(phase, RAN, ()) == phase


def test_every_plan_step_variant_declares_its_ids_and_its_effect() -> None:
    for variant in get_args(PlanStep):
        assert "ids" in vars(variant), f"{variant.__name__} declares no ids"
        assert "apply" in vars(variant), f"{variant.__name__} declares no apply()"
