# DatabaseMCP — Contract Specification v1.0-draft

The storage contract of the RESTO framework (architecture §2.4). It is a **standard with a
pluggable backend**: the framework ships a reference implementation, and any third party may
supply their own as long as it exposes these tool names, these payloads and these semantics.

Status: draft, frozen as **v1.0** together with the architecture document (E0.8). Until then,
this file is authoritative for tool names, payloads, semantics and error codes; the architecture
document is authoritative for *why* the model looks like this.

Scope:

- **In**: the five required capability groups (`networks`, `demands`, `scenarios`, `results`,
  `notes`) and one optional group (`historical_demand`).
- **Out**: `Study`. It is framework run-time state, not knowledge about networks, and is kept
  through a framework-internal `StudyRepository` (architecture §2.3). A DatabaseMCP
  implementation never sees a `Study`.
- **Out**: artifact bytes. See §4.

---

## 1. Transport, discovery and negotiation

The contract is carried over MCP. Discovery uses MCP's own `tools/list`; there is no bespoke
capability call.

**Capability derivation.** A capability is present **iff every tool listed for it in §5 is
present** in `tools/list`. A partially implemented group is not a capability: a server exposing
`store_note` and `search_notes` but not `update_note_status` does **not** have `notes`.

**Negotiation at start-up** (the Coordinator, work-plan E1.6):

| Situation | Behaviour |
|---|---|
| A required capability is missing | Hard failure at start-up, naming the capability and the missing tools. The framework does not start in a degraded mode for required capabilities. |
| `historical_demand` is missing | The Demand Generator falls back to parameter-driven generation, and the `StudyPlan` records the fallback in `reuse_decisions`. Golden path GP-10 exercises exactly this. |
| An unknown extra tool is present | Ignored. Servers may expose more than the contract. |

Discovery is about *capabilities*, never about data formats: the formats are fixed here and are
not negotiated.

---

## 2. Payloads and schemas

Every entity crossing this boundary is one of the domain aggregates, serialised as JSON.

**The schemas are generated from the code, not written by hand.** They live in `schemas/` at the
repository root, one file per type, regenerated with:

```bash
python -m resto.application.schemas schemas
```

The relevant ones here are `Network.json`, `Demand.json`, `Scenario.json`,
`SimulationResult.json` and `ExpertNote.json`. A test fails if the committed files drift from the
code, so an implementer can treat them as current.

**Round-trip fidelity is the central obligation of this contract.** For every aggregate `x`
accepted by a `store_*` tool, the matching `get_*` must return a value that deserialises equal to
`x` — every field, including optional ones, tuples in their original order, and `frozenset`
members. An implementation that drops `probe_report`, reorders `calibration_rounds` or loses
`context_tags` is non-conformant even if nothing errors. The framework's own round-trip suite
(`tests/unit/domain/test_serialisation.py`) demonstrates the property the backend must preserve.

Servers **must** reject a payload that does not validate against its schema with
`INVALID_ARGUMENT` (§7) rather than storing it partially.

---

## 3. Identity and idempotency

Ids are assigned by the framework, never by the store (architecture §2.2, principle 4). The store
must treat them as opaque strings and must not mint, rewrite or normalise them.

| Aggregate | Id | Derived from |
|---|---|---|
| `Network` | `network_id` | content hash of the `.net.xml` |
| `Demand` | `demand_id` | content hash of the trips artifact |
| `Scenario` | `scenario_id` | hash of (network_id, demand_id, interventions, context_tags) |
| `SimulationResult` | `result_id` | hash of (scenario_id, seed, mode, sumo_version) |
| `ExpertNote` | `note_id` | UUID |

**`store_*` is idempotent.** Storing an entity whose id already exists, with byte-identical
content, is a successful no-op. This is load-bearing: the Coordinator's "zero redundant
simulations" guarantee (DoD §4.2) works by computing an id and storing unconditionally, and
callers retry on transient failures.

