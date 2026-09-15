"""Manual smoke test: ONE real tool-calling run against OpenRouter with the default model.

Not a pytest test on purpose (CLAUDE.md "LLM provider & cost policy": the suite never calls the
real API). Run it by hand, from the `resto` conda env, when you want to confirm that the model
in `RESTO_LLM_DEFAULT_MODEL` actually drives the `OpenRouterToolAgent` loop end to end — picks
tools, reads their results, and finishes with a valid `submit_output` call:

    python scripts/smoke_openrouter.py            # one run, prints the trace and the result
    python scripts/smoke_openrouter.py --dry-run  # only shows config + what would be sent

Costs real money (a fraction of a cent on the flash tier at the budget below). Reads the key via
`load_llm_config()` and never prints it — `LlmConfig.__repr__` is redacted, and the tracer only
receives token counts, model name and estimated cost.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from resto.adapters.llm.anthropic_client import OpenRouterToolAgent
from resto.adapters.llm.config import MissingApiKeyError, load_llm_config
from resto.adapters.llm.pricing import estimate_cost_usd
from resto.application.ports.llm import AgentTask, Budget, StopReason, Tool

# Tiny enough that a wrong answer is obvious, and unguessable enough that the model has to call
# the tools rather than answer from memory: the "prices" below are made up.
_UNIT_PRICES_EUR = {"widget": 3.5, "gadget": 12.25, "gizmo": 0.4}


def unit_price(item: str) -> float:
    """Returns the unit price in EUR for a catalogue item."""
    try:
        return _UNIT_PRICES_EUR[item]
    except KeyError:
        raise ValueError(f"unknown item {item!r}; known: {sorted(_UNIT_PRICES_EUR)}") from None


def multiply(a: float, b: float) -> float:
    """Multiplies two numbers."""
    return a * b


TOOLS = (
    Tool(
        name="unit_price",
        description="Unit price in EUR of a catalogue item.",
        fn=unit_price,
        input_schema={
            "type": "object",
            "properties": {"item": {"type": "string"}},
            "required": ["item"],
        },
    ),
    Tool(
        name="multiply",
        description="Multiply two numbers.",
        fn=multiply,
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
    ),
)


@dataclass(frozen=True)
class Quote:
    item: str
    quantity: int
    total_eur: float
    rationale: str

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.total_eur < 0:
            raise ValueError("total_eur must be >= 0")


TASK = AgentTask(
    system_prompt=(
        "You are a quoting assistant. Use the tools to look up prices and compute totals — "
        "never guess a price. When done, call submit_output with the final Quote."
    ),
    input={"request": "Quote 7 gadgets.", "expected_fields": ["item", "quantity", "total_eur"]},
)
EXPECTED_TOTAL = 7 * _UNIT_PRICES_EUR["gadget"]

# Deliberately small: max 4 model turns, 256 output tokens per turn.
BUDGET = Budget(max_steps=4, max_tokens=256, max_seconds=60.0)


class PrintingTracer:
    """Prints each `llm_call` event as it happens and accumulates the estimated cost."""

    def __init__(self) -> None:
        self.total_cost_usd = 0.0
        self.cost_known = True

    def emit(self, study_id: str, event: str, payload: Mapping[str, Any]) -> None:
        print(f"[trace] {event}: {json.dumps(dict(payload), default=str)}")
        cost = payload.get("estimated_cost_usd")
        if cost is None:
            self.cost_known = False
        else:
            self.total_cost_usd += float(cost)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show config, make no API call")
    args = parser.parse_args(argv)

    try:
        config = load_llm_config()
    except MissingApiKeyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"config: {config}")  # redacted repr — never prints the key
    print(f"model:  {config.default_model}")
    print(f"budget: {BUDGET}")
    print(f"tools:  {[t.name for t in TOOLS]} + submit_output(Quote)")
    if estimate_cost_usd(config.default_model, 1, 1) is None:
        print("note:   model not in adapters/llm/pricing.py — cost will show as unknown")
    if args.dry_run:
        print("dry run: no API call made")
        return 0

    tracer = PrintingTracer()
    agent = OpenRouterToolAgent(config, tracer=tracer, trace_id="smoke")
    run = agent.run(TASK, tools=TOOLS, output=Quote, budget=BUDGET)

    print()
    print(f"stop_reason: {run.stop_reason}")
    print(f"usage:       {run.usage}")
    cost = f"${tracer.total_cost_usd:.6f}" if tracer.cost_known else "unknown"
    print(f"est. cost:   {cost}")
    print("tool_calls:")
    for call in run.tool_calls:
        print(f"  - {call.name}({json.dumps(dict(call.arguments))}) -> {call.result_summary}")
    print(f"output:      {run.output}")

    if run.stop_reason is not StopReason.OUTPUT or run.output is None:
        print("\nFAIL: the model did not produce a valid Quote within budget")
        return 1
    used_tools = {call.name for call in run.tool_calls}
    if "unit_price" not in used_tools:
        print("\nFAIL: the model never called unit_price (it guessed instead of using tools)")
        return 1
    if abs(run.output.total_eur - EXPECTED_TOTAL) > 1e-6:
        print(f"\nFAIL: total_eur={run.output.total_eur}, expected {EXPECTED_TOTAL}")
        return 1
    print("\nOK: tool-calling round-trip works with this model")
    return 0


if __name__ == "__main__":
    sys.exit(main())
