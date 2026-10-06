from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

from resto.adapters.llm.agents.input_parser import (
    PARSER_MAX_OUTPUT_TOKENS,
    PARSER_MAX_STEPS,
    PARSER_VERSION,
    SYSTEM_PROMPT,
    InputParserPort,
)
from resto.application.ports.llm import AgentRun, AgentTask, Budget, StopReason, Tool
from resto.domain.value_objects.answer_value import Measure
from resto.domain.value_objects.intervention import InterventionType
from resto.domain.value_objects.question import Intent, Question
from resto.domain.value_objects.step_record import Usage

T = TypeVar("T")

BUDGET = Budget(max_steps=6, max_tokens=2048, max_seconds=60.0)


@dataclass
class RecordingAgent:
    output: Any
    stop_reason: StopReason = StopReason.OUTPUT
    calls: list[tuple[AgentTask, Sequence[Tool], type[Any], Budget]] = field(default_factory=list)

    def run(
        self, task: AgentTask, tools: Sequence[Tool], output: type[T], budget: Budget
    ) -> AgentRun[T]:
        self.calls.append((task, tools, output, budget))
        return AgentRun(
            output=self.output, tool_calls=(), usage=Usage(), stop_reason=self.stop_reason
        )


def test_the_parser_gets_the_request_no_tools_and_one_retry() -> None:
    agent = RecordingAgent(Question(text="x", intent=Intent.DESCRIBE))
    InputParserPort(agent, BUDGET).parse("How busy is edge N4N5?")
    task, tools, output, budget = agent.calls[0]
    assert task.input == {"request": "How busy is edge N4N5?"}
    assert tools == () and output is Question
    assert budget.max_steps == PARSER_MAX_STEPS == 2
    assert budget.max_tokens == PARSER_MAX_OUTPUT_TOKENS
    assert budget.max_seconds == BUDGET.max_seconds


def test_the_question_keeps_the_users_own_text() -> None:
    agent = RecordingAgent(Question(text="a translation", intent=Intent.DESCRIBE))
    run = InputParserPort(agent, BUDGET).parse("¿Qué tal va N4N5?")
    assert run.output is not None and run.output.text == "¿Qué tal va N4N5?"


def test_network_only_parses_from_the_agents_output() -> None:
    from pydantic import TypeAdapter

    raw = {"text": "x", "intent": "describe", "network_only": True}
    question = TypeAdapter(Question).validate_python(raw)
    agent = RecordingAgent(question)
    run = InputParserPort(agent, BUDGET).parse("How many lanes has B0C0?")
    assert run.output is not None and run.output.network_only is True


def test_a_run_without_a_question_is_passed_through() -> None:
    agent = RecordingAgent(None, stop_reason=StopReason.BUDGET)
    run = InputParserPort(agent, BUDGET).parse("asdf")
    assert run.output is None and run.stop_reason is StopReason.BUDGET


def test_the_prompt_names_every_measure_and_intervention_type() -> None:
    for name in (*(m.value for m in Measure), *(t.value for t in InterventionType)):
        assert name in SYSTEM_PROMPT


def test_the_prompt_states_the_adr_0035_rules_and_no_profile_name() -> None:
    assert "- network_only:" in SYSTEM_PROMPT
    assert "one short English phrase" in SYSTEM_PROMPT
    assert "whatever the intent" in SYSTEM_PROMPT
    assert '"peak" when' not in SYSTEM_PROMPT


def test_the_prompt_teaches_four_intents_the_boundary_and_the_tie_break() -> None:
    assert PARSER_VERSION == "v8"
    intents = re.search(r"- intent:.*?\n- mode:", SYSTEM_PROMPT, re.DOTALL)
    assert intents is not None
    for name in ("describe", "diagnose", "compare", "run"):
        assert f"  - {name}:" in intents.group(0)
    assert "counterfactual" not in SYSTEM_PROMPT
    assert "when in doubt, compare" in SYSTEM_PROMPT.lower()
