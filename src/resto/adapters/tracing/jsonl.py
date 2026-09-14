"""JSONL tracer (E0.7): append-only run trace, one JSON object per line.

Implements `application.ports.tracing.Tracer`. One file per run (`{root}/{study_id}.jsonl`);
callers emit `step`/`tool_call`/`artifact`/`usage` events as they happen and this adapter appends
a timestamped record, tolerating domain dataclasses, `Path`s and `Enum`s in the payload.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


def _json_default(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    return str(value)


class JsonlTracer:
    """Appends one JSON record per line to `{root}/{study_id}.jsonl`."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def emit(self, study_id: str, event: str, payload: Mapping[str, Any]) -> None:
        record = {
            "study_id": study_id,
            "event": event,
            "ts": datetime.now(UTC).isoformat(),
            **payload,
        }
        self._root.mkdir(parents=True, exist_ok=True)
        with self._run_path(study_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=_json_default) + "\n")

    def _run_path(self, study_id: str) -> Path:
        return self._root / f"{study_id}.jsonl"


def read_run(root: Path, study_id: str) -> list[dict[str, Any]]:
    """Read back a run's trace in emission order. Empty list if the run has no trace file."""
    path = root / f"{study_id}.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
