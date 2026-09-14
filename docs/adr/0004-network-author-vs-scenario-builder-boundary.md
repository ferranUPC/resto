# ADR-0004: Network Author vs Scenario Builder boundary — derivation vs intervention

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.4, §2.5

## Context

Two modules can plausibly own "change what SUMO simulates": the Network Author, which owns the `.net.xml`
(ADR-0003), and the Scenario Builder, which owns runtime behavior on a fixed network. Without a firm rule,
a request like "close this edge" is ambiguous between "permanently, as a topology change" and "from 8 to 9
am, as a runtime intervention" — and routing it to the wrong module would make `Scenario`'s hash-based
identity (ADR-0002) mean different things depending on which module happened to handle a given request.

## Decision

The rule is mechanical, not judgment-based: **if SUMO must load a different `.net.xml`, it is a
`TopologyModification` handled by the Network Author** (derives a new `Network`, `derived_from` set). **If
the network is unchanged and only runtime behavior differs, it is an `Intervention` handled by the Scenario
Builder** — a static additional file for a fixed `window`, or a script against `traci_api` (ADR-0005) for a
runtime `condition` or a `custom` type. Concretely: permanent edge removal, adding an edge, and lane-count
or design-speed changes are never interventions, regardless of how they're phrased in the request. The
domain enforces this: a permanent `edge_closure` (no `window`, no `condition`) is rejected outright as a
`TopologyModification` in disguise.

## Consequences

- `Scenario`'s identity stays meaningful — two `Scenario`s differ only in intervention/demand/context, never
  in "secretly a different network", so `find_similar_scenario` and the "zero redundant simulations"
  guarantee (ADR-0002) keep meaning what they claim to mean.
- The intervention → mechanism table (§2.5) has an unambiguous domain: every row is genuinely a Builder
  concern.
- GP-11 ("what if we add an edge between J7 and J9?") routes mechanically through Network Author (derive) →
  Demand Generator (`reroute_demand`, ADR-0006) → Builder ×2 (baseline, treatment) → Runner ×2 → Expert
  (compare), exercising the full pipeline instead of the Builder special-casing a topology change.
- A time-bounded phrasing of what is actually a permanent change is explicitly rejected by a domain
  invariant rather than silently reinterpreted — a real modeling constraint that surfaces to the
  Coordinator/user as an error, not absorbed invisibly.

## Alternatives considered

- **Let the Builder also derive networks for "closure-shaped" topology changes.** Rejected: duplicates
  network-identity logic in a second place and breaks the invariant that `Network` = the content hash of
  what SUMO actually loads for a `Scenario` — a Builder-side derivation would let a `Scenario` implicitly
  reference a network nobody assigned an id to.
