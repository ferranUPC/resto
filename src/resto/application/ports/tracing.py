"""Append-only run trace (E0.7): steps, tool calls, artifacts, tokens -> JSONL."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class Tracer(Protocol):
    def emit(self, study_id: str, event: str, payload: Mapping[str, Any]) -> None: ...
