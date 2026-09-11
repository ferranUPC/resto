import pytest

from resto.domain.value_objects.intervention import Intervention, InterventionType, Strategy
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.domain._fixtures import LANE, dynamic_intervention, static_intervention


def test_requires_exactly_one_of_window_or_condition() -> None:
    with pytest.raises(ValueError):
        Intervention(type=InterventionType.LANE_CLOSURE, target=LANE)


def test_permanent_edge_closure_is_rejected_as_topology_change() -> None:
    with pytest.raises(ValueError, match="TopologyModification"):
        Intervention(type=InterventionType.EDGE_CLOSURE, target=LANE)


def test_demand_scale_must_not_have_a_target() -> None:
    with pytest.raises(ValueError):
        Intervention(type=InterventionType.DEMAND_SCALE, target=LANE, window=TimeWindow(0, 3600))


def test_custom_requires_description() -> None:
    with pytest.raises(ValueError):
        Intervention(type=InterventionType.CUSTOM, target=None, window=TimeWindow(0, 3600))
    custom = Intervention(
        type=InterventionType.CUSTOM,
        target=None,
        window=TimeWindow(0, 3600),
        description="adaptive signals on corridor C",
    )
    assert custom.strategy is Strategy.STATIC


def test_strategy_follows_window_or_condition() -> None:
    assert static_intervention().strategy is Strategy.STATIC
    assert dynamic_intervention().strategy is Strategy.DYNAMIC


def test_time_window_must_be_ordered() -> None:
    with pytest.raises(ValueError):
        TimeWindow(10, 10)
