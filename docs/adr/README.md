# Architecture Decision Records

ADRs for RESTO, indexed against [`../tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) v1.0
§7. Only decisions with real alternatives and consequences get an ADR — a fixed catalogue, a flag's
meaning, or a default that moves once E7.4 has measurements is recorded once, in the architecture doc
itself, not here. From v1.0 onward this is the append-only record of *why*: a decision changes by adding a
new ADR that supersedes an old one (as ADR-0012 already supersedes the original, pre-ADR Postgres +
`pgvector` choice), never by silently editing one in place.

Format: lightweight (context / decision / consequences / alternatives considered), one file per decision,
numbered in the order they were taken.

| ID | Title | Date | Status |
|---|---|---|---|
| [0001](0001-tool-agent-port-and-draft-promotion.md) | Single `ToolAgent` port; agents return drafts, promotion is code | 2026-09-11 | Accepted |
| [0002](0002-domain-model-aggregates-and-identity-policy.md) | Domain model: six aggregates, `Study` as the run-time root, identity by content/request hash vs UUID | 2026-09-11 | Accepted |
| [0003](0003-network-edits-via-typed-tools-on-plain-xml.md) | Network edits only via typed tools on plain XML; recipe stored and replayable | 2026-09-11 | Accepted |
| [0004](0004-network-author-vs-scenario-builder-boundary.md) | Network Author vs Scenario Builder boundary — derivation vs intervention | 2026-09-11 | Accepted |
| [0005](0005-traci-api-scripts-as-the-single-dynamic-mechanism.md) | `resto.traci_api` scripts as the single dynamic mechanism | 2026-09-11 | Accepted |
| [0006](0006-demand-as-aggregate-with-calibration-loop.md) | `Demand` as an aggregate with a calibration loop against control-edge counts | 2026-09-11 | Accepted |
| [0007](0007-scenario-builder-static-mechanism-writers.md) | Scenario Builder static mechanisms — one writer per mechanism behind `AdditionalFileWriter` | 2026-09-11 | Accepted |
| [0008](0008-stdlib-dataclasses-with-typeadapter-boundary.md) | stdlib dataclasses + `pydantic.TypeAdapter` at the boundary, no `contracts/` package | 2026-09-11 | Accepted |
| [0009](0009-mcp-as-transport-not-a-layer.md) | MCP as transport, not a layer | 2026-09-11 | Accepted |
| [0010](0010-sumo-version-pin.md) | SUMO 1.27.1 pinned from PyPI, no `SUMO_HOME` | 2026-09-11 | Accepted |
| [0011](0011-network-expert-knowledge-model.md) | Network Expert knowledge model — facts via tools, opinions via `ExpertNote` RAG | kept from v0.1/v0.2 | Accepted |
| [0012](0012-databasemcp-reference-backend-sqlite.md) | DatabaseMCP reference backend — SQLite + in-process cosine, not Postgres + `pgvector` | 2026-09-11 | Accepted — supersedes the original Postgres + `pgvector` choice |
| [0013](0013-network-label-no-network-group-aggregate.md) | `Network.label`; no `NetworkGroup` aggregate | 2026-09-14 | Accepted |
| [0014](0014-note-ranking-domain-pure-algorithm.md) | Note ranking is a fixed, domain-pure algorithm | 2026-09-14 | Accepted |
| [0015](0015-capacity-estimate-greenshields-with-sumo-default-jam-density.md) | `capacity_estimate` — Greenshields estimate, jam density derived from SUMO's default vehicle length/minGap | 2026-09-14 | Accepted |
| [0016](0016-hashing-embedder-for-databasemcp-reference-notes.md) | Reference `Embedder` is a deterministic hashing/bag-of-words vectorizer, not a real embedding model | 2026-09-14 | Accepted |
