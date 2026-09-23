"""Network Expert agent config (E4.1): assembles the AgentTask/tools and hands back whatever the
(fake) agent produced - no logic of its own beyond that assembly."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from resto.adapters.llm.agents.expert import (
    ExpertPort,
    NoteWriterPort,
    build_note_task,
    build_task,
    run_expert,
    run_expert_note,
)
from resto.adapters.persistence.memory import (
    InMemoryNetworkRepository,
    InMemoryResultRepository,
    InMemoryScenarioRepository,
)
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.llm import AgentTask, Budget, Tool
from resto.application.schemas import adapter_for
from resto.application.tools.expert import (
    EXPERT_NETWORK_TOOLS,
    EXPERT_TOPOLOGY_TOOLS,
    RESULT_TOOLS,
    EvidenceLedger,
)
from resto.domain.value_objects.drafts import ExpertNoteDraft, ExpertNoteDrafts
from resto.domain.value_objects.experiment import ExperimentRole
from resto.domain.value_objects.expert_answer import Basis, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask, NoteScenario, NoteTask
from tests.unit.adapters.llm._fakes import FakeToolAgent, call_tool
from tests.unit.application.tools.test_expert import DEV_NET
from tests.unit.domain._samples import expert_answer
from tests.unit.domain._samples import network as sample_network
from tests.unit.domain._samples import simulation_result as sample_result

TASK = ExpertTask(
    question="Which edges exceed 3.5% occupancy between 0s and 300s?",
    mode=Mode.FORCED,
    network_id="abc123",
    result_ids=("res1",),
    notes_allowed=False,
)
BUDGET = Budget(max_steps=6, max_tokens=2048, max_seconds=60.0)


def test_build_task_carries_the_expert_task_as_plain_data() -> None:
    task = build_task(TASK)
    assert task.input == {
        "question": TASK.question,
        "mode": "forced",
        "network_id": "abc123",
        "result_ids": ["res1"],
        "notes_allowed": False,
    }
    for rule in ("query_edgedata", "get_scenario", '"ref"', "extrapolated", "needs_simulation"):
        assert rule in task.system_prompt
    kinds = ('"edges"', '"quantity"', '"change"', '"no_value"', "travel_time (s)", "rank_edges")
    for kind in kinds:
        assert kind in task.system_prompt


def test_prompt_examples_never_use_dev_net_edge_ids() -> None:
    # DEV-NET edges are named <col><row><col><row> (e.g. B2C2); gold answers are built from them
    assert re.findall(r"\b[A-E][0-4][A-E][0-4]\b", build_task(TASK).system_prompt) == []


def test_run_expert_offers_the_expert_tools_and_returns_the_agent_run() -> None:
    results = InMemoryResultRepository()
    results.store(sample_result())
    ledger = EvidenceLedger()
    seen: dict[str, object] = {}

    def interact(task: AgentTask, tools: Sequence[Tool]) -> None:
        seen["input"] = task.input
        seen["tools"] = [t.name for t in tools]
        call_tool(tools, "get_result", result_id="res1")

    agent = FakeToolAgent(output=expert_answer(), interact=interact)
    run = run_expert(
        TASK,
        agent,
        BUDGET,
        query=SumolibNetworkQuery(DEV_NET),
        results=results,
        scenarios=InMemoryScenarioRepository(),
        notes=None,
        ledger=ledger,
    )

    assert run.output == expert_answer()
    assert seen["input"] == build_task(TASK).input
    assert seen["tools"] == [*EXPERT_NETWORK_TOOLS, *EXPERT_TOPOLOGY_TOOLS, *RESULT_TOOLS]
    assert [e.tool for e in ledger.entries] == ["get_result"]


NOTE_TASK = NoteTask(
    round=ExpertRound(question=TASK.question, answer=expert_answer()),
    scenarios=(
        NoteScenario("s1", "base", ExperimentRole.BASELINE, "as it is", simulated=True),
        NoteScenario("s2", "treatment", ExperimentRole.TREATMENT, "closure", simulated=False),
    ),
)


def test_build_note_task_carries_the_round_and_the_allow_list_as_plain_data() -> None:
    task = build_note_task(NOTE_TASK)
    assert task.input == {
        "question": NOTE_TASK.round.question,
        "answer": adapter_for(ExpertAnswer).dump_python(NOTE_TASK.round.answer, mode="json"),
        "scenarios": [
            {
                "scenario_id": "s1",
                "arm": "base",
                "role": "baseline",
                "purpose": "as it is",
                "simulated": True,
            },
            {
                "scenario_id": "s2",
                "arm": "treatment",
                "role": "treatment",
                "purpose": "closure",
                "simulated": False,
            },
        ],
    }
    for rule in ("scenario_ref", "basis", "context_tags", "values", "submit_output", "3 notes"):
        assert rule in task.system_prompt


def test_run_expert_note_offers_no_tools_and_returns_the_agent_run() -> None:
    drafts = ExpertNoteDrafts(
        notes=(
            ExpertNoteDraft(
                text="closing the lane reroutes traffic onto B2C2",
                basis=Basis.INFERRED,
                scenario_ref="s2",
            ),
        )
    )
    seen: dict[str, object] = {}

    def interact(task: AgentTask, tools: Sequence[Tool]) -> None:
        seen["input"] = task.input
        seen["tools"] = list(tools)

    agent = FakeToolAgent(output=drafts, interact=interact)
    run = run_expert_note(NOTE_TASK, agent, BUDGET)

    assert run.output == drafts
    assert seen["input"] == build_note_task(NOTE_TASK).input
    assert seen["tools"] == []


def expert_port(networks: InMemoryNetworkRepository, opened: list[Path]) -> ExpertPort:
    def query_for(path: Path) -> SumolibNetworkQuery:
        opened.append(path)
        return SumolibNetworkQuery(DEV_NET)

    return ExpertPort(
        agent=FakeToolAgent(output=expert_answer()),
        budget=BUDGET,
        networks=networks,
        results=InMemoryResultRepository(),
        scenarios=InMemoryScenarioRepository(),
        notes=None,
        network_query_factory=query_for,
    )


def test_the_expert_port_queries_the_network_the_task_names() -> None:
    networks = InMemoryNetworkRepository()
    networks.store(sample_network())
    opened: list[Path] = []

    run = expert_port(networks, opened).answer(TASK, EvidenceLedger())

    assert run.output == expert_answer()
    assert opened == [sample_network().net_xml.path]


def test_the_expert_port_refuses_a_network_that_is_not_stored() -> None:
    with pytest.raises(LookupError):
        expert_port(InMemoryNetworkRepository(), []).answer(TASK, EvidenceLedger())


def test_the_note_writer_port_runs_the_note_writer() -> None:
    port = NoteWriterPort(agent=FakeToolAgent(output=ExpertNoteDrafts()), budget=BUDGET)

    assert port.write(NOTE_TASK).output == ExpertNoteDrafts()
