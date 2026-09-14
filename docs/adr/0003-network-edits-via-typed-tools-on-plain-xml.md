# ADR-0003: Network edits only via typed tools on plain XML; recipe stored and replayable

- Status: Accepted
- Date: 2026-09-11
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.4 (Network Author)

## Context

SUMO's compiled `.net.xml` is a derived artifact, not a source of truth — editing it directly leaves no
discoverable, replayable record of *what changed*. The Network Author is an LLM agent; per ADR-0001, its
output must be reproducible and verifiable independent of what the LLM claims it did, and per ADR-0002,
`Network`'s identity is a content hash of that same compiled file — so the causal history of how that hash
came to be must itself be data, not agent prose.

## Decision

The Network Author never edits the compiled `.net.xml`. Every change is either a `netconvert` option
(cleanup-class changes: `--keep-edges.components 1`, `--remove-edges.isolated`, `--junctions.join`,
`--keep-edges.by-vclass`, `--geometry.remove`, …) or a typed tool call on the **plain-XML** representation
(`netconvert --plain-output-prefix` → `.nod.xml`/`.edg.xml`/`.con.xml`/`.tll.xml`), recompiled with
`netconvert -n -e -x`. The ordered sequence of options and plain edits is the **recipe**
(`NetworkRecipe`: `source`/`base_network_id`, `osm_snapshot?`, `netconvert_options[]`,
`plain_edits: TopologyModification[]`), stored with the `Network` and replayable without the LLM:
`replay(recipe)` must reproduce the same `content_hash`. The v1 tool catalogue
(`remove_edge`/`add_edge`/`set_lanes`/`set_speed` + the `netconvert` options above) grows from the REAL-NET
hand-cleaning fix log (E6.3); an edit with no matching tool surfaces in `unresolved[]`, never as a silent
best-effort change.

## Consequences

- `content_hash` identity (ADR-0002) is trustworthy because the recipe is the network's actual causal
  history, not the agent's self-report of what it did — `replay(recipe)` reproducing the hash is a store-level
  test, not an assumption.
- The tool catalogue can grow incrementally from real evidence (the REAL-NET fix log) without changing this
  rule, and each new tool is itself typed and replayable the same way.
- Any edit the agent cannot express as a typed tool is visible as `unresolved[]` — evidence the sanity/probe
  loop didn't silently paper over, rather than a network that looks "good enough" but wasn't actually fixed.
- The agent is limited to whatever the catalogue currently expresses — a fix that would be trivial by
  hand-editing the compiled XML directly cannot be made until a corresponding tool exists. Accepted: letting
  an agent hand-edit compiled XML would make the recipe (and therefore the id) fictional.

## Alternatives considered

- **Direct edits to the compiled `.net.xml` via `sumolib`, recorded as a diff.** Rejected: a diff of compiled
  output is not a discoverable, typed causal history and breaks `replay(recipe)` determinism — two networks
  with the "same" diff applied in different tool orders could compile to different bytes with no way to tell.
- **Free-text agent rationale as the only record of what changed.** Rejected: not machine-replayable,
  violates principle 5 ("decisions as data").
