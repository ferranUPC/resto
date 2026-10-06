import pytest

from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    DeriveNetworkStep,
    FromStep,
    ObtainDemandStep,
    ObtainNetworkStep,
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
