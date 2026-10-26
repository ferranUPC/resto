# ADR-0049: An import is widened by a margin, and the polygon is written with fixed precision

- Status: Accepted (2026-10-22, E6.1 ticket 14). Amends [ADR-0045](0045-network-author-sources-and-import-scope.md)
  §8 ("`netconvert` cuts to the same polygon") without editing it
- Date: 2026-10-22
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3;
  [ADR-0045](0045-network-author-sources-and-import-scope.md) §3, §6, §8; tuning log entry of 2026-10-21
  (`docs/tuning/network-author-tuning-log.md`)

## Context

An administrative boundary often runs along the axis of a street, so the street lies on the edge of the polygon.
Two roundings then cut it:

- `OverpassOsmSource._query` wrote the polygon with `:g` (six significant digits, four decimals of latitude, up to
  5.6 m of error). In the run of Hostafrancs of 2026-10-21 the way 1395746250 of Carrer de Tarragona (53 m) fell
  0.3 to 3.2 m outside the rounded polygon, and `poly:` did not return it.
- `_boundary` in `osm_import.py` wrote the cut of `netconvert` the same way, which changes which junctions
  `--junctions.join` merges.

Whatever the download leaves out no tool recovers; whatever comes in too much, `select_streets` and the cleanups
prune. The agent should import generously and prune afterwards.

## Decision

1. **`fetch_osm` takes `margin_pct`** (default 5, from 0 to `MAX_MARGIN_PCT` = 50). The margin in metres is
   `margin_pct / 100 × √area`, the side of a square of the same surface, so it does not depend on the orientation or
   the shape. Hostafrancs: 0.412 km², side 642 m, 5 % is 32 m.
2. **`expand_area`** (`domain/services/geo.py`, pure) grows the area. A `BBox` stays a `BBox` with every side moved
   by the margin. A `Polygon` (also the one a `PlaceName` resolves to) becomes its convex hull moved outwards by the
   margin, which needs no new dependency and cannot cross itself. The concavities of the district are imported too.
3. **The grown area is what is stored.** It is the area that is downloaded, cut and put in the recipe: `source` is the
   grown polygon (keeping the `osm_id`), the snapshot is keyed by it, and a replay builds the same network. The size
   limit (`max_area_km2`) is checked against the grown area, because that is what is downloaded.
4. **Fixed precision.** The Overpass `poly:` filter and `--keep-edges.in-geo-boundary` write every coordinate with up
   to 7 decimals (about 1 cm) through `format_coordinate`, not with `:g`.
5. **Amendment to ADR-0045 §8:** `netconvert` cuts to the grown area, not to the area the user named.
6. Prompt `v9` and the description of `fetch_osm` say that the area is widened 5 % by default, that a larger
   `margin_pct` is for when the user asks for the surroundings, and that what is left over is pruned afterwards.

## Consequences

- A network of a named district now holds some streets outside it. The user's boundary is no longer the cut; the
  agent prunes with `select_streets` when the user wants the exact district.
- A recipe stored before this ADR keeps its exact area, but its `netconvert` cut is now written with 7 decimals, so a
  replay can differ at the junctions `--junctions.join` merges near the edge.
- An area above about 83 % of the size limit is refused now at the default margin, as its grown area (about 21 % more
  for a square) is over it.
