from __future__ import annotations

import pytest
from eval.request_bank.llm import price_of

from resto.adapters.llm.pricing import UnknownModelError


def test_price_of_prices_input_and_output_separately() -> None:
    cost = price_of("qwen/qwen3.5-9b", 1_000_000, 1_000_000)
    assert cost == 0.10 + 0.15


def test_price_of_unknown_model_is_rejected_rather_than_a_guessed_fallback() -> None:
    with pytest.raises(UnknownModelError):
        price_of("some/unknown-model", 1000, 1000)
