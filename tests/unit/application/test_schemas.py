"""Round-trip + invariant tests through pydantic TypeAdapters (DoD §4.9)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from resto.application.schemas import (
    ADAPTERS,
    json_schemas,
    render_json_schemas,
    write_json_schemas,
)
from resto.domain.entities.scenario import Scenario
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import ScriptMechanism, StaticFileMechanism
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.topology_modification import AddEdge
from tests.unit.domain._fixtures import (
    artifact,
    demand_draft,
    dynamic_intervention,
    expert_note_draft,
    network_draft,
    runnable_script,
    scenario_draft,
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


@pytest.mark.parametrize(
    ("name", "builder"),
    [
        ("NetworkDraft", network_draft),
        ("DemandDraft", demand_draft),
        ("ScenarioDraft", scenario_draft),
        ("ExpertNoteDraft", expert_note_draft),
    ],
)
def test_every_draft_round_trips_through_its_adapter(name: str, builder) -> None:
    ta = ADAPTERS[name]
    draft = builder()
    assert ta.validate_json(ta.dump_json(draft)) == draft


def test_draft_invariants_fire_during_validation() -> None:
    """Promotion step (1): this is what turns a bad agent output into the one retry of §1.2."""
    ta = ADAPTERS["NetworkDraft"]
    payload = ta.dump_python(network_draft())
    payload["rationale"] = "   "
    with pytest.raises(ValidationError):
        ta.validate_python(payload)


SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas"


def test_published_schemas_are_in_sync_with_the_code() -> None:
    """The committed schemas are the contract external implementers read (DoD §4.9).

    Regenerate with: python -m resto.application.schemas schemas
    """
    rendered = render_json_schemas()
    assert {p.stem for p in SCHEMA_DIR.glob("*.json")} == set(rendered)
    stale = [name for name, text in rendered.items() if _published(name) != text]
    assert not stale, f"schemas out of date: {stale}"


def _published(name: str) -> str:
    return (SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8")


def test_write_json_schemas_removes_files_for_types_that_no_longer_exist(tmp_path) -> None:
    orphan = tmp_path / "GoneType.json"
    orphan.write_text("{}", encoding="utf-8")
    write_json_schemas(tmp_path)
    assert not orphan.exists()
    assert (tmp_path / "Question.json").exists()
