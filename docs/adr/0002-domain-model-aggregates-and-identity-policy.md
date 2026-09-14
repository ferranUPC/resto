# ADR-0002: Domain model — six aggregates, `Study` as the run-time root, identity by content/request hash vs UUID

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3

## Context

The framework must guarantee "zero redundant simulations" by construction (Coordinator Done criterion,
§4.2), let identical requests dedupe, and distinguish content that an agent *authors* (no canonical input to
compare against) from content that is *requested* (a canonical input exists and two identical requests
should resolve to the same thing). It also needs somewhere to hold the run-time state of answering one
user question — which specialists were called, what they produced, whether a simulation loop closed — that
isn't itself "knowledge about a network" and shouldn't live in the same store as one.

## Decision

Six aggregates: `Study` (root of one user request; UUID; held by a framework-only `StudyRepository`, not
part of the DatabaseMCP contract), `Network` (id = `content_hash` of the `.net.xml`), `Demand` (id =
`content_hash` of trips), `Scenario` (id = `hash(network_id, demand_id, interventions, context_tags)`),
`SimulationResult` (id = `hash(scenario_id, seed, mode, sumo_version)`), `ExpertNote` (UUID).

Identity policy: `Network`/`Demand` are agent outputs with no canonical input to hash against, so their id
is a content hash and lookup is by `source`/`derived_from` (and, per ADR-0013, `label`). `Scenario`/
`SimulationResult` have a canonical input — the request itself — so their id is the hash of *that request*,
not of the files it produces: two builds of the same scenario may differ in file formatting but are the
same scenario and must be reused. `Study`/`ExpertNote` are events and get UUIDs.

`Study` is the root, not `Experiment`, because the user asks a `Question` — sometimes answerable from
existing results with zero experiments, sometimes needing one or several (counterfactual, compare, the
Expert loop). `Experiment` is the unit inside a `Study` (one scenario and its runs); `Study` holds the
question, plan, steps, Expert rounds, and report, and stays outside the DatabaseMCP contract because it is
this framework's own run-time state, not knowledge a third-party backend should need to model.

## Consequences

- `result_id`'s request-hash identity makes "reuse an existing result" a lookup, not a policy the
  Coordinator has to get right by itself — the guard in §4.2 ("never re-run an existing `result_id`") is
  enforceable by construction.
- Two derivations of `Network`/`Demand` that happen to produce byte-identical artifacts collapse to one
  stored row, which is the correct behavior — they are the same artifact regardless of how they were
  produced.
- Content-hash identity means a `Network`/`Demand` cannot be renamed or relabeled without looking like a new
  artifact to anything that identifies by hash — resolved separately by giving `Network` an opaque,
  non-identity `label` field (ADR-0013) rather than folding a name into the hash.
- `Study` living outside DatabaseMCP means a third-party DatabaseMCP backend has no visibility into
  run-history/orchestration state — accepted, that's not a claim the contract makes; DatabaseMCP is about
  facts on networks, demands, scenarios, results and notes.

## Alternatives considered

- **A single generic `Experiment` aggregate covering both the request and the run-time state.** Rejected:
  conflates "what was asked" with "what was tried", and gives neither a stable identity useful for
  reuse-checking.
- **UUIDs for every aggregate.** Rejected: breaks "zero redundant simulations" and reproducibility outright
  — re-submitting the same request would mint a new id every time instead of resolving to the existing one.
