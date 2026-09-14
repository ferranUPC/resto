# ADR-0014: Note ranking is a fixed, domain-pure algorithm

- Status: Accepted
- Date: 2026-09-14 (recorded in the architecture doc as amendment A2, part 2; reconciled into the body at the v1.0 freeze)
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.4, §2.6; [`DATABASE_MCP_CONTRACT.md`](../DATABASE_MCP_CONTRACT.md) §5.5, §10 open point 2

## Context

`DATABASE_MCP_CONTRACT.md` left `search_notes`'s entire scoring behavior server-owned, since it takes a text
query rather than a vector (§10, open point 2). That conflated two things that vary for genuinely different
reasons: the embedding model (legitimately server-owned — different backends may embed differently) and the
ranking step that turns vectors into an ordered, scored list (left implicitly server-owned too, for no good
reason — two backends embedding identically could still disagree on how to rank the result, purely from a
different tie-breaking or scoring rule).

## Decision

Fix only the ranking half. `domain.services.note_ranking.rank_notes` — cosine similarity, ties broken by
`note_id` ascending (per the determinism rule in §6) — is now the one algorithm every conformant DatabaseMCP
implementation must reproduce, checked by the conformance suite (E1.5) against fixed vector fixtures,
independent of any embedder, so the check needs no model to run. The embedding-model half of open point 2
stays open exactly as before: `search_notes` still takes text, so which model produces the vector remains
server-owned and genuinely pluggable.

`rank_notes` operates on `Vector = tuple[float, ...]` — plain data, never text, never a model — which is why
fixing it doesn't create a `domain/` → infrastructure dependency. Producing a `Vector` from `ExpertNote.text`
is the actual infrastructure-dependent step, and it stays behind a port,
`application.ports.embedding.Embedder`, which `domain/` does not import. This is the same split
`domain/services/ids.py` already makes for id policy (pure hashing in `domain/`, the artifacts being hashed
produced elsewhere) applied to retrieval.

## Consequences

- Half of "why did these two backends disagree" can no longer be the ranking rule itself — only the embedder
  underneath it, which is now the only axis of legitimate variation left.
- The learning-effect experiment's numbers (E4.9) are directly comparable across any two implementations
  that share an embedder, and the reference implementation pins one model so its own numbers stay
  reproducible run to run; comparability across implementations using *different* embedders is stated as a
  known limitation in the thesis, not silently assumed away.
- `NoteRepository.search`'s signature (§2.4) and the DatabaseMCP tool surface (§5.5) are unchanged — this
  amendment pins an algorithm that was previously unspecified, it doesn't change any interface.
- `domain/services/note_ranking.py` (`Vector`, `ScoredNote`, `cosine_similarity`, `rank_notes`) and
  `application/ports/embedding.py` (`Embedder`) exist as typed placeholders ahead of E1.3/E1.5 implementing
  them for real.

## Alternatives considered

- **Leave ranking server-owned along with embedding.** Rejected: makes "two conformant backends disagree" an
  unfalsifiable claim about the whole retrieval pipeline instead of a specific, statable limitation about the
  embedder alone.
- **Pin the embedding model too, in the contract itself.** Rejected: `search_notes` deliberately takes text,
  not a vector, so the server must own how it turns text into a vector — pinning the model would remove a
  degree of freedom the contract's own signature already grants implementations.