**Storing different content under an existing id is `CONFLICT`.** For the four hash-derived ids
this can only mean a broken hash or a corrupted store, so it must be surfaced loudly, never
silently overwritten. `ExpertNote` is one exception: its id is a UUID and carries no content
claim, so a repeated `store_note` with the same `note_id` and different text is also `CONFLICT` —
notes are amended through `update_note_status`, not by rewriting. `Network.label` is a narrower,
field-level exception (§5.1, resolving open point 1): it plays no part in `network_id` and carries
no content claim either, so a repeated `store_network` for an existing id with the same `net_xml`
content hash but a different `label` is **not** `CONFLICT` — the server updates the stored `label`
in place. Every other field of `Network` keeps the general rule.

---

## 4. Artifacts are not stored here

Large files — `.net.xml`, trips, routes, edgedata, tripinfo, summaries, scripts, OSM snapshots —
live in the **filesystem artifact store** and appear in payloads only as `ArtifactRef`
(`path`, `content_hash`, `kind`).

A DatabaseMCP implementation:

- **must** persist and return `ArtifactRef` values unchanged, including `path` exactly as given;
- **must not** attempt to read, copy, rewrite or validate the file a reference points at;
- **must not** make storing an entity conditional on the referenced file existing.

The single exception is `query_edgedata` (§5.4), which by definition reads the edgedata a result
produced. An implementation may satisfy it by parsing the referenced artifact on demand or by
having ingested the measures at `store_result` time; the contract fixes the answer, not the
method.

---

## 5. Capability groups

Signatures below mirror `src/resto/application/ports/repositories.py`, which is the in-process
form of the same contract. `A | null` means the field may be absent.

### 5.1 `networks` (required)

| Tool | Arguments | Returns |
|---|---|---|
| `store_network` | `network: Network` | `{ "network_id": str }` |
| `get_network` | `network_id: str` | `Network \| null` |
| `list_networks` | — | `Network[]` |
| `find_network` | `source: str \| null`, `derived_from: str \| null`, `label: str \| null` | `Network[]` |

`find_network` is how the Coordinator answers "do we already have this network?" without a
content hash, since the hash is only known after building it. All three arguments are filters
combined with AND; with none given, it is equivalent to `list_networks`. `source` matches
`Network.recipe.source.value` exactly; `derived_from` matches `Network.derived_from` exactly;
`label` matches `Network.label` exactly. Results are ordered deterministically (see §6).

**`label`** (resolves open point 1, §10) is a human-facing, opaque handle — e.g. `"berlin"` for a
hand-picked base network, or `"berlin/remove_edge_118"` for one of several derived from it. It is
metadata, not identity: it plays no part in `network_id` (still the content hash of the `.net.xml`,
per §3), and a `/` in it is a naming convention the Coordinator and its user may use to express
grouping (e.g. "all networks derived from Berlin") — the server treats it as an opaque string, the
way an object store treats a key as a path it never parses. There is no separate `NetworkGroup`
aggregate: the concrete need this serves (finding every network someone derived from a given base
one for a what-if study) is served by `label` plus prefix matching without one. A store need only
support exact match on `label` for `find_network`; prefix matching (`find_network(label_prefix=…)`)
is a candidate future addition, not required by this version of the contract. Its conflict-check
exemption is stated in §3.

### 5.2 `demands` (required)

| Tool | Arguments | Returns |
|---|---|---|
| `store_demand` | `demand: Demand` | `{ "demand_id": str }` |
| `get_demand` | `demand_id: str` | `Demand \| null` |
| `list_demands` | `network_id: str` | `Demand[]` |

A `Demand` is trips plus routes computed for **one** network, so `list_demands` requires a
`network_id` — there is no global demand list. A demand derived by `reroute_demand` for a
different network is a separate `Demand` with `derived_from` set, and is listed under its own
`network_id`, not the original one.

### 5.3 `scenarios` (required)

| Tool | Arguments | Returns |
|---|---|---|
| `store_scenario` | `scenario: Scenario` | `{ "scenario_id": str }` |
| `get_scenario` | `scenario_id: str` | `Scenario \| null` |
| `find_similar_scenario` | `network_id: str`, `interventions: Intervention[]`, `context_tags: str[]`, `limit: int = 10` | `{ "scenario": Scenario, "score": float }[]` |

