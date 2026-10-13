"""The note writer's task (ADR-0026, ADR-0032): the study decides it over the scenarios and
networks the caller loaded, so no repository and no agent appears here."""

from dataclasses import replace

import pytest

from resto.domain.entities.network import Network
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.study import Study
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.arm import BASE_ARM, Arm
from resto.domain.value_objects.experiment import Experiment, ExperimentRole
from resto.domain.value_objects.network_recipe import NetworkRecipe
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.tasks import NoteScenario, NoteTask
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.domain._fixtures import (
    DEMAND,
    NET,
    artifact,
    static_intervention,
    study_with_rounds,
)
from tests.unit.domain._samples import network, scenario


def _derived(network_id: str, base: str = NET) -> Network:
    return replace(
        network(),
        network_id=network_id,
        net_xml=artifact(f"{network_id}.net.xml", network_id, "net"),
        recipe=NetworkRecipe(base_network_id=base),
        derived_from=base,
    )


def test_the_base_network_is_the_one_not_derived_from_another_wherever_it_comes() -> None:
    """`network_ids` keeps the order the study met its networks: a derived one can come first."""
    study = replace(study_with_rounds(), network_ids=("derived-1", NET))
    final = study.current_phase.round
    assert final is not None

    task = study.note_task(
        final, scenarios={}, networks={"derived-1": _derived("derived-1"), NET: network()}
    )

    assert task.round == final
    assert task.base_network_id == NET


def test_a_study_without_a_stored_base_network_has_no_note_task() -> None:
    study = replace(study_with_rounds(), network_ids=("derived-1", "ghost"))
    final = study.current_phase.round
    assert final is not None

    with pytest.raises(ValueError, match="none of the study's networks is stored as a base"):
        study.note_task(final, scenarios={}, networks={"derived-1": _derived("derived-1")})


BASE = Experiment("s-base", BASE_ARM, ExperimentRole.BASELINE, "reference", 1, ("r1",))
EDGE = Experiment("s-edge", "edge", ExperimentRole.TREATMENT, "the new edge", 2)


def _scenario(scenario_id: str, network_id: str = NET) -> Scenario:
    return replace(scenario(), scenario_id=scenario_id, network_id=network_id)


def _task(study: Study, scenarios: dict[str, Scenario]) -> NoteTask:
    study = replace(study, network_ids=(NET, "derived-1"))
    final = study.current_phase.round
    assert final is not None
    networks = {NET: network(), "derived-1": _derived("derived-1")}
    return study.note_task(final, scenarios=scenarios, networks=networks)


def test_the_study_names_the_scenarios_to_load_in_order_without_repeats() -> None:
    study = study_with_rounds(2, experiments=((BASE, EDGE), (BASE,)))

    assert study.scenario_ids == ("s-base", "s-edge")


def test_the_note_writer_may_cite_every_scenario_of_the_study_once() -> None:
    """A scenario is simulated when its experiment has results; a note about it is stored under
    the scenario's own network (ADR-0032)."""
    study = study_with_rounds(2, experiments=((BASE, EDGE), (BASE,)))

    task = _task(study, {"s-base": _scenario("s-base"), "s-edge": _scenario("s-edge", "derived-1")})

    assert task.scenarios == (
        NoteScenario("s-base", BASE_ARM, ExperimentRole.BASELINE, "reference", True, NET),
        NoteScenario(
            "s-edge", "edge", ExperimentRole.TREATMENT, "the new edge", False, "derived-1"
        ),
    )


def test_a_scenario_of_the_study_that_is_not_stored_has_no_note_task() -> None:
    study = study_with_rounds(experiments=((BASE, EDGE),))

    with pytest.raises(ValueError, match="scenario 's-edge' of the study is not stored"):
        _task(study, {"s-base": _scenario("s-base")})


def _arms_question() -> Question:
    return Question(
        text="does the new J7-J9 edge relieve E12, and what if lane 1 closes?",
        intent=Intent.COMPARE,
        arms=(
            Arm("edge", topology_changes=(AddEdge("J7", "J9", lanes=2, speed=13.9),)),
            Arm("closure", interventions=(static_intervention(),)),
        ),
        context_tags=frozenset({"peak"}),
    )


def test_an_arm_not_realised_that_keeps_the_topology_is_cited_by_its_predicted_id() -> None:
    """The id is the one the Scenario Builder would give the arm on the base scenario's network
    and demand (ADR-0026), and a note about it is stored under that network even when the study
    also has a derived network. An arm that changes the topology has no predicted id."""
    study = study_with_rounds(question=_arms_question(), experiments=((BASE,),))

    task = _task(study, {"s-base": _scenario("s-base")})

    predicted = scenario_id_for(NET, DEMAND, (static_intervention(),), {"peak"})
    assert [(s.scenario_id, s.arm, s.simulated, s.network_id) for s in task.scenarios] == [
        ("s-base", BASE_ARM, True, NET),
        (predicted, "closure", False, NET),
    ]
    assert task.scenarios[1].role is ExperimentRole.TREATMENT


def test_a_realised_arm_is_cited_by_its_scenario_not_by_a_prediction() -> None:
    closure = Experiment("s-closure", "closure", ExperimentRole.TREATMENT, "the closure", 3)
    study = study_with_rounds(question=_arms_question(), experiments=((BASE, closure),))

    task = _task(study, {"s-base": _scenario("s-base"), "s-closure": _scenario("s-closure")})

    assert [s.scenario_id for s in task.scenarios] == ["s-base", "s-closure"]


def test_a_study_without_a_base_experiment_predicts_no_arm() -> None:
    study = study_with_rounds(question=_arms_question(), experiments=((EDGE,),))

    task = _task(study, {"s-edge": _scenario("s-edge", "derived-1")})

    assert [s.scenario_id for s in task.scenarios] == ["s-edge"]
