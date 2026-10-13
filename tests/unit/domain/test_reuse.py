"""What a study reuses instead of running or building again (ADR-0041 §6): the rules decide over
values the Executor loaded, so no repository appears here."""

from dataclasses import replace

from resto.domain.entities.simulation_result import RunMode, RunStatus, SimulationResult
from resto.domain.services.reuse import (
    accepts_found_demand,
    accepts_found_network,
    reused_results,
    reused_scenario_results,
    seeds_to_run,
)
from resto.domain.value_objects.outcomes import Found
from tests.unit.domain._fixtures import DEMAND, NET
from tests.unit.domain._samples import demand, network, scenario, simulation_result


def _result(seed: int, status: RunStatus = RunStatus.OK) -> SimulationResult:
    ok = simulation_result()
    return replace(
        ok,
        result_id=f"r{seed}",
        seed=seed,
        mode=RunMode.BATCH,
        status=status,
        applied_actions=(),
        error="SUMO crashed" if status is RunStatus.FAILED else None,
    )


def test_a_seed_with_a_stored_ok_result_is_not_run_again() -> None:
    """No **Redundant simulation**: the stored ok result is reused."""
    stored = (_result(1),)

    assert seeds_to_run((1, 2, 3), stored) == (2, 3)
    assert reused_results((1, 2, 3), stored) == {1: stored[0]}


def test_a_seed_whose_stored_result_failed_is_run_again() -> None:
    stored = (_result(1, RunStatus.FAILED), _result(2))

    assert seeds_to_run((1, 2), stored) == (1,)
    assert reused_results((1, 2), stored) == {2: stored[1]}


def test_the_seeds_without_any_stored_result_are_run_in_the_steps_order() -> None:
    assert seeds_to_run((3, 1, 2), ()) == (3, 1, 2)
    assert reused_results((3, 1, 2), ()) == {}


def test_a_stored_result_for_a_seed_the_step_does_not_ask_for_is_not_reused() -> None:
    stored = (_result(9),)

    assert seeds_to_run((1,), stored) == (1,)
    assert reused_results((1,), stored) == {}


def test_an_online_result_does_not_stand_for_the_batch_run_a_step_asks_for() -> None:
    online = replace(_result(1), mode=RunMode.ONLINE)

    assert seeds_to_run((1,), (online,)) == (1,)


def test_a_stored_scenario_with_ok_results_is_reused_with_their_ids_by_seed() -> None:
    """Nothing goes to the Scenario Builder (ADR-0037 §5)."""
    stored = (_result(3), _result(1, RunStatus.FAILED), _result(2))

    assert reused_scenario_results(scenario(), stored) == ("r2", "r3")


def test_a_stored_scenario_whose_runs_all_failed_is_built_again() -> None:
    assert reused_scenario_results(scenario(), (_result(1, RunStatus.FAILED),)) == ()


def test_a_scenario_that_is_not_stored_is_built() -> None:
    assert reused_scenario_results(None, (_result(1),)) == ()


def test_a_found_network_is_accepted_when_it_is_stored() -> None:
    assert accepts_found_network(Found(NET), network())


def test_a_found_network_that_is_not_stored_is_refused() -> None:
    assert not accepts_found_network(Found("ghost"), None)


def test_a_found_network_is_refused_when_what_was_loaded_is_another_network() -> None:
    assert not accepts_found_network(Found("ghost"), network())


def test_a_found_demand_on_the_steps_network_is_accepted() -> None:
    assert accepts_found_demand(Found(DEMAND), demand(), network_id=NET)


def test_a_found_demand_that_is_not_stored_is_refused() -> None:
    assert not accepts_found_demand(Found("ghost"), None, network_id=NET)


def test_a_found_demand_of_another_network_is_refused() -> None:
    assert not accepts_found_demand(Found(DEMAND), demand(), network_id="other-network")


def test_a_found_demand_is_refused_when_what_was_loaded_is_another_demand() -> None:
    assert not accepts_found_demand(Found("ghost"), demand(), network_id=NET)
