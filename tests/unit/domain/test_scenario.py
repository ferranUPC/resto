from pathlib import Path

import pytest

from resto.domain.entities.scenario import Scenario
from resto.domain.entities.traci_plan import TraciPlan, TraciPlanEntry
from resto.domain.value_objects.intervention import Intervention, InterventionType, Strategy
from resto.domain.value_objects.intervention_target import LaneTarget

_LANE_TARGET = LaneTarget(edge_id="E12", lane_index=1)


def _static_intervention() -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=_LANE_TARGET,
        window=(7 * 3600, 10 * 3600),
    )


def _dynamic_intervention() -> Intervention:
    return Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=_LANE_TARGET,
        condition="occupancy(E12) > 0.8",
    )


def test_intervention_requires_exactly_one_of_window_or_condition() -> None:
    with pytest.raises(ValueError):
        Intervention(type=InterventionType.LANE_CLOSURE, target=_LANE_TARGET)


def test_intervention_demand_scale_must_not_have_a_target() -> None:
    with pytest.raises(ValueError):
        Intervention(type=InterventionType.DEMAND_SCALE, target=_LANE_TARGET, window=(0, 3600))


def test_intervention_non_demand_scale_requires_a_target() -> None:
    with pytest.raises(ValueError):
        Intervention(type=InterventionType.LANE_CLOSURE, target=None, window=(0, 3600))


def test_intervention_strategy_matches_window_or_condition() -> None:
    assert _static_intervention().strategy is Strategy.STATIC
    assert _dynamic_intervention().strategy is Strategy.DYNAMIC


def test_scenario_with_dynamic_intervention_requires_traci_plan() -> None:
    with pytest.raises(ValueError):
        Scenario(
            scenario_id="s1",
            network_id="net-1",
            demand_id="dem-1",
            sumocfg_path=Path("s1.sumocfg"),
            additional_files=(),
            interventions=(_dynamic_intervention(),),
            context_tags=frozenset({"peak"}),
            seed=1,
            content_hash="abc123",
        )


def test_scenario_with_dynamic_intervention_and_traci_plan_is_valid() -> None:
    plan = TraciPlan(
        entries=(
            TraciPlanEntry(
                trigger="when(occupancy,E12,>,0.8)",
                action="close_lane",
                action_params={"lane_id": "E12_lane_1"},
            ),
        ),
        poll_interval=5.0,
    )
    scenario = Scenario(
        scenario_id="s1",
        network_id="net-1",
        demand_id="dem-1",
        sumocfg_path=Path("s1.sumocfg"),
        additional_files=(),
        interventions=(_dynamic_intervention(),),
        context_tags=frozenset({"peak"}),
        seed=1,
        content_hash="abc123",
        traci_plan=plan,
    )
    assert scenario.traci_plan is plan
