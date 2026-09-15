"""OpenRouter per-token pricing for cost estimation in traces (CLAUDE.md "LLM provider & cost
policy"). Manually maintained — OpenRouter has no pricing endpoint this client calls; prices here
were current as of Sep 2026 and should be spot-checked at https://openrouter.ai/models if a
trace's `estimated_cost_usd` looks off.
"""

from __future__ import annotations

# model slug -> (USD per 1M input tokens, USD per 1M output tokens)
_PRICE_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-v4.1-flash": (0.15, 0.60),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """`None` for a model not in the table rather than a fabricated number — an unknown price
    must show up as missing in a trace, never as a silently wrong one."""
    prices = _PRICE_PER_MILLION_TOKENS.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
