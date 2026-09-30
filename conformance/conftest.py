"""One `db` fixture, parametrized over every DatabaseMCP backend this project ships. Adding a
second backend (the Postgres + `pgvector` stretch goal, contract §9) means adding one entry to
`_BACKENDS` below - every test in this suite then runs against it unchanged, which is the whole
point of a conformance suite (§8: "any implementation").

Every backend is fronted by the real `interface/mcp/database_server.py` and reached only through
`adapters/persistence/mcp_client.py` over an in-memory MCP transport (no subprocess, no network,
but a real MCP session none the less - `mcp.client._memory.InMemoryTransport` wires a real
`ClientSession` to a real `MCPServer` in-process). A test in this suite therefore never imports a
backend's repository classes directly and never reaches past the `db.networks/.demands/.scenarios
/.results/.notes` surface - reaching further would defeat the suite's purpose of exercising only
what the contract actually promises.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from mcp.client._memory import InMemoryTransport
from mcp.server.mcpserver import MCPServer

from resto.adapters.persistence.mcp_client import McpClientDatabase
from resto.adapters.persistence.memory import InMemoryDatabase
from resto.adapters.persistence.sqlite.repositories import SqliteDatabase
from resto.interface.mcp.database_server import build_server


def _sqlite() -> tuple[MCPServer, Callable[[], None]]:
    backend = SqliteDatabase(":memory:")
    return build_server(backend), backend.close


def _memory() -> tuple[MCPServer, Callable[[], None]]:
    return build_server(InMemoryDatabase()), lambda: None


_BACKENDS: dict[str, Callable[[], tuple[MCPServer, Callable[[], None]]]] = {
    "memory": _memory,
    "sqlite": _sqlite,
}


@pytest.fixture(params=sorted(_BACKENDS), ids=sorted(_BACKENDS))
def db(request: pytest.FixtureRequest) -> Iterator[McpClientDatabase]:
    server, release = _BACKENDS[request.param]()
    client = McpClientDatabase(lambda: InMemoryTransport(server))
    try:
        yield client
    finally:
        client.close()
        release()
