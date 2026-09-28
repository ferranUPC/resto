"""OpenRouter chat for the variant pipeline. Bank-building models only (CLAUDE.md, evaluation
tooling exceptions); never used by an agent run. Reasoning is disabled: rewriting needs none, and
reasoning tokens are billed as output."""

from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

from eval.request_bank.pipeline import Models, Reply
from resto.adapters.llm.config import load_llm_config
from resto.adapters.llm.pricing import estimate_cost_usd

DEFAULT_GENERATOR = "qwen/qwen3.5-9b"
DEFAULT_VERIFIER = "meta-llama/llama-3.3-70b-instruct"


def bank_models() -> Models:
    return Models(
        generator=os.environ.get("RESTO_BANK_GENERATOR_MODEL", "").strip() or DEFAULT_GENERATOR,
        verifier=os.environ.get("RESTO_BANK_VERIFIER_MODEL", "").strip() or DEFAULT_VERIFIER,
    )


def price_of(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Priced from `config/prices.toml`; raises `UnknownModelError` for a model missing from the
    manifest rather than falling back to a guessed price."""
    return estimate_cost_usd(model, prompt_tokens, completion_tokens)


class OpenRouterChat:
    def __init__(self) -> None:
        config = load_llm_config()
        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def __call__(self, model: str, system: str, user: str) -> Reply:
        response = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0,
            max_tokens=800,
            extra_body={"reasoning": {"enabled": False}, "usage": {"include": True}},
        )
        usage: Any = response.usage
        cost = getattr(usage, "cost", None)
        if cost is None and usage is not None:
            cost = price_of(model, usage.prompt_tokens, usage.completion_tokens)
        return Reply(text=response.choices[0].message.content or "", cost_usd=float(cost or 0.0))