`find_similar_scenario` must:

1. **Short-circuit on identity.** If a scenario with the `scenario_id` these arguments hash to
   exists, return it alone with `score = 1.0`. This is the path the "zero redundant simulations"
   guarantee runs through, so it must not be approximated.
2. Otherwise rank candidates **within `network_id` only** by

   ```
   score = 0.7 * jaccard(signatures(query), signatures(candidate))
         + 0.3 * jaccard(context_tags(query), context_tags(candidate))
   ```

   where an intervention's **signature** is the tuple `(type, target, strategy)` — `target`
   rendered as its discriminated-union `kind` plus its id, `strategy` being `static` for a
   `window` and `dynamic` for a `condition`. `params` and the window bounds are deliberately
   excluded: two lane closures of different lengths on the same lane are similar, which is what
   the caller is asking.
3. Return at most `limit` results with `score > 0`, highest first, ties broken per §6.

A scenario with no interventions (a baseline) has an empty signature set; `jaccard(∅, ∅)` is
defined as `1.0` here, so baselines match baselines.

### 5.4 `results` (required)

| Tool | Arguments | Returns |
|---|---|---|
| `store_result` | `result: SimulationResult` | `{ "result_id": str }` |
| `get_result` | `result_id: str` | `SimulationResult \| null` |
| `list_results` | `scenario_id: str` | `SimulationResult[]` |
| `query_edgedata` | `result_id: str`, `edge_ids: str[]`, `window: [float, float] \| null` | `{ "<edge_id>": { …measures } }` |

`query_edgedata` is how the Network Expert reaches evidence, so its semantics are pinned tightly:

- **`edge_ids` empty means every edge** present in the result's edgedata.
- **`window` is `[start, end)`** in simulation seconds, matching `TimeWindow`. `null` means the
  whole simulation.
- **Aggregation.** SUMO writes edgedata in intervals. Every interval **overlapping** the window
  contributes, clipped to the overlap. Counters (`entered`, `left`, `departed`, `arrived`) are
  summed over the clipped intervals, prorated by the overlapping fraction of each interval and
  rounded half-up at the end. Rates and means (`density`, `occupancy`, `speed`, `waiting_time`,
  `time_loss`, `travel_time`) are averaged **weighted by `sampled_seconds`** within the overlap,
  which is the only weighting that makes a partially covered interval comparable to a full one.
- **Required measures** per edge: `sampled_seconds`, `density`, `occupancy`, `speed`,
  `waiting_time`, `time_loss`, `travel_time`, `entered`, `left`. Names are the snake_case form of
  SUMO's meandata attributes. Implementations may return more; consumers must ignore extras.
- **An edge with no samples in the window** is returned with `sampled_seconds = 0.0` and the
  remaining measures at `0.0`, **not** omitted — the Expert must be able to tell "no traffic"
  from "edge not in this result".
- **An edge id absent from the network** is omitted from the mapping entirely. Asking for a
  mixture of known and unknown edges is not an error; the caller compares keys.
- Calling it with an unknown `result_id` is `NOT_FOUND`, not an empty mapping.

Ephemeral runs — `probe_run` and `calibration_run` — are **never** stored (DoD §4.6). A
conformant server never sees them; it does not need to filter them out.

### 5.5 `notes` (required)

| Tool | Arguments | Returns |
|---|---|---|
| `store_note` | `note: ExpertNote` | `{ "note_id": str }` |
| `search_notes` | `query: str`, `network_id: str`, `filters: object = {}`, `limit: int = 10` | `{ "note": ExpertNote, "score": float }[]` |
| `update_note_status` | `note_id: str`, `status: "unverified" \| "confirmed" \| "refuted"` | `{ "note_id": str, "status": str }` |

This group is the Expert's memory and the mechanism behind the learning-effect experiment
(DoD §4.7), so retrieval quality is a thesis result, not an implementation detail.

