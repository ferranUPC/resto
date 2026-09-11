"""Web access for the Demand Generator; every fetch is snapshotted into the artifact store."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from resto.domain.value_objects.artifact_ref import ArtifactRef


class WebSearch(Protocol):
    def search(self, query: str, max_results: int = 5) -> Sequence[tuple[str, str]]: ...


class WebFetch(Protocol):
    def fetch(self, url: str, out_dir: Path) -> ArtifactRef: ...
