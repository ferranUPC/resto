# ADR-0047: A street selection is what is kept, by name, ref or zone, minus what is dropped

- Status: Accepted (2026-10-19, E6.1 ticket 11). Extends [ADR-0046](0046-network-author-locates-selects-and-verifies.md)
  §4 and §5 without editing them: the selection gains zones and drop rules; the derived snapshot, the recipe and the
  connectors stay as they were
- Date: 2026-10-19
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3 (`NetworkRecipe`),
  §4.3; ADR-0046 §4, §5; ticket `.scratch/e6-1-network-author-minimal/issues/11-keep-an-area-and-prune.md`

## Context

The `v4` run of the Diagonal (2026-10-19, `docs/tuning/network-author-tuning-log.md`) asked for "the entrances and exits
of Sant Just Desvern". The network had none. The link is four `motorway_link` ways and two `primary` roundabouts with
no `name` and no `ref`. `select_streets` cannot reach them: a way with neither matches no name and no ref, a connector
must join two pieces of the selection within 300 m, and a ramp leaves the selection toward a street that is not in it.
`trace_corridor` drives through them, but its suggested selection speaks only of names and refs.

## Decision

1. **A zone is a circle.** `{"near": [lat, lon], "radius_m": m}`, the pair `list_streets` takes, with the same limits
   (10 to 5000 m, default 300). What the agent sees in a listing is what the zone keeps.
2. **`areas` keeps every drivable road with a node inside a zone**, cut to the stretch between its first and its last
   node inside (the cut `_cut` already does for connectors). A road with one node inside has no stretch and is left
   out. A road that a name or a ref keeps stays whole. `names`, `refs` and `areas` add up; at least one is needed.
3. **`drop` is a list of rules.** A rule has `names`, `refs` and `classes` (the `highway` value) and, optionally, a zone.
   It removes the roads that match any of them; with a zone, only the roads with a node inside it, not cut. A rule with
   no criterion is an error.
4. **Order.** What is kept (names, refs, zones) first, then `drop`, then the connectors. A road that a rule removes is
   not a connector either, so a pruned class does not come back through `connectors="all"`. `pieces` is counted after
   the drop and shows if it split the network.
5. **The summary says what each part did**: the streets kept, what each zone added (ways and metres, by class), what
   each rule removed (ways and metres; 0 when nothing, not an error), the connectors and the pieces.
6. **The recipe does not change.** The selection is a derived snapshot with its own `content_hash`, and the same
   selection of the same snapshot gives the same bytes whatever the order of zones and rules. The file key includes
   them; a selection without zones or rules keeps the key it had.
7. **Prompt `v5`** says when to keep a zone and prune (a municipality's accesses, a link, a roundabout with everything
   that reaches it, a neighbourhood) and when to go on selecting by name or tracing (a long stretch).

## Consequences

- Each road the zone cuts at its edge is an edge that enters or leaves and does not come back, and counts against
  `largest_scc_ratio`. On the Diagonal run the pruned zone gives 0.81 with the four ramps in (tuning log). **Open
  question:** whether the 0.95 threshold fits a network of selected streets. It touches `SanityReport.passes`, the
  promoter and `is_silent_failure`, so it is a separate decision.
- `verify_coverage` still compares the network with the selected snapshot, not with the downloaded one.
- Edges are still not removed from a built network (ADR-0046).

## Alternatives considered

- **`accesses_near`, a parameter that adds ramps up to the first named street.** Rejected: it only serves motorway
  links, and the roundabout and the streets the user wants around it need a zone anyway.
- **Select the exact ways of a trace.** Rejected: each trace gives one access per direction, and which one depends on
  the carriageway the point falls on.
