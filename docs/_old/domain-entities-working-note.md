# Domain entity model — open design problem

Working note for whoever (human or agent) picks this up next. Goal: finish deciding which domain
entities RESTO actually needs, and for each one, whether it's an **entity** or a **value object**.
This is not done — this document exists to hand off the reasoning so far without having to
re-derive it.

This is a private, in-progress working note — not one of the two frozen source-of-truth docs
(`../tfm-architecture-and-dod.md`, `../tfm-work-plan.md`). Once the questions below are resolved,
the outcome belongs in `tfm-architecture-and-dod.md` (as decisions in §7, and possibly a small
Mermaid diagram near §2.2), not here.

## The problem

`docs/tfm-architecture-and-dod.md` §2.2 defines 11 **contracts** — the payloads that cross module
boundaries (`ExperimentRequest`, `Intervention`, `ExperimentPlan`, `Network`, `Demand`, `Scenario`,
`TraciPlan`, `SimulationResult`, `ExpertAnswer`, `ExpertNote`, `Report`). That table says who
produces/consumes each one and lists their "essential fields," but it does not say:

1. Which of these are true **domain entities** (their own identity, independent lifecycle, looked
   up by id from elsewhere) versus **value objects** (no identity, fully defined by their
   attributes, only ever exist embedded inside an entity that owns them). This matters for E0.3
   (contracts as Pydantic models) and E1.3 (DatabaseMCP reference impl) — it determines what gets
   its own `store_x`/`get_x` DatabaseMCP tools versus what only ever travels embedded inside
   something else.
2. How the domain entities relate to each other (composition vs. reference-by-id across
   aggregates) — currently only reconstructable by reading the actual dataclasses in
   `src/resto/domain/`, not written down anywhere.
3. Whether the model is missing an entity that ties a whole request-to-answer chain together for
   traceability purposes (see "Open question 2" below).

## Method: how to tell entity from value object

Not "does it have an `id` field in the dataclass" (that's an implementation detail that can be
added or removed without changing what the thing conceptually is). The real test:

> Does anything in the system need to fetch **this specific instance** again later, independently,
> by an opaque identifier — or does it only ever exist embedded inside the one entity that created
> it, fully replaceable as a whole?

Operationally, for this project: check whether `DatabaseMCP`'s capability table (§2.2, "Tools
grouped by capability") has a `store_x`/`get_x` pair for it. If yes → entity. If it only ever
appears nested inside another contract's fields → value object.

## Current state in code (`src/resto/domain/`)

### Entities (`domain/entities/`)

| Entity | Own id | Referenced by id from elsewhere | DatabaseMCP tools |
|---|---|---|---|
| `Network` (`entities/network.py`) | `network_id` | `Scenario.network_id` | `store_network`, `get_network`, `list_networks` |
| `Scenario` (`entities/scenario.py`) | `scenario_id` | `SimulationResult.scenario_id` (per §2.2; not yet implemented) | `store_scenario`, `get_scenario`, `find_similar_scenario` |

Both pass the test cleanly: independent DatabaseMCP tools exist, and other contracts reference
them by id rather than embedding them whole.

### Filed under `entities/` but structurally a value object

| Thing | Own id | Independent DatabaseMCP tools | Verdict |
|---|---|---|---|
| `TraciPlan` (+`TraciPlanEntry`) (`entities/traci_plan.py`) | none | none (§2.2: only travels Builder → Runner, embedded inside `Scenario.traci_plan`) | **Value object.** Filed in `entities/` for now (groups naturally with "things the Builder produces"); not urgent to move, but the classification is VO, not entity. |

### Value objects (`domain/value_objects/`)

- `Intervention` (`value_objects/intervention.py`) — no own id, always embedded in
  `Scenario.interventions`. Composes `InterventionTarget`.
- `InterventionTarget` (`value_objects/intervention_target.py`) — discriminated union
  `EdgeTarget | LaneTarget | TlsTarget | TazTarget`. Structured targets, no ids of their own.
- `NetworkSource` (`value_objects/network_source.py`) — composed by `Network`.
- `SanityReport` (`value_objects/sanity_report.py`) — composed by `Network`.

### Composition vs. reference-by-id, as it stands today

```
Scenario o-- Intervention        (composes: no id, same lifecycle as the Scenario)
Scenario o-- TraciPlan           (composes, optional: no id, same lifecycle)
Scenario ..> Network             (references by id: network_id, resolved via DatabaseMCP)
Scenario ..> Demand              (references by id: demand_id — see open question 1)
Intervention o-- InterventionTarget
Network o-- NetworkSource
Network o-- SanityReport
```

