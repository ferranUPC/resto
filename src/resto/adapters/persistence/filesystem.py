"""Filesystem artifact store: large files live on disk and are referenced by `ArtifactRef`
(DoD §2.4, "never in the database"). For now the store is the directory the caller chose; what
this module owns is how a file on disk becomes an `ArtifactRef` - its `content_hash` is the
sha256 of the bytes, so two identical files anywhere yield the same reference."""

from __future__ import annotations

import hashlib
from pathlib import Path

from resto.domain.value_objects.artifact_ref import ArtifactRef


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def artifact_ref(path: Path, kind: str) -> ArtifactRef:
    """`ArtifactRef` for a file we wrote ourselves: the hash covers the raw bytes."""
    return ArtifactRef(path=path.resolve(), content_hash=sha256_of(path.read_bytes()), kind=kind)
