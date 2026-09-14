# ADR-0009: MCP as transport, not a layer

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.1, §2.4

## Context

MCP servers are needed so external parties can plug into DatabaseMCP (the pluggable-backend contract,
ADR-0012) and, as a Stretch goal, drive TraciMCP live. Treating "MCP server" as its own software layer risks
duplicating tool logic between an in-process call path (the framework calling its own tools) and an
MCP-server call path (an external client calling the same tools over the wire).

## Decision

Every tool exists first as a typed Python function in `application/tools/`. MCP servers
(`interface/mcp/{network,database,traci}_server.py`) are thin **driving** adapters — the same role the CLI
plays — that expose those functions to an external client and contain no logic beyond protocol plumbing. The
framework itself always calls tools in-process; it never goes through its own MCP server to talk to itself.
MCP is required only where an external party genuinely plugs in (DatabaseMCP's conformance-tested pluggable
backend, §4.9) and optional everywhere else (TraciMCP is Stretch-only, §2.4).

## Consequences

- Tool logic is tested once, as a plain function, regardless of whether it's ever exercised over MCP.
- `interface/` stays a thin translation layer, consistent with the rest of the hexagonal architecture's rule
  that interface adapters hold no logic.
- DatabaseMCP's conformance suite (E1.5) can run the same test bodies against the in-process repository
  adapters and against `mcp_client` — the point being that the two paths are provably interchangeable.
- Server-side optimizations that would only make sense at the wire level (e.g. a query pushed down
  differently for a remote client) have no natural home, since the logic lives below the transport.
  Accepted: this thesis's scale creates no such need, and adding one would mean breaking the
  logic-lives-in-`application/` rule for a hypothetical case.

## Alternatives considered

- **Implement tool logic inside MCP server handlers directly.** Rejected: couples core logic to one specific
  transport and means in-process testing would require spinning up a server.
- **A separate "service layer" between `application/` and the MCP servers.** Rejected: the typed function in
  `application/tools/` already is that layer — adding another is the exact ceremony principle 8 (§1) rules
  out.
