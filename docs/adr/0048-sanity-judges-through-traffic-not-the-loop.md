# ADR-0048: The sanity check judges through traffic, not the largest loop

- Status: Accepted (2026-10-21, E6.1 tuning of the Diagonal). Replaces, for `SanityReport.passes`, the
  `largest_scc_ratio >= 0.95` rule of DoD §4.3 and of the `SanityReport` row in §2.3 without editing them; the
  DoD is frozen, and where it says "strongly connected component" as the test, read "through traffic"
- Date: 2026-10-21
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3 (`SanityReport`),
  §4.3; [ADR-0046](0046-network-author-locates-selects-and-verifies.md); tuning log entry of 2026-10-21
  (`docs/tuning/network-author-tuning-log.md`)

## Context

`sanity_check` passed a network when the largest strongly connected component (SCC) held at least 95 % of its edges.
That asks the network to be one loop a vehicle can leave and come back to. A city is close to that. A section of an
arterial road is not: each carriageway is one-way, the two directions meet only where a ramp or a cross street joins
them, and the selection cuts both at its ends.

The run of the Diagonal of 2026-10-21 (prompt `v7`) ended with `largest_scc_ratio` 0.573 and the agent listed it as
unresolved. Counting on the built `network.net.xml` (560 edges):

- 321 edges are in the largest SCC. Of the other 239, 108 can be entered from the core and not left back to it, 87
  can reach the core and cannot be entered from it, and 44 do neither. 19 edges have nothing leading into them and 19
  lead nowhere: the entries and exits of the cut.
- Every one of the 560 edges lies on a path from an entry to an exit.
- Joining the only gap that a pair of OSM ways leaves in a lateral lane (nodes 1856466592 and 269386319, 98 m apart,
  across a pedestrian area) raises the ratio to 0.613. The ratio was never going to reach 0.95 by repairs.

A Traffic Assignment Zone sends vehicles from an origin to a destination, and those lie at the border of the
network or inside the core. What the sanity check has to protect is that a vehicle placed on any edge can be
reached and can finish its trip. A closed loop is not required.

## Decision

1. **`SanityReport` gains `through_traffic_ratio`**: the share of edges that are reachable from the border and can
   reach an exit. The border is every edge nothing leads into, plus the core (the largest SCC); the exits are every
   edge that leads nowhere, plus the core. The core counts on both sides so that a closed network, which has no
   entry, still has one.
2. **`passes` compares `through_traffic_ratio` with the threshold**, not `largest_scc_ratio`. The other two
   conditions stay: no zero-length edge, and every edge reachable from the border. `largest_scc_ratio` is still
   computed and returned by `sanity_check` as information.
3. **The parameter keeps its name.** `min_scc_ratio` stays in `NetworkTask`, `ObtainNetworkTask`, the plan steps and
   `eval/plan_bank/plans.json` (73 plans carry it, default 0.95). It now bounds `through_traffic_ratio`. Renaming it
   waits for a change that has to regenerate the plan bank anyway.
4. **The prompt lists the new field** (`NETWORK_AUTHOR_VERSION` `v8`).

On the Diagonal network of the run, the report is `through_traffic_ratio` 1.0, `largest_scc_ratio` 0.573, one
zero-length edge. It still fails, for the zero-length edge, which is a defect.

## Consequences

- A one-way road with an entry and an exit passes (`one_way_chain` in the tests: SCC 0.25, through traffic 1.0). A
  loop that is entered and never left does not (`TrapNetwork`: 0.5).
- **The metric cannot tell an interior dead end from the border.** The 98 m gap is a dead end and counts as an
  exit, so it does not lower the ratio. The report does not know where the selection ended, and the bbox is of no
  use: the Diagonal ends kilometres from it. Interior dead ends are still listed as `suspects` by `inspect_network`
  ("no outgoing connection"), where the agent and the maintainer judge them by their coordinates. Telling the
  border from the interior needs the selection's cut points in the recipe; it is not decided here.
- A separate fragment with its own entry and exit passes. `connected_components` in `inspect_network` and
  `--keep-edges.components 1` are what keep fragments out.
- `schemas/Network.json` and `schemas/NetworkDraft.json` are regenerated, and the stored tool snapshot with them. A
  `SanityReport` saved without the new field does not load, so a local run database written before this change
  (`resto.sqlite` under `~/resto-runs`) has to be started again.

## Alternatives considered

- **Lower `min_scc_ratio` for this request.** The threshold is a parameter, but 0.57 is a property of the road, not
  of this run; any threshold that passes it passes a network cut into loops.
- **Keep the SCC and add a tool that closes the carriageways.** It invents roads the user did not ask for, and a
  junction that OSM leaves open would be closed by guess.
- **Count the exits by distance to the bbox.** The bbox is the import area, not the selection.
- **Rename `min_scc_ratio`.** Right in the end, and out of scope while the plan bank holds the old name.
