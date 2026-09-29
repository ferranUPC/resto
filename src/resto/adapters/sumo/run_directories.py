"""`RunDirectories` on the local filesystem."""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from resto.domain.value_objects.artifact_ref import ArtifactRef


class FilesystemRunDirectories:
    def prepare(self, staging_dir: Path) -> None:
        staging_dir.mkdir(parents=True, exist_ok=True)

    def promote(
        self, staging_dir: Path, canonical_dir: Path, artifacts: Sequence[ArtifactRef]
    ) -> tuple[ArtifactRef, ...]:
        if canonical_dir.exists():
            shutil.rmtree(canonical_dir)
        staging_dir.rename(canonical_dir)
        return tuple(_relocated(a, staging_dir, canonical_dir) for a in artifacts)


def _relocated(ref: ArtifactRef, old_dir: Path, new_dir: Path) -> ArtifactRef:
    try:
        return replace(ref, path=new_dir / ref.path.relative_to(old_dir))
    except ValueError:
        return ref
