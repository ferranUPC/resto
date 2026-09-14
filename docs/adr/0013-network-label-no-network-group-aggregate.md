# ADR-0013: `Network.label`; no `NetworkGroup` aggregate

- Status: Accepted
- Date: 2026-09-14 (recorded in the architecture doc as amendment A2, part 1; reconciled into the body at the v1.0 freeze)
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3; [`DATABASE_MCP_CONTRACT.md`](../DATABASE_MCP_CONTRACT.md) §5.1, §10 open point 1

## Context

`Network`'s id is a `content_hash` of the `.net.xml` (ADR-0002) — correct for identity, but useless as
something a person or a Coordinator can refer to by name. §2.3/§2.4 already mentioned looking a network up
by "name" before this decision, but `Network` had no name field, and `find_network` had no matching
parameter (`DATABASE_MCP_CONTRACT.md` §10, open point 1). The motivating case: a set of edits on a "Berlin"
base network, each one its own `Network` by content hash, that a user still wants to refer to as a group —
e.g. "berlin/remove_edge_118".

## Decision

`Network` gains an optional `label: str | None` field: a human-facing, opaque handle, **not** part of
`network_id`. `find_network` gains a matching `label` parameter (`find_network(source, derived_from,
label)`), with exact match required and prefix match (`find_network(label_prefix=…)`) as the mechanism for
the grouping use case — `label` is treated the way an object store treats a key: an opaque path it never
parses, not a modelled parent-child relationship. No `NetworkGroup` aggregate is introduced. Because `label`
carries no identity claim, it is exempt from the DatabaseMCP conflict rule (`DATABASE_MCP_CONTRACT.md` §3)
the same way `ExpertNote`'s id is: a repeated `store_network` for an existing id with the same `net_xml`
content hash but a different `label` is an update, not a `CONFLICT`.

## Consequences

- Resolves DATABASE_MCP_CONTRACT.md open point 1 by adding the field §10 had already flagged as the more
  useful fix, rather than dropping the stale "name" mention from the architecture doc.
- A naming convention inside one string field (`label`) covers the concrete grouping need (prefix matching a
  set of derived networks) without a second aggregate needing its own identity, repository, and lifecycle
  rules for a TFM-scale corpus that never needs more than that.
- `label` being exempt from the conflict rule means relabeling an existing network is cheap and doesn't
  collide with its content-hash identity — the two concerns (what bytes this is vs. what a person calls it)
  stay fully decoupled.
- No hierarchy is enforced between a base network and its derivations beyond what `derived_from` (ADR-0002)
  already records structurally; `label` is purely a human convenience layered on top, not a second source of
  truth about lineage.

## Alternatives considered

- **A `NetworkGroup` aggregate with its own id, owning a set of `Network` ids.** Rejected: needs its own
  identity policy, repository, and conflict rules for a need `label` plus prefix matching already covers —
  the same reasoning ADR-0012 applies against a production-grade backend this thesis's scale never requires.
- **Fold a name into `network_id` itself (e.g. hash the name together with content).** Rejected: two
  networks with identical content but different names would then get different ids, breaking the
  content-hash dedup property ADR-0002 relies on.
