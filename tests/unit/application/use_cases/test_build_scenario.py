"""`build_scenario` promotion (E2.2, ADR-0001): semantic checks, dedupe on an existing
scenario_id, and that a Budget/ERROR stop reason never gets promoted."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Any

import pytest

from resto.adapters.persistence.memory import (
    InMemoryDemandRepository,
    InMemoryNetworkRepository,
    InMemoryScenarioRepository,
)
from resto.application.ports.llm import AgentRun, StopReason
from resto.application.ports.sumo import RunOutput
from resto.application.use_cases.build_scenario import (
    BuilderRunFailed,
    ScenarioSemanticError,
    build_scenario,
)
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.artifact_ref import ArtifactRef
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.mechanism import RegenerateDemandMechanism, StaticFileMechanism
from resto.domain.value_objects.step_record import Usage
from resto.domain.value_objects.tasks import ScenarioTask
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.domain._fixtures import artifact, scenario_draft, static_intervention
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network


class StubNetworkQuery:
    def __init__(
        self,
        edges: AbstractSet[str] = frozenset(),
        lanes: AbstractSet[tuple[str, int]] = frozenset(),
    ) -> None:
        self._edges = edges
        self._lanes = lanes

    def has_edge(self, edge_id: str) -> bool:
        return edge_id in self._edges

    def has_lane(self, edge_id: str, lane_index: int) -> bool:
        return (edge_id, lane_index) in self._lanes

    def has_tls(self, tls_id: str) -> bool:
        raise AssertionError("not used by this intervention")

    def get_edge(self, edge_id: str) -> Mapping[str, Any]:
        raise AssertionError("not used")

    def get_lanes(self, edge_id: str) -> Sequence[Mapping[str, Any]]:
        raise AssertionError("not used")

    def get_neighbours(self, edge_id: str) -> Sequence[str]:
        raise AssertionError("not used")

    def shortest_path(self, from_edge: str, to_edge: str) -> Sequence[str]:
        raise AssertionError("not used")

    def edges_in_bbox(self, bbox: tuple[float, float, float, float]) -> Sequence[str]:
        raise AssertionError("not used")

    def capacity_estimate(self, edge_id: str) -> float:
        raise AssertionError("not used")

    def get_tls(self, tls_id: str) -> Mapping[str, Any]:
        raise AssertionError("not used")


class FakeRunner:
    def __init__(self, outputs: list[RunOutput]) -> None:
        self._outputs = outputs
        self.calls: list[tuple[ArtifactRef, int, Path]] = []

    def run_batch(self, sumocfg: ArtifactRef, seed: int, out_dir: Path) -> RunOutput:
        self.calls.append((sumocfg, seed, out_dir))
        return self._outputs.pop(0)

    def run_online(
        self, sumocfg: ArtifactRef, script: ArtifactRef, seed: int, out_dir: Path
    ) -> RunOutput:
        raise AssertionError("not used")


def ok_output() -> RunOutput:
    from resto.domain.value_objects.kpis import Kpis

    return RunOutput(
        ok=True,
        error=None,
        artifacts=(artifact("run.sumocfg", "cfg1", "sumocfg"),),
        wall_clock_s=0.5,
        kpis=Kpis(mean_delay=1.0, mean_travel_time=1.0, teleports=0, departed=1, arrived=1),
    )


def failed_output() -> RunOutput:
    return RunOutput(
        ok=False,
        error="Error: unknown edge in additional file",
        artifacts=(),
        wall_clock_s=0.1,
    )


TASK = ScenarioTask(
    network_id="abc123",
    demand_id="t1",
    interventions=(static_intervention(),),
    context_tags=frozenset({"peak"}),
)
LANE_QUERY = StubNetworkQuery(lanes={("E12", 1)})


def draft():  # noqa: ANN201
    return scenario_draft(
        mechanisms=(StaticFileMechanism(file_kind="rerouter", path=artifact("r.add.xml").path),),
        additional_files=(artifact("r.add.xml", "a1", "additional"),),
    )


def env(*, runner_outputs=None, networks=None, demands=None, scenarios=None, query=None):  # noqa: ANN001, ANN201
    return dict(
        networks=networks if networks is not None else _networks_with(sample_network()),
        demands=demands if demands is not None else _demands_with(sample_demand()),
        scenarios=scenarios if scenarios is not None else InMemoryScenarioRepository(),
        network_query_factory=lambda path: query or LANE_QUERY,  # noqa: ARG005
        runner=FakeRunner(runner_outputs if runner_outputs is not None else [ok_output()]),
        out_dir=Path("/tmp/resto-test-build-scenario"),
    )


def _networks_with(network):  # noqa: ANN001, ANN201
    repo = InMemoryNetworkRepository()
    repo.store(network)
    return repo


def _demands_with(demand):  # noqa: ANN001, ANN201
    repo = InMemoryDemandRepository()
    repo.store(demand)
    return repo


def agent_run(output=None, stop_reason=StopReason.OUTPUT):  # noqa: ANN001, ANN201
    return AgentRun(output=output, tool_calls=(), usage=Usage(), stop_reason=stop_reason)


def test_promotes_a_valid_draft_and_stores_it(tmp_path: Path) -> None:
    kwargs = env()
    kwargs["out_dir"] = tmp_path

    scenario = build_scenario(TASK, agent_run(output=draft()), **kwargs)

    expected_id = scenario_id_for("abc123", "t1", (static_intervention(),), frozenset({"peak"}))
    assert scenario.scenario_id == expected_id
    assert kwargs["scenarios"].get(expected_id) == scenario
    assert scenario.interventions == (static_intervention(),)


def test_an_existing_scenario_is_returned_without_touching_sumo_again(tmp_path: Path) -> None:
    kwargs = env()
    kwargs["out_dir"] = tmp_path
    runner = kwargs["runner"]
    runner._outputs = [ok_output(), ok_output()]

    first = build_scenario(TASK, agent_run(output=draft()), **kwargs)
    second = build_scenario(TASK, agent_run(output=draft()), **kwargs)

    assert second == first
    assert len(runner.calls) == 1


def test_a_budget_stop_reason_is_never_promoted() -> None:
    with pytest.raises(BuilderRunFailed):
        build_scenario(TASK, agent_run(output=None, stop_reason=StopReason.BUDGET), **env())


def test_a_missing_output_on_a_reported_output_stop_reason_is_never_promoted() -> None:
    with pytest.raises(BuilderRunFailed):
        build_scenario(TASK, agent_run(output=None, stop_reason=StopReason.OUTPUT), **env())


def test_unknown_network_is_rejected() -> None:
    with pytest.raises(ScenarioSemanticError):
        build_scenario(TASK, agent_run(output=draft()), **env(networks=InMemoryNetworkRepository()))


def test_unknown_demand_is_rejected() -> None:
    with pytest.raises(ScenarioSemanticError):
        build_scenario(TASK, agent_run(output=draft()), **env(demands=InMemoryDemandRepository()))


def test_a_demand_from_a_different_network_is_rejected() -> None:
    from dataclasses import replace

    mismatched = _demands_with(replace(sample_demand(), network_id="other-network"))
    with pytest.raises(ScenarioSemanticError):
        build_scenario(TASK, agent_run(output=draft()), **env(demands=mismatched))


def test_an_intervention_target_unknown_to_the_network_is_rejected() -> None:
    with pytest.raises(ScenarioSemanticError):
        build_scenario(TASK, agent_run(output=draft()), **env(query=StubNetworkQuery()))


def test_sumo_rejecting_the_cfg_is_a_semantic_error_and_nothing_is_stored(tmp_path: Path) -> None:
    kwargs = env(runner_outputs=[failed_output()])
    kwargs["out_dir"] = tmp_path

    with pytest.raises(ScenarioSemanticError):
        build_scenario(TASK, agent_run(output=draft()), **kwargs)

    expected_id = scenario_id_for("abc123", "t1", (static_intervention(),), frozenset({"peak"}))
    assert kwargs["scenarios"].get(expected_id) is None


def test_content_hash_differs_from_scenario_id(tmp_path: Path) -> None:
    kwargs = env()
    kwargs["out_dir"] = tmp_path
    scenario = build_scenario(TASK, agent_run(output=draft()), **kwargs)
    assert scenario.content_hash != scenario.scenario_id


# --- demand_scale (E2.3) ------------------------------------------------------------------------


def demand_scale_intervention() -> Intervention:
    return Intervention(
        type=InterventionType.DEMAND_SCALE, target=None, window=TimeWindow(0, 3600)
    )


def derived_demand():  # noqa: ANN201
    from dataclasses import replace

    return replace(
        sample_demand(),
        demand_id="derived1",
        trips=artifact("scaled.trips.xml", "derived1", "trips"),
        derived_from=sample_demand().demand_id,
    )


def demand_scale_draft():  # noqa: ANN201
    return scenario_draft(
        interventions=(demand_scale_intervention(),),
        mechanisms=(RegenerateDemandMechanism(demand_id="derived1"),),
        additional_files=(),
    )


def test_a_demand_scale_mechanism_makes_the_scenario_reference_the_derived_demand(
    tmp_path: Path,
) -> None:
    kwargs = env()
    kwargs["out_dir"] = tmp_path
    kwargs["demands"].store(derived_demand())

    scenario = build_scenario(TASK, agent_run(output=demand_scale_draft()), **kwargs)

    assert scenario.demand_id == "derived1"
    expected_id = scenario_id_for(
        "abc123", "t1", (demand_scale_intervention(),), frozenset({"peak"})
    )
    assert scenario.scenario_id == expected_id  # request identity keeps the task's own demand_id


def test_an_unknown_derived_demand_is_rejected(tmp_path: Path) -> None:
    kwargs = env()
    kwargs["out_dir"] = tmp_path

    with pytest.raises(ScenarioSemanticError):
        build_scenario(TASK, agent_run(output=demand_scale_draft()), **kwargs)


def test_a_derived_demand_from_a_different_network_is_rejected(tmp_path: Path) -> None:
    from dataclasses import replace

    kwargs = env()
    kwargs["out_dir"] = tmp_path
    kwargs["demands"].store(replace(derived_demand(), network_id="other-network"))

    with pytest.raises(ScenarioSemanticError):
        build_scenario(TASK, agent_run(output=demand_scale_draft()), **kwargs)
