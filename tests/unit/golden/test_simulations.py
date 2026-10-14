"""The simulations part of the Expected outcome: essential simulations, the bound, redundancy."""

from __future__ import annotations

import pytest
from golden.framework import (
    EssentialSimulation,
    ExpectedOutcome,
    GoldenPath,
    InterventionPredicate,
    ObservedOutcome,
    ObservedSimulation,
    ParamBound,
    PriorState,
    Severity,
    SimulationsExpectation,
    StoredScenario,
    check,
    compare_outcome,
)
from golden.paths.gp1 import PATH as GP1
from golden.paths.gp5 import GP5
from golden.paths.gp9 import GP9
from golden.setups.fake import AgentScript, FakeSetup

from resto.domain.entities.study import StudyResolution
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.application._world import (
    BASELINE_PLAN,
    CLOSURE,
    DESCRIBE,
    WHAT_IF,
    answers,
)

SCALED = EssentialSimulation(
    (
        InterventionPredicate(
            InterventionType.DEMAND_SCALE, params=(ParamBound("factor", 1.3, 1.8),)
        ),
    )
)
BASE = EssentialSimulation()
CLOSES_LANE = EssentialSimulation(
    (InterventionPredicate(InterventionType.LANE_CLOSURE, CLOSURE.target),)
)


def _scaled(factor: float) -> Intervention:
    return Intervention(
        InterventionType.DEMAND_SCALE, None, {"factor": factor}, window=TimeWindow(0.0, 300.0)
    )


def _sim(
    *interventions: Intervention,
    sid: str = "s",
    seeds: tuple[int, ...] = (1, 2),
    reused: bool = False,
    demand: tuple[str, ...] = ("parameters",),
) -> ObservedSimulation:
    return ObservedSimulation(sid, interventions, demand, seeds, reused)


def _diff(expectation: SimulationsExpectation, *sims: ObservedSimulation) -> str:
    diff = compare_outcome(
        ExpectedOutcome(simulations=expectation),
        ObservedOutcome(StudyResolution.COMPLETED, None, sims),
    )
    return "ok" if diff.ok else diff.render()


# -- the comparator ----------------------------------------------------------------------------


@pytest.mark.parametrize("factor", [1.3, 1.4, 1.65, 1.8])
def test_a_demand_scaled_inside_the_range_satisfies_the_essential_simulation(factor: float) -> None:
    assert _diff(SimulationsExpectation((SCALED,), 1), _sim(_scaled(factor))) == "ok"


@pytest.mark.parametrize("factor", [1.2999, 1.8001, 3.0])
def test_a_demand_scaled_outside_the_range_fails_and_names_the_simulations(factor: float) -> None:
    text = _diff(SimulationsExpectation((SCALED,), 1), _sim(_scaled(factor)))

    assert "simulations" in text and "missing" in text and "demand_scale" in text


def test_a_missing_essential_simulation_fails() -> None:
    text = _diff(SimulationsExpectation((BASE, CLOSES_LANE), 2), _sim())

    assert "simulations" in text and "lane_closure" in text


def test_the_base_predicate_does_not_match_a_scenario_with_interventions() -> None:
    assert "missing" in _diff(SimulationsExpectation((BASE,), 1), _sim(CLOSURE))


def test_a_target_that_differs_does_not_match() -> None:
    elsewhere = EssentialSimulation(
        (InterventionPredicate(InterventionType.LANE_CLOSURE, LaneTarget("E99", 0)),)
    )

    assert "missing" in _diff(SimulationsExpectation((elsewhere,), 1), _sim(CLOSURE))


def test_the_demand_source_kind_is_matched() -> None:
    wants_db = EssentialSimulation(demand_source="historical_db")

    assert "missing" in _diff(SimulationsExpectation((wants_db,), 1), _sim())
    assert _diff(SimulationsExpectation((wants_db,), 1), _sim(demand=("historical_db",))) == "ok"


def test_more_new_simulations_than_the_bound_fail_even_with_the_essential_ones() -> None:
    sims = (_sim(sid="a"), _sim(CLOSURE, sid="b"), _sim(_scaled(1.5), sid="c"))

    text = _diff(SimulationsExpectation((BASE, CLOSES_LANE), 2), *sims)

    assert "new simulations" in text and "at most 2" in text and "observed 3" in text


