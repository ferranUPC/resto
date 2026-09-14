"""Pure ranking algorithm for ExpertNote retrieval (DATABASE_MCP_CONTRACT.md §5.5/§9 amendment A2).

`search_notes` ranks notes by semantic similarity to a query. Two backends using different
embedding models can legitimately produce different vectors for the same text — that stays
pluggable (contract §10, open point 2) — but once vectors exist, turning them into a ranked,
deterministic list must not vary between implementations, or two backends storing identical notes
could disagree on which ones are "most similar" for reasons that have nothing to do with the
embedder, making the learning-effect numbers (DoD §4.7, E4.9) incomparable.

This module fixes that half of the problem. It operates on `Vector` — a plain tuple of floats —
never on text or a model, so it stays domain-pure (stdlib only; see architecture "domain/ never
imports from other layers") while still being the one algorithm every conformant backend must
reproduce. Turning `ExpertNote.text` into a `Vector` is infrastructure and lives behind
`application.ports.embedding.Embedder` instead — this module never imports it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from resto.domain.entities.expert_note import ExpertNote

Vector = tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ScoredNote:
    """One ranked result: an ExpertNote plus its similarity score."""

    note: ExpertNote
    score: float


def cosine_similarity(a: Vector, b: Vector) -> float:
    """Cosine similarity between two embedding vectors of equal dimension.

    Placeholder: dot product over the product of norms; convention for the zero-vector edge case
    (score 0.0 rather than a division by zero) still needs to be pinned when this is implemented.
    """
    raise NotImplementedError("cosine_similarity: see docs/DATABASE_MCP_CONTRACT.md §5.5")


def rank_notes(
    query_vector: Vector,
    candidates: Sequence[tuple[ExpertNote, Vector]],
    limit: int = 10,
) -> list[ScoredNote]:
    """Rank candidates by similarity to `query_vector`, highest score first.

    Ties must break by `note_id` ascending (contract §6 determinism rule) so a listing is
    reproducible across identical calls regardless of backend. Filtering (`status`, `basis`,
    `context_tags` — contract §5.5) happens before this is called; this function only ranks.

    Placeholder: see docs/DATABASE_MCP_CONTRACT.md §5.5 and architecture §9 amendment A2.
    """
    raise NotImplementedError("rank_notes: see docs/DATABASE_MCP_CONTRACT.md §5.5")
