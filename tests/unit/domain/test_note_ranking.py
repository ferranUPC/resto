"""cosine_similarity / rank_notes (DATABASE_MCP_CONTRACT.md §5.5, ADR-0014): the one ranking
algorithm every conformant DatabaseMCP backend must reproduce, independent of the embedder."""

from __future__ import annotations

import math

import pytest

from resto.domain.entities.expert_note import ExpertNote, Provenance
from resto.domain.services.note_ranking import cosine_similarity, rank_notes
from resto.domain.value_objects.expert_answer import Basis


def _note(note_id: str) -> ExpertNote:
    return ExpertNote(
        note_id=note_id,
        network_id="n1",
        study_id="s1",
        text="some observation",
        provenance=Provenance.OPINION,
        basis=Basis.OBSERVED,
    )


def test_cosine_similarity_of_identical_vectors_is_one() -> None:
    assert cosine_similarity((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors_is_zero() -> None:
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)


def test_cosine_similarity_of_opposite_vectors_is_minus_one() -> None:
    assert cosine_similarity((1.0, 0.0), (-1.0, 0.0)) == pytest.approx(-1.0)


def test_cosine_similarity_is_scale_invariant() -> None:
    assert cosine_similarity((1.0, 2.0), (2.0, 4.0)) == pytest.approx(1.0)


def test_cosine_similarity_zero_vector_scores_zero_not_a_division_error() -> None:
    assert cosine_similarity((0.0, 0.0), (1.0, 2.0)) == 0.0
    assert cosine_similarity((0.0, 0.0), (0.0, 0.0)) == 0.0


def test_cosine_similarity_rejects_mismatched_dimensions() -> None:
    with pytest.raises(ValueError, match="dimension"):
        cosine_similarity((1.0, 2.0), (1.0, 2.0, 3.0))


def test_rank_notes_orders_by_score_descending() -> None:
    a, b, c = _note("a"), _note("b"), _note("c")
    candidates = [
        (a, (1.0, 0.0)),  # similarity 1.0 to query (1, 0)
        (b, (0.0, 1.0)),  # similarity 0.0
        (c, (0.7071, 0.7071)),  # similarity ~0.707
    ]

    ranked = rank_notes((1.0, 0.0), candidates)

    assert [s.note.note_id for s in ranked] == ["a", "c", "b"]
    assert ranked[0].score == pytest.approx(1.0)


def test_rank_notes_breaks_ties_by_note_id_ascending() -> None:
    z, a = _note("z"), _note("a")
    candidates = [(z, (1.0, 0.0)), (a, (1.0, 0.0))]  # identical score

    ranked = rank_notes((1.0, 0.0), candidates)

    assert [s.note.note_id for s in ranked] == ["a", "z"]


def test_rank_notes_respects_limit() -> None:
    candidates = [(_note(str(i)), (1.0, 0.0)) for i in range(5)]

    ranked = rank_notes((1.0, 0.0), candidates, limit=2)

    assert len(ranked) == 2


def test_rank_notes_of_empty_candidates_is_empty() -> None:
    assert rank_notes((1.0, 0.0), []) == []


def test_rank_notes_matches_hand_computed_cosine_for_a_realistic_case() -> None:
    # sanity check the two functions agree, not just internally consistent with each other
    note = _note("n")
    query = (1.0, 1.0, 0.0)
    candidate = (1.0, 0.0, 0.0)
    expected = 1.0 / math.sqrt(2.0)

    [scored] = rank_notes(query, [(note, candidate)])

    assert scored.score == pytest.approx(expected)
