from __future__ import annotations

import pytest

from resto.adapters.llm.pricing import UnknownModelError, estimate_cost_usd, price_of

MANIFEST_MODELS = (
    "deepseek/deepseek-v4.1-flash",
    "mistralai/ministral-3b-2512",
    "google/gemma-3-12b-it",
    "qwen/qwen3.5-9b",
    "meta-llama/llama-3.3-70b-instruct",
)


def test_known_model_prices_input_and_output_separately() -> None:
    cost = estimate_cost_usd("deepseek/deepseek-v4.1-flash", 1_000_000, 1_000_000)
    assert cost == 0.15 + 0.60


def test_zero_tokens_cost_nothing() -> None:
    assert estimate_cost_usd("deepseek/deepseek-v4.1-flash", 0, 0) == 0.0


def test_unknown_model_is_rejected_rather_than_estimated() -> None:
    with pytest.raises(UnknownModelError):
        estimate_cost_usd("some/unknown-model", 1000, 1000)


def test_price_of_unknown_model_is_rejected() -> None:
    with pytest.raises(UnknownModelError):
        price_of("some/unknown-model")


def test_manifest_has_the_three_pricing_models_plus_the_two_bank_models() -> None:
    for model in MANIFEST_MODELS:
        price = price_of(model)
        assert price.input_per_mtok > 0
        assert price.output_per_mtok > 0
        assert price.as_of
