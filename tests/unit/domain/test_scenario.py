from typing import Any

import pytest

from resto.domain.entities.scenario import Scenario
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.mechanism import (
    RegenerateDemandMechanism,
    ScriptMechanism,
    StaticFileMechanism,
)
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.domain._fixtures import (
    artifact,
    dynamic_intervention,
    runnable_script,
    static_intervention,
)

STATIC_MECH = StaticFileMechanism(file_kind="rerouter", path=artifact("r.add.xml").path)


def _scenario(**overrides):  # noqa: ANN003, ANN202
    base: dict[str, Any] = dict(
        scenario_id="s1",
        network_id="n1",
        demand_id="d1",
        interventions=(static_intervention(),),
        mechanisms=(STATIC_MECH,),
        sumocfg=artifact("s1.sumocfg"),
        content_hash="c1",
    )
    base.update(overrides)
    return Scenario(**base)


def test_static_scenario_is_batch() -> None:
    assert not _scenario().is_online


def test_dynamic_intervention_requires_script_mechanism_and_script() -> None:
    with pytest.raises(ValueError):
        _scenario(interventions=(dynamic_intervention(),), mechanisms=(STATIC_MECH,))
    with pytest.raises(ValueError):
        _scenario(interventions=(dynamic_intervention(),), mechanisms=(ScriptMechanism(),))
    s = _scenario(
        interventions=(dynamic_intervention(),),
        mechanisms=(ScriptMechanism(),),
        traci_script=runnable_script(),
    )
    assert s.is_online


def test_script_must_pass_lint_and_dry_run() -> None:
    from dataclasses import replace

    with pytest.raises(ValueError):
        _scenario(
            interventions=(dynamic_intervention(),),
            mechanisms=(ScriptMechanism(),),
            traci_script=replace(runnable_script(), dry_run_ok=False),
        )


def test_demand_scale_must_regenerate_demand() -> None:
    scale = Intervention(
        type=InterventionType.DEMAND_SCALE, target=None, window=TimeWindow(0, 3600)
    )
    with pytest.raises(ValueError):
        _scenario(interventions=(scale,), mechanisms=(STATIC_MECH,))
    _scenario(interventions=(scale,), mechanisms=(RegenerateDemandMechanism(demand_id="d2"),))


def test_scenario_id_is_a_request_hash() -> None:
    a = scenario_id_for("n1", "d1", [static_intervention()], {"peak"})
    b = scenario_id_for("n1", "d1", [static_intervention()], ["peak"])
    c = scenario_id_for("n1", "d1", [dynamic_intervention()], ["peak"])
    assert a == b != c
