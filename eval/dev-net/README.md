# DEV-NET

Development / unit-test network (architecture doc §3, work plan E0.5). Synthetic 5x5 grid built
with `netgenerate`, hand-edited for a designed bottleneck, recompiled with `netconvert`. No OSM
data, no manual node placement — every property below is a deliberate, reproducible choice, so
"correct" answers about this network can be computed analytically instead of guessed.

## Requirements (source of truth for `generate.sh`)

1. **Grid topology**: 5x5 junctions, 200 m block spacing (25 junctions, 80 directed edges,
   800x800 m footprint) — matches architecture doc §3's DEV-NET description verbatim.
2. **Deterministic, LLM-free rebuild**: `generate.sh` runs `netgenerate` → one scripted hand edit
   → `netconvert`, with no manual GUI editing. Anyone can reproduce the exact same
   `dev-net.net.xml` (byte-for-byte, given the same SUMO version) by re-running the script.
3. **One designed 2→1 lane merge bottleneck**, isolated from the signalised corridor so its effect
   can be reasoned about independently.
4. **One signalised corridor**: several consecutive traffic-light junctions in a straight line.
5. **No U-turns at any junction**: an agent or a human reasoning about a route through DEV-NET
   should never have to consider a vehicle reversing direction mid-trip.
6. **Answers known by construction**: junction/edge IDs, lane counts and TLS placement must be
   readable directly off the plain XML — no derived or guessed geometry.
7. **SUMO 1.27.1**, `SUMO_HOME` unset, matching `resto.domain.constants.SUMO_VERSION` (CLAUDE.md).

## Design

### Topology & IDs

`netgenerate --grid --grid.number 5 --grid.length 200` names junctions by column letter
(A-E, x = 0..800 m) and row number (0-4, y = 0..800 m), e.g. `C2`. Edges are named
`<from><to>`, e.g. `B0C0` (B0 → C0). Every block has both directions, so the base grid before hand
edits is fully bidirectional (80 directed edges over 25 junctions). Default: 1 lane, 13.89 m/s
(50 km/h, standard urban limit), `priority`-type junctions.

### Signalised corridor: row 2 (A2-B2-C2-D2-E2)

The middle east-west row is traffic-light controlled (`--tls.set A2,B2,C2,D2,E2`); every other
junction stays a plain priority intersection (verified: 5 TLS junctions, 20 priority junctions).
Five consecutive signals in a straight line let signal-timing interventions (`Intervention`s from
the Scenario Builder, e.g. offset/cycle changes) and "does a green wave exist" questions be posed
and checked directly against `dev-net.tll.xml`.

### Bottleneck: `B0C0` (2 lanes) → `C0D0` (1 lane)

Row 0 (bottom row), east-bound, entirely separate from the row-2 corridor. `dev-net.edg.xml` is
hand-edited to set `numLanes="2"` on `B0C0` only; the rest of `dev-net.con.xml` (netgenerate's
explicit, lane-0-only connections) is left as-is for this edge, so after recompiling, `B0C0` lane 1
has **no forward connection at C0** — a vehicle using it must lane-change into lane 0 before the
junction (it can only reach lane 1 in the first place by an in-edge lateral lane-change, since
lane 1 has no incoming junction connection either, which `netconvert` flags with an expected,
harmless warning — see Sanity). That's the designed 2→1 merge: a mandatory-lane-change bottleneck
at a fixed, known location, not an emergent artefact of routing. Verified: `B0C0` has 2 lanes
(lane 1 outgoing = `[]`), `C0D0` has 1 lane.

### No U-turns

Every junction in the base grid has an explicit turnaround connection in `dev-net.con.xml` (an
edge connected back onto its own reverse) except the 8 edges arriving at one of the 4 grid corners,
which never get one from `netgenerate` in the first place (a corner only has one non-reverse
option). `generate.sh` strips all 72 of these before recompiling, and passes `--no-turnarounds` to
`netconvert` as a defence-in-depth default on top of that (explicit connections, which is what the
72 removed ones were, otherwise override that flag). Verified: 0 `dir="t"` connections in
`dev-net.net.xml`, and the network stays fully strongly connected without them — the grid always
has a same-length or near-same-length alternative to reversing.

### Sanity

- 80 edges, 25 nodes, no zero-length edges.
- Fully strongly connected: every junction reachable from, and able to reach, every other junction
  (checked by BFS over the compiled net — no dead pockets from the lane edit or the turnaround
  removal).
- 5 TLS junctions (`A2,B2,C2,D2,E2`), 20 priority junctions, 0 U-turn connections.
- `netconvert` builds with exactly one warning: `Lane 'B0C0_1' is not connected from any incoming
  edge at junction 'B0'` — expected, and it's the same fact noted in "Bottleneck" above (lane 1 is
  only reachable by an in-edge lateral lane-change), not a defect.

## Files

- `generate.sh` — the reproducible build (netgenerate → hand edits → netconvert). Run it from this
  directory inside the `resto` conda env with `SUMO_HOME` unset; it overwrites every output below.
- `dev-net.nod.xml` / `dev-net.edg.xml` / `dev-net.con.xml` — plain XML, netconvert's
  canonicalised view after all hand edits (`--plain-output-prefix` rewrites them at the final
  recompile step so they stay consistent with `dev-net.net.xml`). `dev-net.edg.xml` carries the
  `B0C0` lane edit; `dev-net.con.xml` has every turnaround connection removed. Keep these under
  version control alongside `dev-net.net.xml` — they *are* the network's `NetworkRecipe` (source +
  edits), even though DEV-NET is a hand-built fixture and isn't registered through the Network
  Author / NetworkMCP pipeline.
- `dev-net.tll.xml` — plain traffic-light logic, built fresh by `netconvert --tls.set` at the final
  recompile step (not reused from `netgenerate`, so it can't go stale relative to the turnaround
  removal, which changes the link count at the row-2 junctions).
- `dev-net.netccfg` — `netconvert`'s own config snapshot for reloading `dev-net.{nod,edg,con,tll}.xml`
  as-is (`netconvert -c dev-net.netccfg`); a free byproduct of `--plain-output-prefix`.
- `dev-net.net.xml` — the compiled network to load in SUMO / `sumolib` / `traci`.

## Suggested manual follow-ups (not yet done — pick based on what E0.6+ actually needs)

- **Coordinate the signalised corridor into a green wave.** Right now the 5 TLS programs are
  netconvert's independent per-junction defaults (same cycle length, no relative offset). Hand-editing
  `dev-net.tll.xml` to offset each program by `distance / free-flow speed` between consecutive
  junctions would make "is there a green wave on the corridor" a real, non-trivial question with a
  construction-known answer — good material for the Network Expert question bank.
- **A second, opposite-direction bottleneck** (e.g. narrow a westbound edge elsewhere) if the
  scenario matrix wants more than one `lane_closure`/congestion site to compare against each other.
- **Turn restrictions** (e.g. no-left-turn at one priority junction) via `dev-net.con.xml`, if the
  Builder bank needs a `custom` intervention that changes routing without touching lanes/network.
- **A dedicated bus/HOV lane** (vClass restriction on one lane) if a Builder bank scenario needs a
  vClass-based intervention rather than a lane-count or speed one.
- **External fringe edges** (`--grid.attach-length`) if a future demand profile wants genuine
  through-traffic entering/leaving the grid rather than purely intra-grid trips — not needed for
  `randomTrips`-style internal demand, which is what E0.6 calls for.

None of these are required for E0.5's own DoD (grid + bottleneck + signalised corridor,
documented); they're candidates to revisit once E0.6 (demand profiles) or E3.2 (question bank)
show a concrete need.
