"""Contract §8 item 6: `search_notes` - `status`/`basis` filters narrow the ranking, filters are
never relaxed (a filter matching nothing returns nothing, it does not fall back to unfiltered),
cross-network isolation, an unknown filter key is rejected. 5 cases.

Ranking goes through the server's real `HashingEmbedder` (not a test double), so every case below
queries with the exact text of the note it expects first: under L2-normalised cosine similarity
that scores the maximum 1.0, which an unrelated note's independently-hashed vector will not also
hit (`domain/services/note_ranking.py` ties break by `note_id` regardless)."""

from __future__ import annotations

import dataclasses

import pytest
from tests.unit.domain._samples import expert_note

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.application.ports.errors import InvalidArgumentError
from resto.domain.entities.expert_note import NoteStatus
from resto.domain.value_objects.expert_answer import Basis


def test_status_filter_narrows_the_ranking(db: McpClientDatabase) -> None:
    unverified = dataclasses.replace(expert_note(), note_id="a", text="lane closure on E12")
    confirmed = dataclasses.replace(
        expert_note(),
        note_id="b",
        text="lane closure on E12",
        status=NoteStatus.CONFIRMED,
    )
    db.notes.store(unverified)
    db.notes.store(confirmed)

    results = db.notes.search(
        "lane closure on E12", unverified.network_id, {"status": ["confirmed"]}
    )

    assert [n.note_id for n, _score in results] == ["b"]


def test_basis_filter_narrows_the_ranking(db: McpClientDatabase) -> None:
    observed = dataclasses.replace(
        expert_note(), note_id="a", text="E12 saturates at peak", basis=Basis.OBSERVED
    )
    extrapolated = dataclasses.replace(
        expert_note(), note_id="b", text="E12 saturates at peak", basis=Basis.EXTRAPOLATED
    )
    db.notes.store(observed)
    db.notes.store(extrapolated)

    results = db.notes.search("E12 saturates at peak", observed.network_id, {"basis": ["observed"]})

    assert [n.note_id for n, _score in results] == ["a"]


def test_a_filter_matching_nothing_returns_nothing_not_the_unfiltered_list(
    db: McpClientDatabase,
) -> None:
    note = dataclasses.replace(
        expert_note(), note_id="a", text="E12 saturates", status=NoteStatus.UNVERIFIED
    )
    db.notes.store(note)

    results = db.notes.search("E12 saturates", note.network_id, {"status": ["refuted"]})

    assert results == []


def test_results_are_scoped_to_one_network(db: McpClientDatabase) -> None:
    in_scope = dataclasses.replace(
        expert_note(), note_id="a", network_id="n1", scenario_id="s-a", text="note in scope"
    )
    elsewhere = dataclasses.replace(
        expert_note(), note_id="b", network_id="n2", scenario_id="s-b", text="note in scope"
    )
    db.notes.store(in_scope)
    db.notes.store(elsewhere)

    results = db.notes.search("note in scope", "n1", {})

    assert [n.note_id for n, _score in results] == ["a"]


def test_unknown_filter_key_is_rejected(db: McpClientDatabase) -> None:
    note = expert_note()
    db.notes.store(note)

    with pytest.raises(InvalidArgumentError):
        db.notes.search("q", note.network_id, {"nonexistent_filter": ["x"]})
