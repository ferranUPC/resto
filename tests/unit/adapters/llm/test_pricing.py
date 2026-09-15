from __future__ import annotations

from resto.adapters.llm.pricing import estimate_cost_usd


def test_known_model_prices_input_and_output_separately() -> None:
    cost = estimate_cost_usd("deepseek/deepseek-v4.1-flash", 1_000_000, 1_000_000)
    assert cost == 0.15 + 0.60


def test_zero_tokens_cost_nothing() -> None:
    assert estimate_cost_usd("deepseek/deepseek-v4.1-flash", 0, 0) == 0.0


def test_unknown_model_returns_none_rather_than_a_guess() -> None:
    assert estimate_cost_usd("some/unknown-model", 1000, 1000) is None
