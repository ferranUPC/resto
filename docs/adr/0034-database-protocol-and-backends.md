# ADR-0034: The DatabaseMCP server takes a `Database`, not a SQLite class

- Status: Accepted (2026-09-29) — refines the DatabaseMCP paragraph of §2.2 (SQLite reference
  implementation, ADR-0012); does not change the contract
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2, §4 layout;
  refactor r2 ([work plan §7](../tfm-work-plan.md#7-deviations-from-the-plan))

## Context

§2.2 describes the DatabaseMCP as a standard contract with a pluggable backend, yet the frozen text also
names the SQLite package as the in-process adapter and `interface/mcp/database_server.py` as the server that
exposes it. In code the coupling went further: `build_server` was typed to `SqliteDatabase`, so no other
backend could sit behind the server, and the in-memory repositories could drift from SQLite unnoticed.

## Decision

- `Database` is a protocol in `application/ports/repositories.py`. It has the five DatabaseMCP repositories
  (networks, demands, scenarios, results, notes) as attributes, by composition. `StudyRepository` is not part
  of it, and `close` is not either: whoever opens a backend knows its concrete type and closes it.
- `build_server` accepts any `Database`, and `database_server.py` imports no backend. The SQLite launcher is
  `interface/mcp/database_sqlite_main.py`.
- `InMemoryDatabase` (`adapters/persistence/memory.py`) is the second implementation. It has no
  `historical_demand`, which lets GP-10 check the Coordinator against a backend without that capability.
- The conformance suite runs on `memory` and `sqlite`. SQLite stays the reference implementation.

## Consequences

- Where §2.2 and §4 name `persistence/sqlite/` or `database_server.py` as the DatabaseMCP's implementation,
  read them as the reference backend and its server. The frozen text is not edited.
- A new backend (the Postgres stretch goal) adds one entry to the conformance backends and implements
  `Database`.
