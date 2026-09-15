"""`OpenRouterToolAgent` (E2.2): the tool-calling loop, budget handling, and that nothing sent to
the tracer ever carries the API key. `complete` is always a fake here — this file must never
construct a real `openai.OpenAI` client or need `OPENROUTER_API_KEY`, per CLAUDE.md's cost policy
(tests never call the real API)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
from resto.adapters.llm.config import LlmConfig
from resto.application.ports.llm import AgentTask, Budget, StopReason, Tool

CONFIG = LlmConfig(api_key="test-key", default_model="test/model")


@dataclass(frozen=True, slots=True)
class Answer:
    text: str

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("text must not be blank")


def tool_call(call_id: str, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(arguments))
    )


def completion(
    *,
    content: str | None = None,
    tool_calls: tuple[SimpleNamespace, ...] = (),
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> SimpleNamespace:
    message = SimpleNamespace(content=content, tool_calls=list(tool_calls) or None)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class ScriptedCompletions:
    """Fake `chat.completions.create`: returns each response in `responses` in turn."""

    def __init__(self, *responses: SimpleNamespace) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class RecordingTracer:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def emit(self, study_id: str, event: str, payload: Mapping[str, Any]) -> None:
        self.events.append((study_id, event, dict(payload)))


DUMMY_BUDGET = Budget(max_steps=5, max_tokens=256, max_seconds=30.0)
DUMMY_TASK = AgentTask(system_prompt="be helpful", input={"goal": "test"})


def test_submits_a_valid_output_directly() -> None:
    complete = ScriptedCompletions(
        completion(tool_calls=(tool_call("c1", "submit_output", {"text": "done"}),))
    )
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(DUMMY_TASK, tools=(), output=Answer, budget=DUMMY_BUDGET)

    assert run.stop_reason is StopReason.OUTPUT
    assert run.output == Answer(text="done")
    assert run.usage.input_tokens == 10
    assert run.usage.output_tokens == 5


def test_calls_an_offered_tool_before_submitting() -> None:
    echo = Tool(name="echo", description="echoes", fn=lambda text: {"echoed": text})
    complete = ScriptedCompletions(
        completion(tool_calls=(tool_call("c1", "echo", {"text": "hi"}),)),
        completion(tool_calls=(tool_call("c2", "submit_output", {"text": "hi"}),)),
    )
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(DUMMY_TASK, tools=(echo,), output=Answer, budget=DUMMY_BUDGET)

    assert run.stop_reason is StopReason.OUTPUT
    assert [c.name for c in run.tool_calls] == ["echo", "submit_output"]
    assert run.tool_calls[0].arguments == {"text": "hi"}
    # the tool result the model would have seen next turn:
    second_call_messages = complete.calls[1]["messages"]
    assert any('"echoed": "hi"' in (m.get("content") or "") for m in second_call_messages)


def test_a_failing_tool_call_is_fed_back_as_an_error_not_raised() -> None:
    def boom(**_: Any) -> None:
        raise RuntimeError("kaboom")

    broken = Tool(name="broken", description="always fails", fn=boom)
    complete = ScriptedCompletions(
        completion(tool_calls=(tool_call("c1", "broken", {}),)),
        completion(tool_calls=(tool_call("c2", "submit_output", {"text": "recovered"}),)),
    )
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(DUMMY_TASK, tools=(broken,), output=Answer, budget=DUMMY_BUDGET)

    assert run.stop_reason is StopReason.OUTPUT
    assert "error: kaboom" in run.tool_calls[0].result_summary


def test_an_unknown_tool_name_is_reported_without_crashing() -> None:
    complete = ScriptedCompletions(
        completion(tool_calls=(tool_call("c1", "does_not_exist", {}),)),
        completion(tool_calls=(tool_call("c2", "submit_output", {"text": "ok"}),)),
    )
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(DUMMY_TASK, tools=(), output=Answer, budget=DUMMY_BUDGET)

    assert run.stop_reason is StopReason.OUTPUT
    assert "no such tool" in run.tool_calls[0].result_summary


def test_invalid_submission_gets_one_more_turn_to_fix_it() -> None:
    complete = ScriptedCompletions(
        completion(tool_calls=(tool_call("c1", "submit_output", {"text": ""}),)),  # invalid
        completion(tool_calls=(tool_call("c2", "submit_output", {"text": "fixed"}),)),
    )
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(DUMMY_TASK, tools=(), output=Answer, budget=DUMMY_BUDGET)

    assert run.stop_reason is StopReason.OUTPUT
    assert run.output == Answer(text="fixed")
    # the validation error was fed back, not swallowed silently:
    second_call_messages = complete.calls[1]["messages"]
    assert any("validation failed" in (m.get("content") or "") for m in second_call_messages)


def test_a_plain_text_reply_is_nudged_back_toward_submitting() -> None:
    complete = ScriptedCompletions(
        completion(content="thinking out loud, no tool call"),
        completion(tool_calls=(tool_call("c1", "submit_output", {"text": "ok"}),)),
    )
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(DUMMY_TASK, tools=(), output=Answer, budget=DUMMY_BUDGET)

    assert run.stop_reason is StopReason.OUTPUT


def test_exhausting_max_steps_without_a_submission_stops_on_budget() -> None:
    never_submits = tuple(
        completion(tool_calls=(tool_call(f"c{i}", "does_not_exist", {}),)) for i in range(3)
    )
    complete = ScriptedCompletions(*never_submits)
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(
        DUMMY_TASK,
        tools=(),
        output=Answer,
        budget=Budget(max_steps=3, max_tokens=64, max_seconds=30.0),
    )

    assert run.stop_reason is StopReason.BUDGET
    assert run.output is None
    assert len(complete.calls) == 3


def test_exceeding_max_seconds_stops_on_budget_without_calling_the_api() -> None:
    complete = ScriptedCompletions()
    agent = OpenRouterToolAgent(CONFIG, complete=complete)

    run = agent.run(
        DUMMY_TASK,
        tools=(),
        output=Answer,
        budget=Budget(max_steps=5, max_tokens=64, max_seconds=-1.0),
    )

    assert run.stop_reason is StopReason.BUDGET
    assert complete.calls == []


def test_traces_tokens_and_estimated_cost_but_never_the_key() -> None:
    tracer = RecordingTracer()
    complete = ScriptedCompletions(
        completion(
            tool_calls=(tool_call("c1", "submit_output", {"text": "ok"}),),
            prompt_tokens=100,
            completion_tokens=20,
        )
    )
    agent = OpenRouterToolAgent(CONFIG, complete=complete, tracer=tracer, trace_id="run-1")

    agent.run(DUMMY_TASK, tools=(), output=Answer, budget=DUMMY_BUDGET)

    assert len(tracer.events) == 1
    study_id, event, payload = tracer.events[0]
    assert (study_id, event) == ("run-1", "llm_call")
    assert payload["input_tokens"] == 100
    assert payload["output_tokens"] == 20
    assert payload["model"] == "test/model"
    assert "api_key" not in payload
    assert CONFIG.api_key not in json.dumps(payload)


def test_repr_of_the_config_never_leaks_into_a_trace_payload() -> None:
    # defense in depth: even if a future change accidentally traced the whole config object,
    # str()/repr() of LlmConfig itself must not carry the key (see test_config.py for the
    # dedicated repr test) - this just re-asserts the invariant from the client's point of view.
    assert CONFIG.api_key not in repr(CONFIG)
    assert CONFIG.api_key not in str(CONFIG)
