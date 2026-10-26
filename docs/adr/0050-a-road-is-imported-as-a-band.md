# ADR-0050: A stretch of road is imported as a band along its line, and the size limit is measured on the band

- Status: Accepted (2026-10-26, E6.1 ticket 15). Amends [ADR-0045](0045-network-author-sources-and-import-scope.md)
  §6 (the recommendation of `AreaTooLarge`) and [ADR-0047](0047-select-streets-keeps-a-zone-and-prunes.md) (a
  selection needs something to keep) without editing them
- Date: 2026-10-26
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3;
  [ADR-0045](0045-network-author-sources-and-import-scope.md) §2, §6, §8;
  [ADR-0049](0049-import-with-margin.md) §2; tuning log entry of 2026-10-26
  (`docs/tuning/network-author-tuning-log.md`)

## Context

In the run of 2026-10-26 the user asked for the A-2 between km 8 and km 56 of Madrid, with its service roads and
without the town streets. `fetch_osm` takes a box, a polygon or a place, and the size limit (25 km²) is measured on
that area. The box of the stretch is 1,261 km² or more. A band of 400 m along the 48 km of road would be about
19 km², but the agent cannot draw it without inventing the line of the road, and `expand_area` (ADR-0049) turns any
polygon into its convex hull, which for a road that bends is close to the box again.

The limit protects Overpass and `netconvert` from a large download. A long, thin band downloads about as much as a
district of the same area, so the limit does not need to change: what needs to change is the area a road is asked as.

Two texts also misled the agent. The recommendation of `AreaTooLarge` said "or an import profile with fewer road
classes", but a profile does not change the area. And with no way to keep every road but some classes, a band
could not lose its town streets without losing its service roads too.

## Decision

1. **`fetch_road(ref, from_point, to_point, half_width_m=200)`** imports a stretch of road in two downloads. The
   first, `OsmSource.fetch_road`, is light: the highways inside the box of the two points (plus `ROAD_BOX_MARGIN_M`)
   whose `ref` is that road's, matched without case, hyphens or spaces ("A2" is "A-2", not "A-21"). The second is
   the usual `fetch`, of the band.
2. **The line** (`OsmMap.road_line`) is the shortest chain of those ways between the nodes nearest the two points (at most
   `MAX_ROAD_SNAP_M`, 5 km: the user names towns, not points of the motorway), in either direction, crossing gaps of up
   to `MAX_ROAD_GAP_M` (300 m) between them: OSM leaves the ref off ramps and roundabouts.
3. **The band** (`road_band` in `domain/services/geo.py`, pure) is the line, simplified to fit `MAX_POLYGON_VERTICES`,
   moved `half_width_m` to each side, with its ends lengthened by as much. It is a `Polygon` like any other: it is
   downloaded with `poly:`, cut by `netconvert`, stored in the recipe, and a replay gives the same network. It takes no
   margin: `half_width_m` is the margin, and the convex hull would undo the band.
4. **The size limit is the same and is measured on the band.** Before any download, a band the straight line already
   puts over the limit (`2 × half_width_m ×` the distance between the points) is refused with `AreaTooLarge`.
5. **`select_streets` with only `drop`** keeps every road of the snapshot (no footways) and removes what the rules
   match. A call with nothing to keep or drop is still an error.
6. **The recommendation of `AreaTooLarge` by area** is to pick a smaller area or, for a stretch of road, `fetch_road`,
   and it says that the profile does not change the area. The one by edges does not change.
7. **Prompt `v10`** sends a stretch of road to `fetch_road`, says that kilometre points are not in the data (the
   agent locates the places at them and says which in `rationale`), and adds two rules to `NeedsUser`: `message` is
   in the language of `network_ref`, and `advice` offers only what the tools can do.

## Consequences

- At the default half width a stretch of up to about 60 km fits the limit; a longer one needs a narrower band or is
  asked for in parts.
- A town the road passes through comes into the band too; the agent prunes it with `drop` by class.
- The corners of the band meet where the two moved sides cross, so a hairpin tighter than the half width can make the
  ring cross itself on the inner side. A road a car drives at speed has none; a mountain road may.
- Kilometre points stay out: OSM has `highway=milestone` nodes near the A-2, mixed with those of the M-50, A-1 and
  M-108 and many with no `ref`.

## Alternatives considered

- **Raise the area limit, or measure it in edges or km of road.** Rejected: the band keeps the area what the download
  costs, and the edge limit after `netconvert` (ADR-0045 §6) is already there.
- **Overpass `around` over the road's ways.** Rejected: the cut of `netconvert` and the recipe need a polygon anyway,
  and the band gives one that is downloaded and cut the same way.
- **Several boxes joined into one network.** Rejected: no tool joins snapshots or networks, and a band makes it
  unnecessary for this case.
- **Let the agent draw the band.** Rejected: it would draw the road from memory, which the prompt forbids, and the
  margin would turn it into its hull.
