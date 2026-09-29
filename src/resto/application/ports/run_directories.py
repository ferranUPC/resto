"""Where a simulation attempt's files live on disk: the staging directory it runs in, and the
canonical directory an ok result is promoted to."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef


class RunDirectories(Protocol):
    def prepare(self, staging_dir: Path) -> None:
        """Creates `staging_dir` (and its parents) if it does not exist."""
        ...

    def promote(
        self, staging_dir: Path, canonical_dir: Path, artifacts: Sequence[ArtifactRef]
    ) -> tuple[ArtifactRef, ...]:
        """Makes `staging_dir` the `canonical_dir`, replacing a leftover one, and returns
        `artifacts` with the paths under `staging_dir` relocated. A ref outside `staging_dir` is
        returned unchanged."""
        ...
