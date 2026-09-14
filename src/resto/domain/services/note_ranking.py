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

import math
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

    Convention (pinned here): a zero vector has no direction, so any pair involving one scores
    `0.0` rather than dividing by zero - it is neither "similar" nor "opposite" to anything.
    """
    if len(a) != len(b):
        raise ValueError(f"vectors must have equal dimension, got {len(a)} and {len(b)}")
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (norm_a * norm_b)


def rank_notes(
    query_vector: Vector,
    candidates: Sequence[tuple[ExpertNote, Vector]],
    limit: int = 10,
) -> list[ScoredNote]:
    """Rank candidates by similarity to `query_vector`, highest score first.

    Ties break by `note_id` ascending (contract §6 determinism rule) so a listing is reproducible
    across identical calls regardless of backend. Filtering (`status`, `basis`, `context_tags` -
    contract §5.5) happens before this is called; this function only ranks.
    """
    scored = [
        ScoredNote(note=note, score=cosine_similarity(query_vector, vector))
        for note, vector in candidates
    ]
    scored.sort(key=lambda s: (-s.score, s.note.note_id))
    return scored[:limit]
