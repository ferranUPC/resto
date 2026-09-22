"""Network Expert agent config (E4.1): assembles the AgentTask/tools and hands back whatever the
(fake) agent produced - no logic of its own beyond that assembly."""

from __future__ import annotations

import re
from collections.abc import Sequence

from resto.adapters.llm.agents.expert import (
    build_note_task,
    build_task,
    run_expert,
    run_expert_note,
)
from resto.adapters.persistence.memory import InMemoryResultRepository, InMemoryScenarioRepository
from resto.adapters.sumo.netxml import SumolibNetworkQuery
from resto.application.ports.llm import AgentTask, Budget, Tool
from resto.application.schemas import adapter_for
from resto.application.tools.expert import (
    EXPERT_NETWORK_TOOLS,
    EXPERT_TOPOLOGY_TOOLS,
    RESULT_TOOLS,
    EvidenceLedger,
)
from resto.domain.value_objects.drafts import ExpertNoteDraft
from resto.domain.value_objects.expert_answer import Basis, ExpertAnswer
from resto.domain.value_objects.expert_round import ExpertRound
from resto.domain.value_objects.question import Mode
from resto.domain.value_objects.tasks import ExpertTask
from tests.unit.adapters.llm._fakes import FakeToolAgent, call_tool
from tests.unit.application.tools.test_expert import DEV_NET
from tests.unit.domain._samples import expert_answer
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


ROUND = ExpertRound(question=TASK.question, answer=expert_answer())


def test_build_note_task_carries_the_round_as_plain_data() -> None:
    task = build_note_task(ROUND)
    assert task.input == {
        "question": ROUND.question,
        "answer": adapter_for(ExpertAnswer).dump_python(ROUND.answer, mode="json"),
    }
    for rule in ("basis", "context_tags", "values", "submit_output"):
        assert rule in task.system_prompt


def test_run_expert_note_offers_no_tools_and_returns_the_agent_run() -> None:
    draft = ExpertNoteDraft(
        text="closing the lane reroutes traffic onto B2C2", basis=Basis.INFERRED
    )
    seen: dict[str, object] = {}

    def interact(task: AgentTask, tools: Sequence[Tool]) -> None:
        seen["input"] = task.input
        seen["tools"] = list(tools)

    agent = FakeToolAgent(output=draft, interact=interact)
    run = run_expert_note(ROUND, agent, BUDGET)

    assert run.output == draft
    assert seen["input"] == build_note_task(ROUND).input
    assert seen["tools"] == []
