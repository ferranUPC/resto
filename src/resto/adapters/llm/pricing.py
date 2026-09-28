"""Reads `config/prices.toml`, the single source of truth for OpenRouter per-token prices
(CLAUDE.md "LLM provider & cost policy"; refactor-paid-runs decision 1). A model absent from the
manifest is refused rather than estimated at $0 or a guessed fallback price — see
`UnknownModelError` — so a caller that gates spending on `estimate_cost_usd`/`price_of` fails
before it can spend against an unpriced model.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_MANIFEST_PATH = Path(__file__).resolve().parents[4] / "config" / "prices.toml"


class UnknownModelError(ValueError):
    """A model slug absent from `config/prices.toml`."""

    def __init__(self, model: str) -> None:
        super().__init__(
            f"{model!r} is not priced in config/prices.toml — add it before spending against it"
        )
        self.model = model


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float
    as_of: str


@lru_cache(maxsize=1)
def _manifest() -> dict[str, ModelPrice]:
    with _MANIFEST_PATH.open("rb") as fh:
        raw = tomllib.load(fh)
    return {model: ModelPrice(**fields) for model, fields in raw["models"].items()}


def price_of(model: str) -> ModelPrice:
    """Raises `UnknownModelError` for a model not in `config/prices.toml`."""
    try:
        return _manifest()[model]
    except KeyError:
        raise UnknownModelError(model) from None


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Raises `UnknownModelError` for a model not in `config/prices.toml`."""
    price = price_of(model)
    return (input_tokens * price.input_per_mtok + output_tokens * price.output_per_mtok) / 1_000_000
