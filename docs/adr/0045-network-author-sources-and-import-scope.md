# ADR-0045: A network comes from an area of interest or from a generated pattern; the import keeps what lands in the `.net.xml`

- Status: Accepted (2026-10-14, E6.1 grilling). Extends [ADR-0003](0003-network-edits-via-typed-tools-on-plain-xml.md)
  (the recipe) and [ADR-0037](0037-specialists-resolve-network-and-demand.md) (`obtain_network`) without
  editing them. Replaces the `place` / `bbox` source kinds of `NetworkSource`. Folded into the ADR
  consolidation of 2026-10-16
- Date: 2026-10-14
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3
  (`NetworkRecipe`), §2.4, §4.3; [ADR-0001](0001-tool-agent-port-and-draft-promotion.md),
  [ADR-0004](0004-network-author-vs-scenario-builder-boundary.md),
  [ADR-0035](0035-described-demand-no-default.md) point 6; work-plan E6.1, E6.2

## Context

`NetworkSource` only knows `place`, `bbox` and `file`, and the Network Author was a black box until E6.1.
Building it showed four gaps:

- A synthetic network (grid, spider, random trips of roads) needs no OpenStreetMap, but a recipe has no way to
  say how to regenerate one.
- A place name resolved by a geocoder can change its answer, so a recipe that stores the name cannot be
  replayed.
- `netconvert` can import rail, bicycle lanes and pedestrian paths, and can write public transport stops and
  lines and polygons. Only the first group ends up in the `.net.xml`, which is the only file `network_id`
  hashes.
- Importing a whole city is too large for the public Overpass servers and for `netconvert`.

## Decision

1. **Two kinds of source.** An **area of interest** (`BBox`, `Polygon`, or `PlaceName` resolved to a polygon)
   or a **generated network** (`grid`, `spider`, `rand`, with their parameters and, for `rand`, the seed).
   `NetworkSource` becomes a discriminated union of small dataclasses. A generated network has no
   `osm_snapshot`.
2. **The recipe stores the polygon, never the name.** `PlaceName` is resolved once through Nominatim, keeping
   the `osm_id`, and rejected unless the result is a `boundary` relation. The polygon has at most about 200
   vertices.
3. **Tests use a fake `OsmSource`** that returns a small committed `.osm`. A generated network needs no fake.
4. **Import is a catalogue of profiles** (typemap plus `netconvert` options): road types, rail, bicycle,
   pedestrian, and a vehicle-class filter. The agent picks one with a tool. The user's requirement reaches
   it only inside `network_ref` for now (the Parser does not extract it).
5. **Out of scope: public transport stops and lines, and polygons.** They are not in the `.net.xml`, and
   where they live (`Network`, `Scenario` or `Demand`) crosses the boundary of ADR-0004. A request for them
   ends in `NeedsUser` with an explicit "unsupported requirement" reason, never ignored.
6. **Size limit before downloading.** An area above the limit ends in `NeedsUser` with its own reason
   (`AreaTooLarge`, recommendation: pick a smaller area or a profile with fewer road classes). Initial values,
   to calibrate on GEN-LOCATIONS: 10 km², about 25,000 edges, Overpass `maxsize` 256 MiB, `timeout` 90 s.
7. **One download per area.** The OSM snapshot is stored as an artifact, keyed by the polygon's hash; a
   second request reuses it. A geocoder or Overpass failure is a failed step by name, not `NeedsUser`: the
   user cannot fix it.
8. **The cut comes after loading.** Overpass returns whole ways, so `netconvert` cuts to the same polygon
   (`--keep-edges.in-geo-boundary`, which takes `lon,lat`, the reverse of Overpass) and keeps the largest
   component.
9. **Promotion replays the recipe** and rejects the draft when the `content_hash` differs (ADR-0001's
   semantic validation; the DoD §4.3 replay criterion is measured in E6.2). SUMO 1.27.1 writes a timestamp
   header that `canonical_bytes` already removes, and `netgenerate` and the plain-XML round trip are
   otherwise stable (checked on 2026-10-14).
10. **`add_edge` joins existing junctions only.** A new junction the agent needs ends in `unresolved[]` with
    `needed_tool: "add_node"`.

## Consequences

- Domain: the source union and the recipe change, so the schemas and `docs/class_diagram.md` are regenerated.
- A whole city is out of reach in one call; it is asked for in parts or with a profile that drops road classes.
- The Parser bank has no case with an import requirement. If the resolution bank (E3.12) shows that free text
  in `network_ref` fails, a typed field in `Question` comes next, with its golden path.

## Alternatives considered

- **Keep `NetworkSource(kind, value)` with a string of options for generated networks.** Rejected: a blob
  with no validation, against the convention for variant types.
- **Use SUMO's `osmGet.py`.** Rejected: it ties the importer to what SUMO's tools do at the moment, and it
  asks for `SUMO_HOME`, which ADR-0010 forbids.
- **Store the place name in the recipe.** Rejected: replay would depend on a service that changes.
- **Import stops, lines and polygons now.** Rejected: no home in the model yet.
