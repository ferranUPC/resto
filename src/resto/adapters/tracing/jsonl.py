"""JSONL tracer (E0.7): append-only study trace, one JSON object per line.

Implements `application.ports.tracing.Tracer`. One file per study (`{root}/{study_id}.jsonl`). Each
line holds the event's name, a timestamp and the event's fields; the first line of a file also holds
`schema_version`. `read_run` rebuilds the typed events. The format is internal: bump
`SCHEMA_VERSION` when it changes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, get_args

from resto.application.ports.tracing import TraceEvent
from resto.application.schemas import adapter_for

SCHEMA_VERSION = 1

_EVENT_TYPES: dict[str, type] = {t.__name__: t for t in get_args(TraceEvent)}


class JsonlTracer:
    """Appends one JSON record per line to `{root}/{study_id}.jsonl`."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def emit(self, study_id: str, event: TraceEvent) -> None:
        path = self._root / f"{study_id}.jsonl"
        record: dict[str, Any] = {"event": type(event).__name__}
        if not path.exists():
            record["schema_version"] = SCHEMA_VERSION
        record["ts"] = datetime.now(UTC).isoformat()
        record["data"] = adapter_for(type(event)).dump_python(event, mode="json")
        self._root.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def read_run(root: Path, study_id: str) -> list[TraceEvent]:
    """A study's trace as typed events, in emission order. Empty if it has no trace file."""
    path = root / f"{study_id}.jsonl"
    if not path.exists():
        return []
    events: list[TraceEvent] = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f):
            if not line.strip():
                continue
            record = json.loads(line)
            if n == 0 and record.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(
                    f"trace {path} has schema version {record.get('schema_version')}, "
                    f"expected {SCHEMA_VERSION}"
                )
            event_type = _EVENT_TYPES.get(record["event"])
            if event_type is None:
                raise ValueError(f"trace {path} has an unknown event {record['event']!r}")
            events.append(adapter_for(event_type).validate_python(record["data"]))
    return events
