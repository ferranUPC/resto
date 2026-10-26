# ADR-0051: A snapshot that reaches `netconvert` has no open roundabout, so a replay gives the same network

- Status: Accepted (2026-10-26, E6.1 ticket 16). Amends [ADR-0045](0045-network-author-sources-and-import-scope.md) §8
  (what the recipe stores as `osm_snapshot`) and [ADR-0050](0050-a-road-is-imported-as-a-band.md) §1 without editing
  them
- Date: 2026-10-26
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3;
  [ADR-0045](0045-network-author-sources-and-import-scope.md) §3, §8; [ADR-0046](0046-network-author-locates-selects-and-verifies.md) §4;
  tuning log entry of 2026-10-26 (`docs/tuning/network-author-tuning-log.md`);
  [eclipse-sumo/sumo#18375](https://github.com/eclipse-sumo/sumo/issues/18375)

## Context

In the run of 2026-10-26 (A-2, km 15 to 25) the agent delivered a valid `NetworkDraft` and `NetworkPromoter` rejected
it: replaying the recipe gave another `content_hash`. Seven builds of the same snapshot with the same options gave four
hashes.

`netconvert` 1.27.1 registers roundabouts in `NBEdgeCont::extractRoundabouts` walking a `std::set<NBEdge*>` ordered by
pointer, and it registers one whenever a walk reaches an edge an earlier walk visited. A closed ring gives the same set
every time. An open chain of `junction=roundabout` ways is cut into false roundabouts where the heap order says, which
changes the priorities and the `M`/`m` state of the connections of the junctions around it. No option avoids it:
`--keep-edges.in-geo-boundary` cuts while loading, before the extraction.

A ring is open because the download or the cut leaves part of it out: `fetch_road` downloads with `poly:` and a ring on
the edge of the band comes in part, a `fetch_osm` box does the same, and the cut to the polygon removes the edges that
lie outside it. `select_streets` already keeps whole the rings a selection touches (ticket 13); nothing did for the
other tools.

## Decision

1. **`fetch_road` completes the roundabouts the band holds in part.** After the download it asks the source for the
   roundabout ways that pass through the nodes where a ring stops short (`OsmSource.fetch_roundabouts`, one Overpass
   query by node ids), at most `MAX_RING_ROUNDS` (3) times, and stores the result as a snapshot of its own
   (`completed-<key>.osm`).
2. **A snapshot is sealed before it is built.** `OsmMap.sealed(area)` takes `junction` off every roundabout way of a ring
   that is open, that shares a node with another ring, or that has a node outside `area` (the polygon of
   `--keep-edges.in-geo-boundary`, which leaves it open after the cut), and adds `oneway=yes` where the way has no
   `oneway` tag (a `oneway=-1` stays). Closed rings inside the area are not touched.
3. **The sealed snapshot is the snapshot of the recipe.** `network_import._build` writes it as `sealed-<key>.osm`, with
   its own `content_hash`, builds from it, and returns it as `osm_snapshot`. The promoter replays from the same bytes
   and applies no transformation. The run knows the sealed hash, so a tool accepts it like any other. When no ring is
   loose the snapshot is built as it came and nothing is written. The download itself is never modified.
4. **The recipe stays honest about the change.** `osm_snapshot` is no longer always the raw answer of Overpass, but a
   file whose differences from it are one tag removed and one added on the ways of open rings.

## Consequences

- A replay of a recipe gives the same `.net.xml` as the build: 20 of 20 identical builds of the A-2 selection of the
  run (6 rings left, 16 ways sealed), and of a fixture with 45 open rings that gave 4 hashes in 12 raw builds.
- A ring the polygon cuts is not a roundabout in the network (a ring that straddles the border of the band loses
  `ROUNDABOUT` priority); the cut would have left it open anyway, and the alternative is a network that changes between
  builds.
- The rings completed in 1 are mostly stripped in 2 when they poke out of the polygon; completion pays off when the
  missing way lies inside it. Both stay: completion keeps the whole ring when the polygon holds it, sealing is the net.
- `fetch_osm` does not complete rings; the seal covers it. It can be added with the same helper.
- A sealed way is driven one way (`oneway=yes`) as the roundabout would have been; a `junction=circular` way, which
  OSM does not imply one-way, becomes one-way too.
- The ring tag is lost for the real roundabouts of the area that a profile cut leaves open, which `--roundabouts.guess`
  does not recover.

## Alternatives considered

- **Fix or avoid `extractRoundabouts`.** Out of reach: upstream issue #18375 is open, and no option skips the
  extraction.
- **Strip the tag of every roundabout.** Deterministic in the run (`--roundabouts.guess` rebuilds the closed ones), but
  an elongated ring may not be recognised, and real roundabouts would depend on a heuristic.
- **Transform in the promoter before replaying.** Rejected: the recipe would no longer name the bytes it was built
  from, and the promoter would repeat the transformation on every replay.
- **Reject the draft and ask the agent to narrow the area.** Rejected: the agent cannot see the ring and the user did not
  ask for it.