def test_a_reused_result_is_not_a_new_simulation() -> None:
    sims = (_sim(sid="a", reused=True), _sim(CLOSURE, sid="b", reused=True))

    assert _diff(SimulationsExpectation((BASE, CLOSES_LANE), 0), *sims) == "ok"


def test_the_margin_adds_to_the_bound() -> None:
    expectation = SimulationsExpectation((BASE,), 0, margin=1, margin_reason="a retry is fine")

    assert _diff(expectation, _sim()) == "ok"
    assert "new simulations" in _diff(expectation, _sim(sid="a"), _sim(CLOSURE, sid="b"))


def test_a_margin_without_a_stated_reason_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="reason"):
        SimulationsExpectation((BASE,), 1, margin=1)
    with pytest.raises(ValueError, match="reason"):
        SimulationsExpectation((BASE,), 1, margin=1, margin_reason="  ")


def test_a_negative_bound_or_margin_is_rejected() -> None:
    with pytest.raises(ValueError):
        SimulationsExpectation((), -1)
    with pytest.raises(ValueError):
        SimulationsExpectation((), 0, margin=-1, margin_reason="x")


def test_the_same_scenario_with_the_same_seeds_twice_is_reported_as_redundant() -> None:
    sims = (_sim(sid="a"), _sim(sid="a", reused=True))

    text = _diff(SimulationsExpectation((BASE,), 1), *sims)

    assert "redundant" in text and "a" in text


def test_the_same_scenario_with_other_seeds_is_not_redundant() -> None:
    sims = (_sim(sid="a", seeds=(1,)), _sim(sid="a", seeds=(2,), reused=True))

    assert _diff(SimulationsExpectation((BASE,), 1), *sims) == "ok"


def test_the_severity_of_the_part_is_data() -> None:
    soft = SimulationsExpectation((CLOSES_LANE,), 0, severity=Severity.WARNING)

    diff = compare_outcome(
        ExpectedOutcome(simulations=soft), ObservedOutcome(StudyResolution.COMPLETED, None, ())
    )

    assert diff.ok and len(diff.warnings) == 1


def test_a_range_that_is_upside_down_is_rejected() -> None:
    with pytest.raises(ValueError):
        ParamBound("factor", 2.0, 1.0)


# -- through the real use cases ----------------------------------------------------------------

BASE_ONLY = AgentScript(question=DESCRIBE, plans=(BASELINE_PLAN,), expert=(answers(),))


def _path(expectation: SimulationsExpectation, prior: PriorState | None = None) -> GoldenPath:
    return GoldenPath(
        "throwaway", WHAT_IF.text, ExpectedOutcome(simulations=expectation), prior or PriorState()
    )


def _fake(path: GoldenPath) -> str:
    diff = check(FakeSetup({"throwaway": BASE_ONLY}), path)
    return "ok" if diff.ok else diff.render()


def test_a_new_base_simulation_meets_a_bound_of_one() -> None:
    assert _fake(_path(SimulationsExpectation((BASE,), 1))) == "ok"


def test_a_new_simulation_breaks_a_bound_of_zero() -> None:
    assert "new simulations" in _fake(_path(SimulationsExpectation((BASE,), 0)))


def test_a_stored_base_is_reused_and_meets_a_bound_of_zero() -> None:
    prior = PriorState((StoredScenario(),))

    assert _fake(_path(SimulationsExpectation((BASE,), 0), prior)) == "ok"


def test_an_essential_simulation_the_study_never_ran_fails() -> None:
    assert "lane_closure" in _fake(_path(SimulationsExpectation((BASE, CLOSES_LANE), 2)))


@pytest.mark.parametrize("path", [GP1, GP5, GP9], ids=lambda p: p.name)
def test_the_migrated_paths_state_a_bound_of_zero_and_pass(path: GoldenPath) -> None:
    assert isinstance(path.expected, ExpectedOutcome)
    assert path.expected.simulations is not None and path.expected.simulations.max_new == 0
    diff = check(FakeSetup(), path)
    assert diff.ok, diff.render()


def test_gp5_essentials_are_the_base_and_the_closure() -> None:
    assert isinstance(GP5.expected, ExpectedOutcome) and GP5.expected.simulations is not None
    assert len(GP5.expected.simulations.essential) == 2
