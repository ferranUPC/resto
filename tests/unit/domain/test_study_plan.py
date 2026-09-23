import pytest

from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.network_source import NetworkSource
from resto.domain.value_objects.study_plan import (
    BuildScenarioStep,
    ClarificationRequest,
    DeriveNetworkStep,
    FromStep,
    GenerateNetworkStep,
    RerouteDemandStep,
    ReusedExperiment,
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
        network_id="n1",
        rationale="treatment is the derived network; baseline reused",
        steps=(
            DeriveNetworkStep(base_network_id="n1", modifications=(AddEdge("J7", "J9", 1, 13.9),)),
            RerouteDemandStep(demand_id="d1", network_id=FromStep(0), depends_on=(0,)),
            BuildScenarioStep(
                network_id=FromStep(0),
                demand_id=FromStep(1),
                arm="new-edge",
                role=ExperimentRole.TREATMENT,
                purpose="new edge J7-J9",
                depends_on=(0, 1),
            ),
            RunSimulationStep(scenario_id=FromStep(2), depends_on=(2,)),
        ),
        reused=(ReusedExperiment("s-base", "base", BASELINE, "network as it is"),),
    )


def test_a_plan_may_have_no_steps() -> None:
    plan = StudyPlan(
        network_id="n1",
        rationale="baseline results exist",
        reused=(ReusedExperiment("s1", "base", BASELINE, "reference"),),
    )
    assert plan.steps == ()


def test_a_multi_step_plan_with_from_step_is_valid() -> None:
    assert len(_gp11_plan().steps) == 4


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
            steps=(RunSimulationStep(scenario_id=FromStep(0), depends_on=(0,)),),
        )


def test_from_step_must_point_to_a_step_that_produces_the_expected_id() -> None:
    with pytest.raises(ValueError, match="a network is expected"):
        StudyPlan(
            network_id="n1",
            rationale="r",
            steps=(
                _build(),
                _build(network_id=FromStep(0), depends_on=(0,)),
            ),
        )


def test_plan_network_id_may_come_from_a_network_step() -> None:
    generate = GenerateNetworkStep(source=NetworkSource(kind="place", value="Eixample"))
    StudyPlan(network_id=FromStep(0), rationale="GP-8 creates the network", steps=(generate,))
    with pytest.raises(ValueError, match="not a step of this plan"):
        StudyPlan(network_id=FromStep(0), rationale="r")
    with pytest.raises(ValueError, match="a network is expected"):
        StudyPlan(network_id=FromStep(0), rationale="r", steps=(_build(),))


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
    with pytest.raises(ValueError, match="purpose"):
        ReusedExperiment("s1", "base", BASELINE, "")


def test_a_scenario_is_reused_once() -> None:
    reused = ReusedExperiment("s1", "base", BASELINE, "reference")
    with pytest.raises(ValueError, match="more than once"):
        StudyPlan(network_id="n1", rationale="r", reused=(reused, reused))


def test_a_clarification_needs_a_reason() -> None:
    with pytest.raises(ValueError):
        ClarificationRequest(reason="", candidates=("gv-2024",))


def test_each_arm_is_realised_once_per_plan() -> None:
    with pytest.raises(ValueError, match="once per plan"):
        StudyPlan(
            network_id="n1",
            rationale="r",
            steps=(_build(),),
            reused=(ReusedExperiment("s1", "base", BASELINE, "reference"),),
        )
    assert _gp11_plan().arms == ("base", "new-edge")


def test_a_build_step_names_its_arm() -> None:
    with pytest.raises(ValueError, match="arm"):
        _build(arm="")
