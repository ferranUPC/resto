from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Reference to a file in the artifact store, identified by content hash."""

    path: Path
    content_hash: str
    kind: str

    def __post_init__(self) -> None:
        if not self.content_hash:
            raise ValueError("an ArtifactRef requires a content_hash")
