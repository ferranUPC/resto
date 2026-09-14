"""Port for turning text into an embedding vector — the one infrastructure-dependent step of
note retrieval (architecture §9 amendment A2). `application/` may depend on this; `domain/` never
does — `domain.services.note_ranking` operates on `Vector`, plain data, and knows nothing about
how a `Vector` is produced.

Implementations live in `adapters/` (e.g. a wrapped local embedding model). The DatabaseMCP
reference implementation pins one specific embedder so the thesis's E4.9 numbers are reproducible;
a third-party backend may plug in a different one and remains conformant, at the cost of its
rankings no longer being numerically comparable to the reference's
(docs/DATABASE_MCP_CONTRACT.md §10, open point 2).
"""

from __future__ import annotations

from typing import Protocol

from resto.domain.services.note_ranking import Vector


class Embedder(Protocol):
    """Turns text into a fixed-dimension embedding vector."""

    def embed(self, text: str) -> Vector:
        """Embed one piece of text (a query, or an `ExpertNote.text` at `store_note` time).

        Must be deterministic: the same text always yields the same `Vector`, since note
        embeddings are meant to be computed once and reused, not recomputed per search.
        """
        ...

    @property
    def dimension(self) -> int:
        """Length of every `Vector` this embedder produces — fixed per instance."""
        ...
