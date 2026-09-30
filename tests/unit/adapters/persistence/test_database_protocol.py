"""Both backends are a `Database` (mypy checks the assignments); the in-memory one has no
`historical_demand`; the DatabaseMCP server does not import the SQLite package."""

from __future__ import annotations

import asyncio
import inspect

from resto.adapters.persistence.memory import InMemoryDatabase
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.application.ports.repositories import Database, HistoricalDemandSource
from resto.interface.mcp import database_server
from resto.interface.mcp.database_server import build_server


def test_both_backends_satisfy_the_database_protocol() -> None:
    sqlite: Database = SqliteDatabase(":memory:")
    memory: Database = InMemoryDatabase()

    for database in (sqlite, memory):
        assert {"networks", "demands", "scenarios", "results", "notes"} <= set(vars(database))
        assert not hasattr(database, "studies")


def test_the_in_memory_database_offers_no_historical_demand() -> None:
    database = InMemoryDatabase()

    capability = [n for n in dir(HistoricalDemandSource) if not n.startswith("_")]
    assert capability == ["get_historical_demand"]
    assert not any(hasattr(database, name) for name in capability)


def test_the_server_built_on_the_in_memory_database_lists_the_same_tools_as_on_sqlite() -> None:
    memory_tools = {t.name for t in asyncio.run(build_server(InMemoryDatabase()).list_tools())}
    sqlite = SqliteDatabase(":memory:")
    try:
        sqlite_tools = {t.name for t in asyncio.run(build_server(sqlite).list_tools())}
    finally:
        sqlite.close()

    assert memory_tools == sqlite_tools


def test_the_server_module_does_not_import_the_sqlite_package() -> None:
    assert "persistence.sqlite" not in inspect.getsource(database_server)
