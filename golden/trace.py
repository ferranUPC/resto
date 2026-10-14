"""Trace files for a golden-path run: one JSONL file per golden path and repetition."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from golden.framework.expected import GoldenPath
from golden.framework.setup import Run, Setup
from resto.adapters.tracing.jsonl import JsonlTracer

DEFAULT_TRACE_ROOT = Path("golden-traces")


def run_directory(root: Path, now: datetime | None = None) -> Path:
    """`root/<UTC time>`, the directory one invocation writes into."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return root / stamp


class TracingSetup:
    """Wraps a `Setup` and writes each run's events to `{directory}/{path}-rep{n}.jsonl`.

    A file that cannot be written prints a warning to stderr and the run goes on."""

    def __init__(self, inner: Setup, directory: Path) -> None:
        self._inner = inner
        self._tracer = JsonlTracer(directory)
        self._directory = directory
        self._count: dict[str, int] = {}
        self._warned = False

    @property
    def repetitions(self) -> int:
        return self._inner.repetitions

    @property
    def compare_repetitions(self) -> bool:
        return self._inner.compare_repetitions

    def run(self, path: GoldenPath) -> Run:
        result = self._inner.run(path)
        n = self._count.get(path.name, 0)
        self._count[path.name] = n + 1
        try:
            for event in result.events:
                self._tracer.emit(f"{path.name}-rep{n}", event)
        except OSError as error:
            if not self._warned:
                self._warned = True
                print(
                    f"warning: cannot write traces to {self._directory}: {error}", file=sys.stderr
                )
        return result
