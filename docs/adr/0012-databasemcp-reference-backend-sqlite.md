# ADR-0012: DatabaseMCP reference backend — SQLite + in-process cosine, not Postgres + `pgvector`

- Status: Accepted — supersedes the original Postgres + `pgvector` choice (kept from v0.1/v0.2 through v0.3)
- Date: 2026-09-11 (recorded in the architecture doc as amendment A1, reconciled into the body at the v1.0 freeze)
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.1, §2.4, §4.9; [`DATABASE_MCP_CONTRACT.md`](../DATABASE_MCP_CONTRACT.md) §9

## Context

DatabaseMCP's original reference implementation (v0.1–v0.3) was Postgres + `pgvector` via SQLAlchemy Core,
budgeted at 24 h (E1.3) plus a Docker service for the reproducible environment (E0.2). `pgvector` exists in
this design for exactly one port method, `NoteRepository.search` — and the largest note corpus the thesis
ever queries is the learning-effect experiment (§4.7, E4.9) at **25 notes**. The work plan was overcommitted
by roughly 6 % with no contingency (work plan §5), and M2/M3/M5 are the milestones that must not be cut.

## Decision

The reference implementation of the DatabaseMCP contract is **SQLite plus cosine similarity computed in
process** (embeddings stored as a blob column, similarity computed with `numpy`). Postgres + `pgvector` is
deferred, not cancelled. The contract itself does not change: same six capability groups, same tool names
and I/O schemas, same error codes, same conformance suite (E1.5), same two consumption paths (in-process
repository adapters and `mcp_client`). The backend swap is invisible above the repository ports of
`application/ports/repositories.py` — that invisibility is the pluggable-backend claim the contract makes,
and keeping the SQLite implementation conformant is what proves it. Large artifacts stay in the filesystem
artifact store, referenced by `ArtifactRef`, unchanged. The `persistence/postgres/` placeholder package was
renamed to `persistence/sqlite/` to match.

## Consequences

- E0.2 drops the Postgres + `pgvector` Docker service from the reproducible environment.
- E1.3 becomes "DatabaseMCP reference implementation (SQLite + cosine)" at a reduced estimate.
- E1.5's conformance suite is unchanged and becomes the acceptance gate for any later Postgres backend —
  which, being the *second* implementation of an already-specified, already-tested contract, is additive
  work with a ready-made acceptance test. That is itself the strongest evidence the pluggable-backend claim
  was real, stronger than shipping only one backend ever could be.
- Exact cosine over 25 embeddings is a single `numpy` dot product; there is no approximate-nearest-neighbour
  index to validate, tune, or explain in the thesis for a scale this small.
- The remaining five capability groups (`networks`, `demands`, `scenarios`, `results` incl.
  `query_edgedata`, `historical_demand`) are ordinary relational work SQLite serves at the volumes in §3
  without qualification.
- Postgres returns when a note corpus outgrows linear scan (order 10³ notes), when edgedata volume or
  concurrent access outgrows SQLite, or for a real deployment at DLR — none of which this thesis's
  evaluation assets reach.

## Alternatives considered

- **Keep Postgres + `pgvector` as originally planned.** Rejected: buys a production-grade engineering claim,
  not a thesis result, against an overcommitted schedule with milestones that cannot slip.
- **A file-based backend with no relational engine at all (e.g. flat JSON + linear scan).** Rejected: SQLite
  gives the same relational query surface (`query_edgedata`, `find_similar_scenario`) with none of the
  ad hoc indexing a hand-rolled file format would need, at comparable setup cost.
