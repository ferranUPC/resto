# ADR-0032: The Expert sees the study's network scope; edge references name their network

- Status: Accepted (2026-09-29) — amends ADR-0019 (typed answer values) and ADR-0026 (which network a note
  belongs to); replaces the estimate in ADR-0030 that E5.3 "touches only `expert_round`"
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3–§2.5;
  work-plan E5.2, E5.3, E6.7 (GP-11)

## Context

`ExpertTask.network_id` and `PlanningContext.network_id` are singular, and seven modules interpret them on
their own. A topology modification derives a new `Network` (its id is the hash of its `.net.xml`) that lives
next to the base one in the same study, and edge ids repeat across the two. Three consequences: the Expert
cannot see an edge the derivation added, `ask_expert` rejects a correct answer about it, and a note about a
derived scenario is stored under the study's network but looked up under the scenario's network, so it is
never verified.

## Decision

- **Scope.** A **Network scope** (see `CONTEXT.md`) is read from `Study.network_ids` when an Expert round
  starts. `ExpertTask` carries `network_ids`; every topology tool takes an explicit `network_id`, checked
  against the scope. A Planning step gets only the networks that exist when it plans.
- **Answer values.** Every `AnswerValue` that names an edge also names its network, always, not only when
  the study has several networks. `ask_expert` checks the edge against that network.
- **Notes.** A note's network is derived by code: the network of its scenario, or the study's base network
  when it has no scenario. The note writer never chooses it. A note that contrasts two networks is written
  as two notes, one per scenario.
- **One loader.** A `NetworkQueryLoader` port (`application/ports/network_query.py`) answers "which
  `NetworkQuery` belongs to this network id"; `expert_round`, the tools, `ask_expert`, the notes and the
  Scenario Builder ask it instead of loading networks. Its adapter (`adapters/sumo/network_query_loader.py`)
  reads the repository, builds the sumolib query and keeps one query per id, so `application/` never holds
  a query factory.

## Consequences

- Five value variants carry an edge (`Edges`, `Quantity`, `Change`, `NoValue`, `EdgeCause`), and so do the
  gold answers of the question bank. Each gets its own `network_id` field, not a shared edge-reference
  type (decided 2026-09-30, ticket r4/02). `Edges` holds one list of edges on one network, so a single
  field covers the whole list (an empty list still names the network it was asked about). `Quantity` and
  `Change` carry `network_id` exactly when they carry an `edge_id` (a network-wide measure names no
  network). `NoValue` and `EdgeCause` always carry it. A shared type would add a nesting level to every
  value the model writes and to every gold answer, for no invariant that a field pair does not already
  give. The gold migration is ticket 03.
- A pure opinion about a derived network, written without a scenario, is stored under the base network.
  Judged rare; revisit if `hygiene_probes` show otherwise.

## Alternatives considered

- One Expert round per network: cannot express "does the derived network improve on the base one", which is
  what GP-11 asks.
- Restrict the scope to the networks of the analysed `result_ids`: needs the scope rebuilt from scenarios on
  every round and a rule for the base network when no result uses it.
- Let the note writer pick the note's network: an identity field set by an agent, against ADR-0001.
