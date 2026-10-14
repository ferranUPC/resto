"""`ScenarioPromoter` (E2.2, E2.3; ADR-0001, ADR-0042 §5): a Scenario Builder draft is accepted
only if the demand belongs to the network, a derived demand of a `demand_scale` intervention does
too, and every intervention target exists on the network. The context carries the loaded network,
demands and network query, so no test needs a repository or a runner."""

from __future__ import annotations

from dataclasses import replace

import pytest

from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.network_query import NetworkQuery
from resto.application.promoters.scenario import ScenarioContext, ScenarioPromoter
from resto.application.promotion import Blame, DraftRejected, RunWithoutDraft
from resto.domain.entities.demand import Demand
from resto.domain.entities.scenario import Scenario
from resto.domain.entities.simulation_result import RunMode
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.condition import Condition, Metric, Operator
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.mechanism import (
    RegenerateDemandMechanism,
    ScriptMechanism,
    StaticFileMechanism,
)
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import ScenarioTask
from resto.domain.value_objects.time_window import TimeWindow
from resto.domain.value_objects.traci_script import (
    Action,
    AtTime,
    CloseLane,
    OpenLane,
    Rule,
    SetSpeed,
    SetTlsProgram,
    TraciScript,
    Trigger,
    When,
)
from tests.unit.application._doubles import StubNetworkQuery
from tests.unit.domain._fixtures import (
    artifact,
    dynamic_intervention,
    scenario_draft,
    static_intervention,
    traci_script,
)
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network

TASK = ScenarioTask(
    network_id="abc123",
    demand_id="t1",
    interventions=(static_intervention(),),
    context_tags=frozenset({"peak"}),
)
LANE_QUERY = StubNetworkQuery(lanes={("E12", 1)})
# Worked out once from the inputs above and pinned, so a change to the id rule shows up here.
EXPECTED_ID = "d8f5745d41cd0a29939ad3a5f5f9142d1cb3cde260642dc03929a1f5e37ace10"


def draft() -> ScenarioDraft:
    return scenario_draft(
        mechanisms=(StaticFileMechanism(file_kind="rerouter", path=artifact("r.add.xml").path),),
        additional_files=(artifact("r.add.xml", "a1", "additional"),),
    )


def demand_scale_draft() -> ScenarioDraft:
    return scenario_draft(
        interventions=(
            Intervention(
                type=InterventionType.DEMAND_SCALE, target=None, window=TimeWindow(0, 3600)
            ),
        ),
        mechanisms=(RegenerateDemandMechanism(demand_id="derived1"),),
        additional_files=(),
    )


def derived_demand(**changes: object) -> Demand:
    return replace(
        sample_demand(),
        demand_id="derived1",
        trips=artifact("scaled.trips.xml", "derived1", "trips"),
        derived_from=sample_demand().demand_id,
        **changes,  # type: ignore[arg-type]
    )


def run(
    output: ScenarioDraft | None, stop_reason: StopReason = StopReason.OUTPUT
) -> AgentRun[ScenarioDraft]:
    return AgentRun(output=output, tool_calls=(), usage=Usage(), stop_reason=stop_reason)


def promote(
    output: ScenarioDraft | None,
    *,
    demands: tuple[Demand, ...] = (sample_demand(),),
    query: NetworkQuery = LANE_QUERY,
    stop_reason: StopReason = StopReason.OUTPUT,
) -> Scenario:
    context = ScenarioContext(
        task=TASK,
        network=sample_network(),
        demands={d.demand_id: d for d in demands},
        query=query,
    )
    return ScenarioPromoter().promote(run(output, stop_reason), context)


def test_a_valid_draft_becomes_the_scenario_of_the_request() -> None:
    scenario = promote(draft())

    assert scenario.scenario_id == EXPECTED_ID
    assert scenario.network_id == "abc123"
    assert scenario.demand_id == "t1"
    assert scenario.interventions == (static_intervention(),)
    assert scenario.context_tags == frozenset({"peak"})


def test_the_content_hash_is_not_the_scenario_id() -> None:
    assert promote(draft()).content_hash != EXPECTED_ID


def test_a_budget_stop_reason_is_never_promoted() -> None:
    with pytest.raises(RunWithoutDraft):
        promote(None, stop_reason=StopReason.BUDGET)


def test_a_missing_output_on_a_reported_output_stop_reason_is_never_promoted() -> None:
    with pytest.raises(RunWithoutDraft):
        promote(None)


def test_an_unknown_demand_is_rejected() -> None:
    with pytest.raises(DraftRejected, match="unknown demand_id 't1'"):
        promote(draft(), demands=())