`search_notes`:

- is **scoped to one network**: `network_id` is required and notes from other networks must never
  be returned, however similar;
- ranks by semantic similarity between `query` and `ExpertNote.text`, highest first, ties broken
  by `note_id` ascending (§6). Turning text into a vector is server-owned (an implementation
  detail, since the tool takes `query: str` — this is what open point 2 calls out as a source of
  cross-implementation variance), but the ranking step itself is not: given the query vector and
  a candidate's stored vector, every conformant server must produce the same score, because it is
  the same fixed algorithm — cosine similarity, `domain.services.note_ranking.rank_notes` in the
  framework's own code (architecture §9, amendment A2). A third-party backend may reimplement it
  in its own stack; it must reproduce the same output on the same vectors, which the conformance
  suite (§8) checks directly against fixed vector fixtures, independent of any embedder;
- accepts these `filters`, each optional, combined with AND:

  | Filter | Type | Meaning |
  |---|---|---|
  | `status` | `str[]` | keep only these `NoteStatus` values |
  | `basis` | `str[]` | keep only these `Basis` values |
  | `provenance` | `str[]` | keep only these `Provenance` values |
  | `scenario_id` | `str` | notes attached to this scenario |
  | `context_tags` | `str[]` | notes carrying **all** of these tags |

- **applies filters before ranking and never relaxes them**: if filtering leaves nothing, the
  result is empty. Returning a near-miss because the filtered set was empty is non-conformant —
  the filters are how the Expert keeps an old extrapolated opinion from being read as an observed
  fact (architecture §2.4).
- An unknown key in `filters` is `INVALID_ARGUMENT`, not silently ignored: a typo in a filter
  would otherwise widen a search invisibly.

`update_note_status` is the only mutation in the contract. `NoteStatus` changes because a later
simulation confirmed or refuted the note, and only code decides that. Unknown `note_id` is
`NOT_FOUND`.

### 5.6 `historical_demand` (optional)

| Tool | Arguments | Returns |
|---|---|---|
| `get_historical_demand` | `network_id: str`, `day_type: str`, `hour: int` | `{ "counts": { "<edge_id>": float }, "source": str, … }` |

`hour` is 0–23 local time; `day_type` is a free string the backend defines (`weekday`,
`saturday`, …) since it depends on the data available. Returns measured counts per edge, used by
the Demand Generator as calibration targets. An absent combination returns empty `counts` rather
than an error — no data for a Tuesday at 3 am is a fact, not a failure.

Being optional, its absence is a supported configuration (GP-10), not a degraded one.

---

## 6. Determinism of listings

Every tool returning a list must be **deterministic across identical calls**: the same query
against an unchanged store returns the same items in the same order. Where no ranking applies
(`list_*`, `find_network`), order by the entity's id ascending. Where a score applies, order by
score descending and break ties by id ascending.

This is not cosmetic. Repeated-run evaluation (DoD §4.7, three runs per benchmark) attributes
variation to the agent; a store that shuffles its listings would inject variance the metrics
would read as agent instability.

---

## 7. Error codes

Errors are returned as MCP tool errors carrying a stable `code` and a human-readable `message`.

| Code | When | Retryable |
|---|---|---|
| `INVALID_ARGUMENT` | Payload fails its JSON schema; an argument is out of range; an unknown key in `filters` | no |
| `NOT_FOUND` | `update_note_status` or `query_edgedata` addresses an id that does not exist | no |
| `CONFLICT` | `store_*` with an existing id and different content (§3) | no |
| `UNSUPPORTED_CAPABILITY` | The tool is exposed but its capability is disabled in this deployment | no |
| `BACKEND_UNAVAILABLE` | Transient: connection lost, lock timeout, disk full | yes |
| `INTERNAL` | Anything else; the message must not leak connection strings or credentials | yes |

**`get_*` never raises `NOT_FOUND`.** A missing entity is a `null` return, because "does this
exist?" is the question the Coordinator asks constantly and an exception is the wrong shape for a
routine negative. `NOT_FOUND` is reserved for operations that cannot proceed without the row.

