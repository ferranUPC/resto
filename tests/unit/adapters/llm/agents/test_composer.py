"""Output Composer agent config (E5.4): assembles the task from the closed study and hands back the
draft the (fake) agent produced - no logic of its own beyond that assembly."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from resto.adapters.llm.agents.composer import COMPOSER_VERSION, ComposerPort
from resto.adapters.persistence.memory import InMemoryResultRepository, InMemoryStudyRepository
from resto.application.ports.llm import AgentTask, Budget, Tool
from resto.application.schemas import adapter_for
from resto.domain.entities.study import Study
from resto.domain.value_objects.drafts import ReportDraft
from resto.domain.value_objects.expert_answer import ExpertAnswer
from tests.unit.adapters.llm._fakes import FakeToolAgent, call_tool
from tests.unit.domain._samples import simulation_result as sample_result
from tests.unit.domain._samples import study as sample_study

BUDGET = Budget(max_steps=6, max_tokens=2048, max_seconds=60.0)
DRAFT = ReportDraft(summary="closing the lane shifts delay")


def test_the_composer_gets_the_closed_study_and_its_tools_and_returns_the_draft() -> None:
    study = sample_study()
    studies = InMemoryStudyRepository()
    studies.store(study)
    results = InMemoryResultRepository()
    results.store(sample_result())
    seen: dict[str, Any] = {}

    def interact(task: AgentTask, tools: Sequence[Tool]) -> None:
        seen["input"] = task.input
        seen["tools"] = [t.name for t in tools]
        seen["study"] = call_tool(tools, "get_study")

    agent = FakeToolAgent(output=DRAFT, interact=interact)
    run = ComposerPort(agent=agent, budget=BUDGET, studies=studies, results=results).compose(study)

    assert run.output == DRAFT
    assert seen["tools"] == ["get_study", "get_result", "query_edgedata"]
    assert seen["study"] == adapter_for(Study).dump_python(study, mode="json")
    assert seen["input"]["study_id"] == study.study_id
    assert seen["input"]["question"] == study.question.text
    answer = study.rounds[-1].answer
    assert seen["input"]["answer"] == adapter_for(ExpertAnswer).dump_python(answer, mode="json")


def test_the_version_is_a_label() -> None:
    assert COMPOSER_VERSION.startswith("v")
