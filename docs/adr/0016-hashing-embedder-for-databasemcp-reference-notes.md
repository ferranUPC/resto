# ADR-0016: Reference `Embedder` is a deterministic hashing/bag-of-words vectorizer, not a real embedding model

- Status: Accepted
- Date: 2026-09-14
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §4.9; [`DATABASE_MCP_CONTRACT.md`](../DATABASE_MCP_CONTRACT.md) §5.5, §10 open point 2; work-plan E1.3

## Context

`search_notes` ranks `ExpertNote`s by similarity to a query. The contract deliberately leaves
*which embedder* server-owned (§10 open point 2) — only the ranking step on top of the vectors is
pinned (`domain.services.note_ranking`, ADR-0014). E1.3's reference implementation still needs
one concrete `Embedder` (`application/ports/embedding.py`) to be runnable and testable at all.

The real choice is between retrieval *quality* (what E4.9's learning-effect benchmark ultimately
cares about) and *engineering cost now* (a new dependency, network calls, or non-determinism) —
for a reference/conformance-testing implementation, not yet the tuned Expert benchmark itself.

## Decision

The reference `Embedder` (`adapters/embedding/hashing.py`) is a deterministic hashing/bag-of-words
vectorizer: lowercase + tokenize the text, hash each token with `hashlib.sha256` (never Python's
built-in `hash()`, which is randomized per-process for strings and would make embeddings
non-reproducible run to run) into one of `dimension` buckets with a sign derived from the same
digest, accumulate, then L2-normalize. Zero new dependencies, fully offline, deterministic by
construction.

This is explicitly a placeholder for retrieval *quality*, not for the contract: it sits entirely
behind `Embedder`, so swapping it for a real embedding model later (local model or hosted API)
touches nothing above the port — same reasoning as `NetworkQuery`/`SumolibNetworkQuery` (ADR-0009).
The swap should happen before E4.9 (the learning-effect experiment) is run for real, since that is
where retrieval quality becomes a thesis result rather than a conformance detail.

## Consequences

- E1.3 (conformance suite, round-trip fidelity, filter/status logic, the fixed ranking algorithm)
  can be built and tested now with zero new dependencies and no network access — CI stays offline.
- Retrieval *quality* on this embedder is weak (no real semantic understanding, just token
  overlap under hashing) — acceptable for conformance testing and early Expert dogfooding, not
  acceptable as the number reported in E4.9. Tracked as a known gap to close before that task, and
this ADR is that record.
- Because embeddings are computed once at `store_note` time and reused, swapping the embedder
  later requires re-embedding the existing note corpus (cheap at this thesis's scale, ≤25 notes).

## Alternatives considered

- **A local embedding model (e.g. sentence-transformers).** Rejected for now: adds a heavy
  dependency (torch + a model download), slows tests, and introduces some cross-hardware
  floating-point non-determinism to manage — real quality gain, but premature before E4.9 needs it.
- **A hosted embeddings API.** Rejected: breaks offline/deterministic test runs, adds cost and a
  network dependency this project has avoided everywhere else (CLAUDE.md's environment rules).
