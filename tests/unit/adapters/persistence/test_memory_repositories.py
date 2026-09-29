"""`InMemory*Repository.store` idempotency/conflict (DATABASE_MCP_CONTRACT.md §3; ADR-0031): each
one must raise `ConflictError` on an existing id with different content, the same as its SQLite
counterpart (`tests/unit/adapters/persistence/sqlite/test_repositories.py`) — `Network` keeps its
`label`-only exemption, `Study` is excluded on purpose (mutable, UUID-keyed, framework-only)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from resto.adapters.persistence.memory import (
    InMemoryDemandRepository,
    InMemoryNetworkRepository,
    InMemoryNoteRepository,
    InMemoryScenarioRepository,
)
from resto.application.ports.errors import ConflictError
from tests.unit.domain._samples import demand, expert_note, network, scenario


def test_network_store_is_idempotent_on_identical_content() -> None:
    repo = InMemoryNetworkRepository()
    net = network()
    repo.store(net)

    repo.store(net)

    assert repo.get(net.network_id) == net


def test_network_store_same_id_different_label_updates_in_place_not_a_conflict() -> None:
    repo = InMemoryNetworkRepository()
    repo.store(network())

    repo.store(replace(network(), label="renamed"))

    assert repo.get(network().network_id).label == "renamed"  # type: ignore[union-attr]


def test_network_store_different_content_same_id_is_conflict() -> None:
    repo = InMemoryNetworkRepository()
    repo.store(network())

    with pytest.raises(ConflictError):
        repo.store(replace(network(), probe_report=None))


def test_demand_store_different_content_same_id_is_conflict() -> None:
    repo = InMemoryDemandRepository()
    repo.store(demand())

    with pytest.raises(ConflictError):
        repo.store(replace(demand(), routes=replace(demand().routes, content_hash="different")))


def test_scenario_store_different_content_same_id_is_conflict() -> None:
    repo = InMemoryScenarioRepository()
    repo.store(scenario())

    with pytest.raises(ConflictError):
        repo.store(replace(scenario(), content_hash="different"))


def test_note_store_different_text_same_id_is_conflict() -> None:
    repo = InMemoryNoteRepository()
    repo.store(expert_note())

    with pytest.raises(ConflictError):
        repo.store(replace(expert_note(), text="a different claim"))
