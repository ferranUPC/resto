"""scenario_builder agent config (E2.2): assembles the right AgentTask/tools/budget and returns
whatever the (fake) agent produces — no logic of its own to test beyond that assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from resto.adapters.llm.agents.scenario_builder import (
    ScenarioBuilderPort,
    build_task,
    run_scenario_builder,
)
from resto.adapters.persistence.memory import InMemoryDemandRepository, InMemoryNetworkRepository
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.llm import Budget, StopReason
from resto.domain.services.ids import scenario_id_for
from resto.domain.value_objects.drafts import ScenarioDraft
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.mechanism import StaticFileMechanism
from resto.domain.value_objects.tasks import ScenarioTask
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit.adapters.llm._fakes import FakeToolAgent, call_tool
from tests.unit.application.tools.test_scenario_builder import (
    DEV_NET,
    RecordingAdditionalFileWriter,
    RecordingDemandRepository,
    RecordingDemandScaler,
    RecordingDuarouter,
    RecordingWriter,
)
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network

LANE = LaneTarget(edge_id="A0A1", lane_index=0)
CLOSURE = Intervention(type=InterventionType.LANE_CLOSURE, target=LANE, window=TimeWindow(0, 3600))
TASK = ScenarioTask(
    network_id="n1", demand_id="d1", interventions=(CLOSURE,), context_tags=frozenset({"peak"})
)
BUDGET = Budget(max_steps=6, max_tokens=2048, max_seconds=60.0)


def canned_draft() -> ScenarioDraft:
    from resto.domain.value_objects.artifact_ref import ArtifactRef

    return ScenarioDraft(
        interventions=(CLOSURE,),
        mechanisms=(StaticFileMechanism(file_kind="rerouter", path=Path("r.add.xml")),),
        sumocfg=ArtifactRef(path=Path("s.sumocfg"), content_hash="h", kind="sumocfg"),
        rationale="closed the lane for the window",
    )


def run(agent, tmp_path: Path, task: ScenarioTask = TASK):  # noqa: ANN001, ANN201
    return run_scenario_builder(
        task,
        agent,
        BUDGET,
        query=SumolibNetworkQuery(DEV_NET),
        net_file=Path("net.xml"),
        route_files=(Path("routes.rou.xml"),),
        begin=0.0,
        end=3600.0,
        rerouter_writer=RecordingAdditionalFileWriter(),
        vss_writer=RecordingAdditionalFileWriter(),
        tls_program_writer=RecordingAdditionalFileWriter(),
        sumocfg_writer=RecordingWriter(),
        demand=sample_demand(),
        network=sample_network(),
        demand_scaler=RecordingDemandScaler(),
        duarouter=RecordingDuarouter(),
        demands=RecordingDemandRepository(),
        out_dir=tmp_path,
    )


def test_build_task_carries_the_scenario_task_as_plain_data() -> None:
    task = build_task(TASK)
    assert task.input["network_id"] == "n1"
    assert task.input["demand_id"] == "d1"
    assert task.input["context_tags"] == ["peak"]
    assert task.input["interventions"][0]["type"] == "lane_closure"
    assert "lane_closure" in task.system_prompt
    assert "speed_limit" in task.system_prompt
    assert "edge_closure" in task.system_prompt
    assert "signal_program" in task.system_prompt
    assert "demand_scale" in task.system_prompt


def test_run_returns_the_agents_output(tmp_path: Path) -> None:
    agent = FakeToolAgent(output=canned_draft())
    run_result = run(agent, tmp_path)
    assert run_result.stop_reason is StopReason.OUTPUT
    assert run_result.output == canned_draft()


def test_run_offers_exactly_the_e2_3_tools(tmp_path: Path) -> None:
    seen_tool_names: list[str] = []

    def interact(task, tools):  # noqa: ANN001
        seen_tool_names.extend(t.name for t in tools)

    agent = FakeToolAgent(output=canned_draft(), interact=interact)
    run(agent, tmp_path)

    assert seen_tool_names == [
        "edge_exists",
        "lane_exists",
        "write_rerouter",
        "write_vss",
        "write_tls_program",
        "scale_demand",
        "write_sumocfg",
    ]


def test_the_offered_tools_are_actually_wired_up(tmp_path: Path) -> None:
    rerouter_writer = RecordingAdditionalFileWriter()

    def interact(task, tools):  # noqa: ANN001
        assert call_tool(tools, "edge_exists", edge_id="A0A1") is True
        call_tool(tools, "write_rerouter", intervention_index=0)

    agent = FakeToolAgent(output=canned_draft(), interact=interact)
    run_scenario_builder(
        TASK,
        agent,
        BUDGET,
        query=SumolibNetworkQuery(DEV_NET),
        net_file=Path("net.xml"),
        route_files=(Path("routes.rou.xml"),),
        begin=0.0,
        end=3600.0,
        rerouter_writer=rerouter_writer,
        vss_writer=RecordingAdditionalFileWriter(),
        tls_program_writer=RecordingAdditionalFileWriter(),
        sumocfg_writer=RecordingWriter(),
        demand=sample_demand(),
        network=sample_network(),
        demand_scaler=RecordingDemandScaler(),
        duarouter=RecordingDuarouter(),
        demands=RecordingDemandRepository(),
        out_dir=tmp_path,
    )

    assert rerouter_writer.calls == [(CLOSURE, tmp_path)]


def test_budget_exhaustion_surfaces_as_no_output(tmp_path: Path) -> None:
    from resto.application.ports.llm import AgentRun

    class BudgetExhaustedAgent:
        def run(self, task, tools, output, budget):  # noqa: ANN001, ANN201
            from resto.domain.value_objects.step_record import Usage

            return AgentRun(
                output=None, tool_calls=(), usage=Usage(), stop_reason=StopReason.BUDGET
            )

    run_result = run(BudgetExhaustedAgent(), tmp_path)
    assert run_result.output is None
    assert run_result.stop_reason is StopReason.BUDGET


def builder_port(tmp_path: Path, agent: FakeToolAgent, **writers: object) -> ScenarioBuilderPort:
    networks = InMemoryNetworkRepository()
    networks.store(sample_network())
    demands = InMemoryDemandRepository()
    demands.store(sample_demand())
    return ScenarioBuilderPort(
        agent=agent,
        budget=BUDGET,
        networks=networks,
        demands=demands,
        network_query_factory=lambda path: SumolibNetworkQuery(DEV_NET),
        rerouter_writer=writers.get("rerouter", RecordingAdditionalFileWriter()),  # type: ignore[arg-type]
        vss_writer=RecordingAdditionalFileWriter(),
        tls_program_writer=RecordingAdditionalFileWriter(),
        sumocfg_writer=writers.get("sumocfg", RecordingWriter()),  # type: ignore[arg-type]
        demand_scaler=RecordingDemandScaler(),
        duarouter=RecordingDuarouter(),
        out_dir=tmp_path,
    )


PORT_TASK = ScenarioTask(network_id="abc123", demand_id="t1", interventions=(CLOSURE,))


def test_the_builder_port_writes_into_the_requested_scenarios_directory(tmp_path: Path) -> None:
    rerouter_writer = RecordingAdditionalFileWriter()
    sumocfg_writer = RecordingWriter()

    def interact(task, tools):  # noqa: ANN001
        call_tool(tools, "write_rerouter", intervention_index=0)
        call_tool(tools, "write_sumocfg")

    port = builder_port(
        tmp_path,
        FakeToolAgent(output=canned_draft(), interact=interact),
        rerouter=rerouter_writer,
        sumocfg=sumocfg_writer,
    )

    run_result = port.build(PORT_TASK)

    requested = scenario_id_for("abc123", "t1", (CLOSURE,), frozenset())
    assert run_result.output == canned_draft()
    assert rerouter_writer.calls == [(CLOSURE, tmp_path / requested)]
    (settings, _, _), = sumocfg_writer.calls
    window = sample_demand().spec.window
    assert (settings.begin, settings.end) == (window.start, window.end)


def test_the_builder_port_refuses_an_unknown_demand(tmp_path: Path) -> None:
    port = builder_port(tmp_path, FakeToolAgent(output=canned_draft()))

    with pytest.raises(LookupError):
        port.build(ScenarioTask(network_id="abc123", demand_id="nope"))
