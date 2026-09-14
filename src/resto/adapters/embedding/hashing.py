"""HashingEmbedder: the reference `Embedder` (ADR-0016) - deterministic, offline, zero new
dependencies, weak retrieval quality by design. Swap behind `application.ports.embedding.Embedder`
before E4.9's learning-effect benchmark needs real semantic quality.

Uses `hashlib.sha256`, never Python's built-in `hash()` - `hash()` on `str` is randomized per
process (PYTHONHASHSEED) unless explicitly disabled, which would make `embed(text)` return a
different vector every run and break the Embedder contract's determinism requirement.
"""

from __future__ import annotations

import hashlib
import math
import re

from resto.domain.services.note_ranking import Vector

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    """Feature-hashing bag-of-words: each token votes +1/-1 on one of `dimension` buckets
    (sign chosen from the same hash, to reduce the bias plain hashing-without-sign would give
    high-collision buckets), then the result is L2-normalized."""

    def __init__(self, dimension: int = 256) -> None:
        if dimension < 1:
            raise ValueError("dimension must be >= 1")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> Vector:
        buckets = [0.0] * self._dimension
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:8], "big") % self._dimension
            sign = 1.0 if digest[8] % 2 == 0 else -1.0
            buckets[index] += sign
        norm = math.sqrt(sum(x * x for x in buckets))
        if norm == 0.0:
            return tuple(buckets)
        return tuple(x / norm for x in buckets)
