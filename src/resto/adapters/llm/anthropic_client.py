"""Real `ToolAgent` implementation. Despite the module name (kept from the architecture doc's
§2.6 repository layout, written before the provider was chosen), this talks to **OpenRouter**'s
OpenAI-compatible API, not the Anthropic API directly — see CLAUDE.md "LLM provider & cost
policy". Model selection, budgets and the escalation gate all live in `adapters/llm/config.py`;
this module only runs the tool-calling loop once a model has been chosen.

The loop: offer `tools` plus one synthetic terminal tool, `submit_output` (JSON schema taken from
`output` via `application.schemas.adapter_for`), with `tool_choice="auto"`. Every non-terminal
call the model makes is executed against the matching `Tool.fn` and fed back as a tool result;
`submit_output`'s arguments are validated against `output` (running its dataclass invariants via
pydantic) and, on success, end the run with `StopReason.OUTPUT`. A validation failure is fed back
to the model as that tool's result, so it gets another turn to fix it — still inside
`budget.max_steps`, which is where ADR-0001's "retry-on-validation-failure, implemented once at
the port" lives. Running out of `max_steps`/`max_seconds` without a valid `submit_output` call
ends the run with `StopReason.BUDGET`, never a partially-guessed output.

Never logs, prints, or traces `LlmConfig.api_key` — the OpenAI SDK client holds it in memory only,
and everything this module sends to `Tracer.emit` is limited to token counts, model name, tool
names and an estimated cost.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import ValidationError

from resto.adapters.llm.config import LlmConfig
from resto.adapters.llm.pricing import estimate_cost_usd
from resto.application.ports.llm import AgentRun, AgentTask, Budget, StopReason, Tool, ToolCall
from resto.application.ports.tracing import Tracer
from resto.application.schemas import adapter_for
from resto.domain.value_objects.step_record import Usage

T = TypeVar("T")

SUBMIT_TOOL_NAME = "submit_output"
_RESULT_SUMMARY_MAX_LEN = 500

CompletionFn = Callable[..., Any]


class OpenRouterToolAgent:
    """`ToolAgent` over OpenRouter. One instance is pinned to one model — escalating to a
    stronger model means constructing a second instance with `model=config.escalation_model`,
    deliberately, never a fallback this class picks on its own."""

    def __init__(
        self,
        config: LlmConfig,
        *,
        model: str | None = None,
        tracer: Tracer | None = None,
        trace_id: str | None = None,
        complete: CompletionFn | None = None,
    ) -> None:
        self._config = config
        self._model = model or config.default_model
        self._tracer = tracer
        self._trace_id = trace_id
        self._complete: CompletionFn = complete or OpenAI(
            api_key=config.api_key, base_url=config.base_url
        ).chat.completions.create

    def run(
        self, task: AgentTask, tools: Sequence[Tool], output: type[T], budget: Budget
    ) -> AgentRun[T]:
        tools_by_name = {tool.name: tool for tool in tools}
        tools_schema = [_tool_schema(tool) for tool in tools] + [_submit_tool_schema(output)]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": task.system_prompt},
            {"role": "user", "content": json.dumps(task.input, default=str)},
        ]
        tool_calls: list[ToolCall] = []
        input_tokens = 0
        output_tokens = 0
        started = time.monotonic()

        for step in range(budget.max_steps):
            if time.monotonic() - started > budget.max_seconds:
                break

            response = self._complete(
                model=self._model,
                messages=messages,
                tools=tools_schema,
                tool_choice="auto",
                max_tokens=budget.max_tokens,
            )
            usage = getattr(response, "usage", None)
            step_input = getattr(usage, "prompt_tokens", 0) or 0
            step_output = getattr(usage, "completion_tokens", 0) or 0
            input_tokens += step_input
            output_tokens += step_output
            self._trace(step, step_input, step_output)

            message = response.choices[0].message
            calls = list(getattr(message, "tool_calls", None) or [])
            if not calls:
                messages.append({"role": "assistant", "content": message.content or ""})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Call {SUBMIT_TOOL_NAME} with your final answer, or another "
                        "tool to keep working.",
                    }
                )
                continue

            messages.append(_assistant_message(message, calls))
            for call in calls:
                name = call.function.name
                result_text, arguments = _run_one_call(call, tools_by_name, output)
                if name == SUBMIT_TOOL_NAME and arguments is not None:
                    try:
                        validated = adapter_for(output).validate_python(arguments)
                    except ValidationError as exc:
                        feedback = f"validation failed: {exc}"
                        messages.append(_tool_result(call.id, feedback))
                        tool_calls.append(
                            ToolCall(
                                name=name,
                                arguments=arguments,
                                result_summary=feedback[:_RESULT_SUMMARY_MAX_LEN],
                            )
                        )
                        continue
                    tool_calls.append(
                        ToolCall(name=name, arguments=arguments, result_summary="submitted")
                    )
                    return AgentRun(
                        output=validated,
                        tool_calls=tuple(tool_calls),
                        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
                        stop_reason=StopReason.OUTPUT,
                    )
                messages.append(_tool_result(call.id, result_text))
                tool_calls.append(
                    ToolCall(
                        name=name,
                        arguments=arguments or {},
                        result_summary=result_text[:_RESULT_SUMMARY_MAX_LEN],
                    )
                )

        return AgentRun(
            output=None,
            tool_calls=tuple(tool_calls),
            usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
            stop_reason=StopReason.BUDGET,
        )

    def _trace(self, step: int, input_tokens: int, output_tokens: int) -> None:
        if self._tracer is None or self._trace_id is None:
            return
        self._tracer.emit(
            self._trace_id,
            "llm_call",
            {
                "step": step,
                "model": self._model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimate_cost_usd(self._model, input_tokens, output_tokens),
            },
        )


def _run_one_call(
    call: Any, tools_by_name: Mapping[str, Tool], output: type[T]
) -> tuple[str, dict[str, Any] | None]:
    """Parses and executes one tool call. Returns `(result_text, arguments)` — `arguments` is
    `None` only when the model's JSON itself did not parse (e.g. truncated at `max_tokens`): the
    caller then neither executes nor validates it, but still records it in the trace."""
    try:
        arguments = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError as exc:
        return f"invalid JSON arguments: {exc}", None

    name = call.function.name
    if name == SUBMIT_TOOL_NAME:
        return "", arguments  # validated by the caller, which has the real output type

    tool = tools_by_name.get(name)
    if tool is None:
        return f"error: no such tool: {name}", arguments
    try:
        result = tool.fn(**arguments)
    except Exception as exc:  # a tool failing is informative feedback, not a fatal run error
        return f"error: {exc}", arguments
    return json.dumps(result, default=str), arguments


def _tool_schema(tool: Tool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.input_schema) or {"type": "object", "properties": {}},
        },
    }


def _submit_tool_schema(output: type[Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SUBMIT_TOOL_NAME,
            "description": f"Submit the final {output.__name__} once you are done.",
            "parameters": adapter_for(output).json_schema(),
        },
    }


def _assistant_message(message: Any, calls: Sequence[Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            }
            for call in calls
        ],
    }


def _tool_result(call_id: str, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": content}
