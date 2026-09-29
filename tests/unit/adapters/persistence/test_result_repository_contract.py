"""Shared `ResultRepository` contract (DATABASE_MCP_CONTRACT.md §3; ADR-0031): every backend must
agree on idempotency and conflict, not just the SQLite reference implementation. Parametrized over
both repositories so a regression in either one fails here, not only in production."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import replace

import pytest

from resto.adapters.persistence.memory import InMemoryResultRepository
from resto.adapters.persistence.sqlite.repositories import SqliteResultRepository, connect
from resto.application.ports.errors import ConflictError
from resto.application.ports.repositories import ResultRepository
from tests.unit.domain._samples import simulation_result


@pytest.fixture(params=["memory", "sqlite"])
def results(request: pytest.FixtureRequest) -> Iterator[ResultRepository]:
    if request.param == "memory":
        yield InMemoryResultRepository()
        return
    conn: sqlite3.Connection = connect(":memory:")
    yield SqliteResultRepository(conn)
    conn.close()


def test_existing_id_identical_content_is_a_no_op(results: ResultRepository) -> None:
    result = simulation_result()
    results.store(result)

    results.store(result)

    assert results.get(result.result_id) == result


def test_existing_id_different_content_is_conflict(results: ResultRepository) -> None:
    result = simulation_result()
    results.store(result)
    changed = replace(result, wall_clock_s=(result.wall_clock_s or 0.0) + 1.0)

    with pytest.raises(ConflictError):
        results.store(changed)

    assert results.get(result.result_id) == result  # the original is untouched
