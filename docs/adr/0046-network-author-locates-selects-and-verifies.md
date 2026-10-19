# ADR-0046: The Network Author locates, selects and verifies; a street selection is a derived snapshot

- Status: Accepted (2026-10-19, E6.1 ticket 09). Amends [ADR-0045](0045-network-author-sources-and-import-scope.md)
  §7 and §8 without editing it: the recipe's `osm_snapshot` may be a selection derived from the download, keyed by
  the download and the selection rather than by the polygon, and the cut to the polygon is no longer the only thing
  between the download and `netconvert`. Replaces the filter at download tried on 2026-10-19, which was never
  committed
- Date: 2026-10-19
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3
  (`NetworkRecipe`), §4.3; [ADR-0001](0001-tool-agent-port-and-draft-promotion.md),
  [ADR-0033](0033-tools-declared-once.md), ADR-0045 §2, §7, §9; ticket
  `.scratch/e6-1-network-author-minimal/issues/09-locate-select-verify-tools.md`

## Context

A request for one street between two places ("the Diagonal from the Hospital Broggi to Francesc Macià, main
carriageway and lateral lanes") could not be met with the catalogue of ADR-0045. Two runs with the default model
on 2026-10-19 showed why:

- Without a filter the network had the 6,621 edges of the whole box. The agent reported in `unresolved[]` that it
  had no tool to cut by street.
- With a filter by name in the Overpass query, the network broke at every large crossing (strongly connected
  ratio 0.676). The ways that join the carriageways (`primary_link`, the squares Pius XII, Reina Maria Cristina and
  Francesc Macià) carry another `name`. West of lon 2.103 the same road is called "Carretera de Collblanc" and
  "Carretera Reial" (`ref` N-340), so the network stopped short of Sant Just. The agent also drew the box from
  memory: it put the east edge at 2.152 when Francesc Macià is near 2.143.

## Decision

1. **Three steps, four tools, one agent.** The Network Author locates (`locate_place`), selects (`list_streets`,
   `select_streets`) and verifies (`verify_coverage`). Each step is a group of tools with its own inputs and
   outputs, so splitting them into separate agents stays open; it waits for the measurements of E6.2.
2. **Locating a point is a second question to the `Geocoder`.** `locate(query)` returns the best match of any
   kind (a hospital, a square) as a `LocatedPlace` with its point and what it is, or `None`. "Not found" is an
   answer the agent can act on (another wording), not a failed step. A failing service is still a failed step by
   name (ADR-0045 §7). The recipe never stores a located point: the box drawn from it is the source, as before.
3. **The download is the whole area again.** `fetch_osm` has no street filter. The name matching, the escaping and
   the "nothing matches" error moved to `select_streets`, which needs no regex for Overpass.
4. **A selection is a derived snapshot.** `select_streets` reads the downloaded `.osm` and writes a new one with
   the highways whose `name` contains one of the given names (case-insensitive), or whose `ref` is one of the given
   refs, plus connectors, and the nodes they use. The derived file is an `ArtifactRef` of kind `osm` with its own
   `content_hash`; the recipe stores it as `osm_snapshot` and replays from it like any snapshot. The selection is
   not written into `netconvert_options`: the recipe keeps saying "this snapshot, these options", and
   `NetworkRecipe`, `NetworkDraft` and `SanityReport` do not change. The same selection of the same snapshot gives
   the same bytes, so trying it again downloads and writes nothing new.
5. **Connectors are the agent's choice: `none`, `links` or `all`.** A connector is a way not selected that lies on
   a path of at most 300 m between two pieces of the selection (pieces are ways joined by shared nodes). `links`
   considers only `*_link` ways; `all` any road (footways, paths, cycleways and the like never join two
   carriageways for a car, so they are left out). The 300 m bound keeps a square and a large crossing and leaves
   out a detour through the next street. `select_streets` returns how many pieces the selection has, so a gap is
   visible before `netconvert` runs.
6. **The coverage report reads the built network against its snapshot.** It is text, because the default model
   reads no images, and it reports the extent, the connected components with their ends, the stretches of each
   street of the snapshot that are not in the network, and the distance from every located place to the network
   and to its nearest end. To know which OSM ways an edge was built from, every import now passes
   `--output.original-names`, which writes them as an `origId` parameter of each lane. It changes the `.net.xml`
   (and so the `content_hash`) of new imports; stored recipes keep their options and replay as they were.
7. **Rounds are unchanged.** A round is still one `sanity_check` call. Locating, listing, selecting and verifying
   are construction, not repair, so they cost no round; a new selection costs one only when it is followed by a
   `sanity_check`, like any other rebuild.
8. **Limits keep their order.** The area limit is checked before the download and the edge limit after
   `netconvert`, on the selected network as on any other.
9. **The OSM file is read in the application layer** with the stdlib XML parser, as the import tools already count
   the edges of a `.net.xml`. No port stands in front of it: there is one format and no second backend.

## Consequences

- The prompt of the Network Author becomes `v3` and says when to locate and select, that coordinates come from a
  tool, and that the coverage report is read before submitting.
- `ImportRun` keeps the places located in the run and, for each snapshot, the last network built from it.
- A street whose lateral lanes carry neither its name nor its ref is joined only through connectors; the coverage
  report shows what is still missing. A cut along a polyline (`around:` in Overpass) is the next step if selection
  by name and ref proves not to be enough.
- Selection acts on the snapshot. Removing edges by name from a built network stays out of scope.

## Alternatives considered

- **Filter by name in the Overpass query** (tried on 2026-10-19). Rejected: it loses the connectors that carry
  another name and the stretches where the road changes name, and it needs one download per filter.
- **Write the selection into `netconvert_options`** (`--keep-edges.input-file` with edge ids). Rejected: edge ids
  only exist after a first build, the list would be long and opaque in the recipe, and the cut by `ref` and the
  connectors would have to be redone in `netconvert` terms.
- **`--output.street-names` instead of `--output.original-names`.** Rejected: with it, `--geometry.remove` stops
  joining edges whose names differ, which changes the topology of every import, and a name alone does not tell
  which way an edge came from.
- **Three agents (locate, select, verify).** Deferred to E6.2: one agent with more tools is measured first.
