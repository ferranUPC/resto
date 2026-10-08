"""The `agentic` setup: a model and limits per agent. Protocol only in E9.1.

The per-agent configuration arrives with E12.1, so there is no implementation here and
`python -m golden.run --setup agentic` is rejected. An implementation must satisfy `AgenticSetup`
and reuse the golden path definitions and the comparator unchanged. Before it makes a model call it
prints `estimate_cost` and asks for confirmation (`docs/llm-cost-policy.md`).
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol, runtime_checkable

from golden.framework.expected import GoldenPath
from golden.framework.setup import Setup


@runtime_checkable
class AgenticSetup(Setup, Protocol):
    @property
    def models(self) -> Mapping[str, str]:
        """The model id each agent runs on, by agent name."""
        ...

    def estimate_cost(self, paths: tuple[GoldenPath, ...]) -> Decimal:
        """Estimated cost in USD of running `paths` with `repetitions` each, shown before any
        model call."""
        ...


__all__ = ["AgenticSetup"]
