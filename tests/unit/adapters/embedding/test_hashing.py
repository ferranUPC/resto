"""HashingEmbedder (ADR-0016): deterministic, dimension-fixed, weak-but-sane similarity."""

from __future__ import annotations

import math

import pytest

from resto.adapters.embedding.hashing import HashingEmbedder
from resto.domain.services.note_ranking import cosine_similarity


def test_embed_is_deterministic_across_calls_and_instances() -> None:
    a = HashingEmbedder(dimension=64).embed("B0C0 saturates during the evening peak")
    b = HashingEmbedder(dimension=64).embed("B0C0 saturates during the evening peak")

    assert a == b


def test_embed_returns_a_vector_of_the_configured_dimension() -> None:
    embedder = HashingEmbedder(dimension=32)

    assert len(embedder.embed("some note text")) == 32
    assert embedder.dimension == 32


def test_embed_of_empty_text_is_the_zero_vector() -> None:
    embedder = HashingEmbedder(dimension=16)

    assert embedder.embed("") == (0.0,) * 16
    assert embedder.embed("   ") == (0.0,) * 16


def test_embed_of_nonempty_text_is_unit_normalized() -> None:
    vector = HashingEmbedder(dimension=64).embed("the bottleneck at B0C0 is congested")

    norm = math.sqrt(sum(x * x for x in vector))
    assert norm == pytest.approx(1.0)


def test_shared_vocabulary_scores_higher_than_unrelated_text() -> None:
    embedder = HashingEmbedder(dimension=128)
    query = embedder.embed("bottleneck congestion at the B0C0 approach during peak")
    related = embedder.embed("B0C0 approach is congested at peak, a clear bottleneck")
    unrelated = embedder.embed("traffic light program on the signalised corridor row two")

    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)


def test_dimension_must_be_positive() -> None:
    with pytest.raises(ValueError, match="dimension"):
        HashingEmbedder(dimension=0)