def test_a_demand_from_a_different_network_is_rejected() -> None:
    with pytest.raises(DraftRejected, match="belongs to network 'other-network'"):
        promote(draft(), demands=(replace(sample_demand(), network_id="other-network"),))


def test_an_intervention_target_unknown_to_the_network_is_rejected_on_the_users_account() -> None:
    with pytest.raises(DraftRejected, match="unknown lane") as rejected:
        promote(draft(), query=StubNetworkQuery())

    assert rejected.value.blame is Blame.USER


def test_a_demand_rejection_comes_before_a_target_rejection() -> None:
    with pytest.raises(DraftRejected, match="unknown demand_id") as rejected:
        promote(draft(), demands=(), query=StubNetworkQuery())

    assert rejected.value.blame is Blame.AGENT


def test_a_demand_scale_mechanism_makes_the_scenario_reference_the_derived_demand() -> None:
    scenario = promote(demand_scale_draft(), demands=(sample_demand(), derived_demand()))

    assert scenario.demand_id == "derived1"


def test_the_scenario_id_keeps_the_requests_own_demand() -> None:
    scaled = demand_scale_draft()

    scenario = promote(scaled, demands=(sample_demand(), derived_demand()))

    assert scenario.scenario_id == scenario_id_for(
        "abc123", "t1", scaled.interventions, frozenset({"peak"})
    )


def test_an_unknown_derived_demand_is_rejected() -> None:
    with pytest.raises(DraftRejected, match="unknown derived demand_id 'derived1'"):
        promote(demand_scale_draft())


def test_a_derived_demand_from_a_different_network_is_rejected() -> None:
    with pytest.raises(DraftRejected, match="derived demand .* belongs to network 'other-network'"):
        promote(
            demand_scale_draft(),
            demands=(sample_demand(), derived_demand(network_id="other-network")),
        )


def scripted_draft(*rules: Rule) -> ScenarioDraft:
    return scenario_draft(
        interventions=(dynamic_intervention(),),
        mechanisms=(ScriptMechanism(),),
        additional_files=(),
        script=TraciScript(rules=rules),
    )


def _rule(action: Action, trigger: Trigger | None = None) -> Rule:
    return Rule(trigger=trigger or AtTime(t=60.0), action=action)


SCRIPT_QUERY = StubNetworkQuery(edges={"E12", "E13"}, lanes={("E12", 1)}, tls={"J4"})


def test_a_scripted_scenario_is_promoted_with_its_rules() -> None:
    script = traci_script()

    scenario = promote(scripted_draft(*script.rules), query=SCRIPT_QUERY)

    assert scenario.traci_script == script
    assert scenario.run_mode is RunMode.ONLINE


def test_the_content_hash_follows_the_rules() -> None:
    close = scripted_draft(_rule(CloseLane("E12", 1)))
    open_ = scripted_draft(_rule(OpenLane("E12", 1)))

    first = promote(close, query=SCRIPT_QUERY).content_hash
    again = promote(close, query=SCRIPT_QUERY).content_hash

    assert first == again
    assert first != promote(open_, query=SCRIPT_QUERY).content_hash


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        (_rule(CloseLane("E12", 5)), "unknown lane 'E12_5'"),
        (_rule(OpenLane("E13", 0)), "unknown lane 'E13_0'"),
        (_rule(SetSpeed("E99", 5.0)), "unknown edge 'E99'"),
        (_rule(SetTlsProgram("J9", "night")), "unknown tls 'J9'"),
        (
            _rule(
                CloseLane("E12", 1),
                When(Condition(Metric.OCCUPANCY, "E99", Operator.GT, 0.8)),
            ),
            "unknown edge 'E99' in a rule condition",
        ),
    ],
)
def test_a_rule_naming_something_the_network_lacks_is_rejected(rule: Rule, message: str) -> None:
    with pytest.raises(DraftRejected, match=message) as rejected:
        promote(scripted_draft(rule), query=SCRIPT_QUERY)

    assert rejected.value.blame is Blame.USER


def test_an_action_variant_the_promoter_does_not_know_fails_loudly() -> None:
    rule = _rule(SetSpeed("E12", 5.0))
    object.__setattr__(rule, "action", "not an action")

    with pytest.raises(AssertionError):
        promote(scripted_draft(rule), query=SCRIPT_QUERY)


def test_a_context_whose_network_is_not_the_tasks_is_refused() -> None:
    with pytest.raises(ValueError, match="network"):
        ScenarioContext(
            task=replace(TASK, network_id="other"),
            network=sample_network(),
            demands={},
            query=LANE_QUERY,
        )