`INVALID_ARGUMENT` must name the offending field. It is fed back into an agent's single retry
(architecture §1, principle 2), so a message that does not identify what to fix wastes the retry.

---

## 8. Conformance

Work-plan E1.5 ships a **conformance suite** runnable against any implementation through the
`mcp_client` adapter. An implementation is conformant when it passes it. The suite checks:

1. **Round-trip fidelity** (§2) for all five aggregates, including every optional field
   populated and every optional field absent.
2. **Idempotency and conflict** (§3): double-store is a no-op; changed content under a known id
   is `CONFLICT`.
3. **Capability derivation** (§1): a server with a group's tools removed is detected as lacking
   that capability, and a partial group counts as absent.
4. **`find_similar_scenario`** (§5.3): exact-hash short-circuit, the scoring formula, the
   baseline-matches-baseline case, `limit`, cross-network isolation — 10 cases (DoD §4.9).
5. **`query_edgedata`** (§5.4): window clipping, weighted aggregation, empty `edge_ids`,
   zero-sample edges present, unknown edges omitted — 5 cases.
6. **`search_notes`** (§5.5): each filter, filters never relaxed, cross-network isolation,
   unknown filter key rejected — 5 cases.
7. **Determinism** (§6): every listing called twice returns identical order.
8. **Error codes** (§7): at least one case per code, and `get_*` returning `null` rather than
   raising.

Latency targets, measured per tool on DEV-NET (E1.6): single call < 1 s on DEV-NET, < 5 s on
REAL-NET *(threshold, revisited after the first measurements)*.

---

## 9. Reference implementation

**SQLite, with vector search done in process** (cosine over embeddings held in a blob column),
plus the filesystem artifact store. This supersedes the Postgres + `pgvector` reference
implementation named in architecture §2.1, §2.4 and §7; the reasoning is recorded in architecture
§9, amendment A1 (2026-09-11).

The contract above is deliberately free of anything that assumes either backend. Postgres +
`pgvector` remains the intended second implementation, and when it arrives its acceptance test is
the conformance suite of §8 — which is the evidence that the pluggable-backend claim was true
rather than merely asserted.

---

## 10. Open points

1. **`find_network(name=…)` — resolved (2026-09-14, architecture §9 amendment A2).** Architecture
   §2.3/§2.4 mentioned looking a network up by *name*, but `Network` had no name field. Resolved
   by adding `Network.label` (§5.1) rather than dropping the mention: networks are referred to in
   a user's request by more than their source string (e.g. a batch of edits derived from one base
   network, as in the Berlin example that motivated this). No separate `NetworkGroup` aggregate —
   `label` plus a naming convention (`"berlin/remove_edge_118"`) covers the concrete need without
   one; see §5.1 for the field's semantics and its conflict-check exemption.
2. **Embedding ownership — narrowed (2026-09-14, architecture §9 amendment A2).** `search_notes`
   still takes text, not a vector, so *which embedding model* a server uses stays server-owned and
   genuinely pluggable — two conformant servers may still embed differently and therefore rank
   differently on identical data, so the learning-effect numbers of E4.9 remain comparable only
   across implementations that share an embedder (stated as a limitation in the thesis; the
   reference implementation pins one specific model so its own numbers stay reproducible run to
   run). What is no longer open: the *ranking* step — turning a query vector and a set of
   candidate vectors into a scored, ordered list — is fixed by the contract (§5.5) as one
   algorithm, `domain.services.note_ranking.rank_notes`, so that half of "why did these two
   backends disagree" can no longer be the ranking rule itself, only the embedder underneath it.
   That function is deliberately pure (plain vectors in, no model, no I/O), which is what let it
   move from "server-owned, therefore unpinnable" to "pinned in the contract" without forcing
   every backend onto one embedding model.
3. **`historical_demand` return shape** is only sketched here because no data source has been
   chosen yet (E6.5). It must be pinned before that task starts.
