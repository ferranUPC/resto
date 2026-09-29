"""What every agent is given today: name, description and input schema of each network, Expert and
Scenario Builder tool, stored once in `tool_snapshot.json` and asserted exactly (refactor r3).

The declaration refactor must leave this file unchanged. Regenerate it only on purpose:

    python -m tests.unit.application.tools.test_tool_snapshot
"""

from __future__ import annotations

import json
from pathlib import Path

from resto.adapters.persistence.memory import (
    InMemoryNetworkRepository,
    InMemoryNoteRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
)
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.llm import Tool
from resto.application.tools.expert import EvidenceLedger, build_expert_tools
from resto.application.tools.network import build_network_tools
from resto.application.tools.scenario_builder import (
    BuilderCollaborators,
    BuilderRequest,
    build_scenario_builder_tools,
)
from resto.domain.value_objects.intervention import Intervention, InterventionType
from resto.domain.value_objects.intervention_target import LaneTarget
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask
from resto.domain.value_objects.time_window import TimeWindow
from tests.unit._paths import DEV_NET
from tests.unit.application.tools._recorders import (
    RecordingAdditionalFileWriter,
    RecordingDemandRepository,
    RecordingDemandScaler,
    RecordingDuarouter,
    RecordingWriter,
)
from tests.unit.domain._samples import demand as sample_demand
from tests.unit.domain._samples import network as sample_network
from tests.unit.domain._samples import simulation_result as sample_result

SNAPSHOT = Path(__file__).with_name("tool_snapshot.json")


def _describe(tools: tuple[Tool, ...]) -> list[dict[str, object]]:
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]


def _expert(query: SumolibNetworkQuery, *, notes_allowed: bool) -> tuple[Tool, ...]:
    results = InMemoryResultRepository()
    results.store(sample_result())
    task = ExpertTask(
        question="which edges are congested?",
        mode=Mode.FORCED,
        network_id="abc123",
        result_ids=("res1",),
        notes_allowed=notes_allowed,
    )
    return build_expert_tools(
        task=task,
        query=query,
        results=results,
        scenarios=InMemoryScenarioRepository(),
        notes=InMemoryNoteRepository(),
        ledger=EvidenceLedger(),
    )


def _builder(query: SumolibNetworkQuery) -> tuple[Tool, ...]:
    closure = Intervention(
        type=InterventionType.LANE_CLOSURE,
        target=LaneTarget(edge_id="A0A1", lane_index=0),
        window=TimeWindow(0, 3600),
    )
    collaborators = BuilderCollaborators(
        networks=InMemoryNetworkRepository(),
        demands=RecordingDemandRepository(),
        network_query_factory=SumolibNetworkQuery,
        rerouter_writer=RecordingAdditionalFileWriter(),
        vss_writer=RecordingAdditionalFileWriter(),
        tls_program_writer=RecordingAdditionalFileWriter(),
        sumocfg_writer=RecordingWriter(),
        demand_scaler=RecordingDemandScaler(),
        duarouter=RecordingDuarouter(),
        out_dir=Path("out"),
    )
    request = BuilderRequest(
        interventions=(closure,),
        query=query,
        network=sample_network(),
        demand=sample_demand(),
        net_file=Path("net.xml"),
        route_files=(Path("routes.rou.xml"),),
        begin=0.0,
        end=3600.0,
        out_dir=Path("out"),
    )
    return build_scenario_builder_tools(collaborators, request)


def collect() -> dict[str, list[dict[str, object]]]:
    query = SumolibNetworkQuery(DEV_NET)
    return {
        "network": _describe(build_network_tools(query)),
        "expert": _describe(_expert(query, notes_allowed=False)),
        "expert_with_notes": _describe(_expert(query, notes_allowed=True)),
        "scenario_builder": _describe(_builder(query)),
    }


def test_tools_given_to_agents_match_the_stored_snapshot() -> None:
    # round-trip through JSON so tuples compare as lists, like the stored file
    current = json.loads(json.dumps(collect()))
    assert current == json.loads(SNAPSHOT.read_text())


if __name__ == "__main__":
    SNAPSHOT.write_text(json.dumps(collect(), indent=2, sort_keys=True) + "\n")
