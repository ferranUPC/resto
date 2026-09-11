"""Round-trip + invariant tests through pydantic TypeAdapters (DoD §4.9)."""

import pytest
from pydantic import ValidationError

from resto.application.schemas import ADAPTERS, json_schemas
from resto.domain.entities.scenario import Scenario
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import ScriptMechanism, StaticFileMechanism
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.domain._fixtures import (
    artifact,
    dynamic_intervention,
    runnable_script,
    static_intervention,
)


def test_every_boundary_type_exports_a_json_schema() -> None:
    schemas = json_schemas()
    assert set(schemas) == set(ADAPTERS)
    assert all("properties" in s for s in schemas.values())


def test_scenario_round_trip_and_discriminated_unions() -> None:
    scenario = Scenario(
        scenario_id="s1",
        network_id="n1",
        demand_id="d1",
        interventions=(static_intervention(), dynamic_intervention()),
        mechanisms=(
            StaticFileMechanism(file_kind="vss", path=artifact("v.add.xml").path),
            ScriptMechanism(),
        ),
        sumocfg=artifact("s1.sumocfg"),
        content_hash="c1",
        traci_script=runnable_script(),
        context_tags=frozenset({"peak", "rain"}),
    )
    ta = ADAPTERS["Scenario"]
    back = ta.validate_json(ta.dump_json(scenario))
    assert back == scenario
    assert isinstance(back.interventions[0].target, LaneTarget)
    assert isinstance(back.mechanisms[1], ScriptMechanism)


def test_domain_invariants_fire_during_validation() -> None:
    ta = ADAPTERS["Scenario"]
    payload = ta.dump_python(
        Scenario(
            scenario_id="s1",
            network_id="n1",
            demand_id="d1",
            interventions=(dynamic_intervention(),),
            mechanisms=(ScriptMechanism(),),
            sumocfg=artifact("s1.sumocfg"),
            content_hash="c1",
            traci_script=runnable_script(),
        )
    )
    payload["traci_script"] = None
    with pytest.raises(ValidationError):
        ta.validate_python(payload)


def test_question_from_llm_json() -> None:
    raw = {
        "text": "what if we add an edge between J7 and J9?",
        "intent": "counterfactual",
        "topology_changes": [
            {
                "kind": "add_edge",
                "from_junction": "J7",
                "to_junction": "J9",
                "lanes": 2,
                "speed": 13.9,
            }
        ],
        "metrics_of_interest": ["delay"],
    }
    q = ADAPTERS["Question"].validate_python(raw)
    assert isinstance(q, Question)
    assert q.intent is Intent.COUNTERFACTUAL
    assert isinstance(q.topology_changes[0], AddEdge)