`o--` = composition (owned, no independent id). `..>` = reference by opaque id, resolved
separately through DatabaseMCP.

## Open questions still unresolved

### 1. `Demand` — entity, or filesystem artifact like `.net.xml`?

§2.2 gives `Demand` its own `demand_id` and lists it as consumed by `DatabaseMCP`, which points
to "entity, like `Network`." But the DatabaseMCP capability table (§2.2) has **no** `demand`
capability group — no `store_demand`/`get_demand`. The only demand-related tool is
`historical_demand.get_historical_demand(network_id, day_type, hour)`, which is a different thing
(real-world historical traffic data used to seed generation, not the generated route/trip files
themselves).

Two ways to resolve it, need to pick one before writing any `Demand` code:

- **(a) `Demand` is a full entity**, symmetric with `Network`: add a `demand` capability group to
  DatabaseMCP (`store_demand`, `get_demand`, `list_demands`) in the E0.4 contract spec. Then
  `Scenario.demand_id` is a real cross-aggregate reference, same pattern as `network_id`.
  Route/trip files themselves (large artifacts) still live on the filesystem, referenced by
  path/hash from within the `Demand` record — same pattern `Network` uses for `.net.xml`.
- **(b) `Demand` is not a domain entity at all**, just generated route/trip files referenced by
  path/hash directly from `Scenario`, the same way large simulation artifacts (edgedata, tripinfo)
  are handled — no separate store/get, no independent lookup, `demand_id` becomes just a
  content-hash-derived label rather than a real cross-aggregate reference.

This decides E0.4 (DatabaseMCP contract spec) and blocks writing a real `Demand`
entity/value-object either way.

### 2. Is there a missing `Experiment` identity for traceability?

None of `ExperimentRequest`, `ExperimentPlan`, `ExpertAnswer`, or `Report` carry an id in their
§2.2 "essential fields," and none of them carry a back-reference to the earlier step in their own
causal chain (`SimulationResult` has `scenario_id`, but `ExpertAnswer` has no `result_id` or
`scenario_id`; `ExperimentPlan`/`Report` have nothing tying them back to the `ExperimentRequest`
that started the chain).

This looks like a real gap against two things the architecture doc itself requires:

- Design principle 6: *"Every answer carries evidence. No module produces a claim that cannot be
  traced to an artifact."*
- E5.7 (work plan): *"Output Composer Done: automatic traceability checker."* — hard to build an
  automatic checker if there's no id threading the chain for it to follow.

Two options, not yet decided:

- **(a) Introduce an `Experiment` entity** (aggregate root) with its own `experiment_id`, from
  which the request, plan, scenario(s), result(s) and answer are all reachable by id.
- **(b) No new entity** — just add an `experiment_id` (or reuse `request_id`) field to
  `ExperimentRequest`, `ExperimentPlan`, `ExpertAnswer` and `Report`, threading it through
  end-to-end without a dedicated aggregate object.

## What "done" looks like for this task

- Every one of the 11 §2.2 contracts classified as entity or value object, with the reasoning
  (not just the label) — using the independent-lookup test above, not vibes.
- Open questions 1 and 2 above resolved one way or the other.
- The resulting model written into `tfm-architecture-and-dod.md`: classification decisions folded
  into §7 ("Decisions taken"), and a small relationship diagram (Mermaid, in the style sketched
  above) placed near §2.2 — scoped to what actually exists, extended incrementally as more
  entities get implemented rather than drawn all at once for contracts that don't exist yet.
- This file (`docs/private/domain-entities.md`) can be deleted once that's done — it's scaffolding
  for the discussion, not a permanent doc.

## Where this came from

This reasoning was worked out across two conversations, not derived from scratch — check those
transcripts (`~/.claude/projects/-Users-ferrangonzalez-Documents-repos-resto/*.jsonl`, readable
with any JSON-lines viewer) before re-deriving anything above from first principles:

- The writer-per-mechanism decision for the Scenario Builder (`AdditionalFileWriter` port,
  `RerouterWriter`/`VssWriter`/`TlsProgramWriter`/`TazWriter` in
  `adapters/scenario_builder/writers/`, dispatch via `supports()`) is separate from this entity
  question but was resolved in the same line of discussion and is already recorded in
  `tfm-architecture-and-dod.md` §7.
- The `application/contracts/` placement decision (Pydantic models for the 11 §2.2 contracts live
  in the application layer, not a new top-level package, per this project's hexagonal layering —
  `domain/` stays framework-free) is the reason the entity/value-object classification in this
  document matters: it determines which contracts need a `to_domain()`/`from_domain()` mapper
  against an existing dataclass, and which are the only representation there is.
