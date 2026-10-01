# ADR-0037: The specialists resolve the network and the demand; the Coordinator plans the experiments and never reads the database

- Status: Accepted (2026-10-01, E3.7 grilling). Replaces the Coordinator's database tools and its
  clarification output (ADR-0023 decision 1), points 2, 3 and 6 of [ADR-0035](0035-described-demand-no-default.md)
  as the Coordinator's rules (they now bind the specialists), `StudyPlan.reused` and the "zero steps is
  valid" rule of [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md) decision 1, and the
  "reuse, or build" half of ADR-0025 §2. Built by the tasks that change E5.2, E5.9, E5.10, E6.1 and E6.2
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2, §2.4, §4.2;
  [ADR-0023](0023-coordinator-split-deterministic-executor.md), ADR-0025, ADR-0035,
  [ADR-0036](0036-raw-demand-data-aggregate.md); work-plan E3.7, E5.2, E5.9, E5.10, E6.1, E6.2

## Context

ADR-0023 gave the Coordinator four read-only tools (`find_network`, `find_demand`, `find_scenario`,
`list_results`), so it decides before anything runs whether a network exists, which stored demand matches
the request, and which scenarios already have results. ADR-0035 added the rules for that decision.

Grilling the plan bank (E3.7) showed what this costs:

- The Coordinator's gold plan depends on the database: four states, distractors, synthetic results. The
  bank would measure database lookup, not experiment design.
- The agent that knows how to obtain a network is the Network Author, and the one that knows what a demand
  covers is the Demand Generator. The Coordinator decides on their behalf, then hands them a result.
- In practice an id travels down the pipeline: the Demand Generator needs the id of the network that was
  resolved, not the name the user wrote, and checks what demands that network has.

None of the specialist agents is built yet (E6.1 and E6.2 are placeholders), so the change lands before
the code it would rewrite.

## Decision

1. **The Coordinator has no database tools.** It maps a `Question` to a `StudyPlan` and decides only what
   the experiment needs: the arms, the role and purpose of each scenario, and what runs for each `intent`
   (ADR-0025 §2, ADR-0027). Its output is a `StudyPlan`. The clarifications that depend on the database
   no longer come from it.
2. **Two plan steps replace `generate_network` and `generate_demand`:** `obtain_network` and
   `obtain_demand`. Each carries the reference the Parser wrote (`network_ref`, `demand_ref`) and, for the
   demand, the study window. The later steps (`derive_network`, `reroute_demand`, `build_scenario`,
   `run_simulation`) take their ids through `FromStep` as they do now. A plan always contains
   `obtain_network`, so zero-step plans no longer exist; a network-only question (ADR-0035 point 5) is a
   plan whose only step is `obtain_network`.
3. **The specialist resolves.** The Network Author and the Demand Generator get `find_network` and
   `find_demand` (the tools of ADR-0023, moved). Their output is one of `Found(id)`, a draft to generate
   from (promoted by code, ADR-0001), or `NeedsUser(reason, candidates)`. The rules of ADR-0035 apply to
   them: the Network Author for points 6 (networks by name), the Demand Generator for points 3 and 4 (a
   stored demand whose window contains the request is reused, one that can be obtained is generated, an
   unobtainable one is asked about, a request with no demand named is asked about). The Demand Generator
   receives the id of the network already resolved, never the reference.
4. **`NeedsUser` puts the `Study` in `awaiting_user`**, not `failed`, with the candidates and what was
   already found ("the network was found, the demand was not"). The Executor stops at that step, as it does
   at a failure; a rerun reuses everything promoted (ADR-0025 decision 3). When no window can be derived
   for the demand, the Demand Generator asks for the period, and "it does not matter" is a valid answer.
5. **The study window is derived by code from the `Question`:** the smallest interval that contains the
   window of every intervention in every arm (`CONTEXT.md`, **Study window**). One demand serves all arms.
6. **Reuse of scenarios is found by the Executor, not planned.** Before calling the Scenario Builder, the
   Executor looks the scenario up by the hash of the typed request and, when its `ok` results exist, marks
   it `reused`. `StudyPlan.reused` is dropped. One thing to verify when this is built: `build_scenario`
   computes `scenario_id` from the interventions the Builder accepted, so the hash before the call must
   equal the hash after it. Where they can differ, the Builder is called and the duplicate is found as
   today.

## Consequences

- Parser and request bank (E3.11): unchanged. `demand_ref`, `time_window` and `network_only` mean the same.
- ADR-0035 keeps points 1, 5 (the plan changes, see decision 2) and 7. Point 4 ("peak hour" is a
  description) is read by the Demand Generator.
- E5.9 and E5.10 (done) change: the two step variants, `StudyPlan` without `reused`, the `NeedsUser`
  outcome and its `awaiting_user` rendering, the Executor's scenario lookup. E5.2 loses its tools and its
  four database states. E6.1 and E6.2 gain the resolution behaviour and its evaluation.
- The plan bank (E3.7) no longer depends on the database: one gold plan per concept (arms, roles, steps by
  `intent`), with no DB states, no distractors and no plan-or-clarification field. The resolution cases
  (reuse, generate, ask, distractors, demands described by day) become a bank for each specialist, built
  from the same states designed for E3.7.
- The study's cost changes: a database lookup is no longer an agent step of the Coordinator but a tool
  call inside a specialist that runs only when the plan needs that specialist.

## Alternatives considered

- **The Coordinator keeps the lookup** (ADR-0023). Rejected: it ties the plan to the database state and
  makes the specialists receive decisions they would take better with their own tools.
- **One shared resolver agent for networks and demands.** Rejected: another agent to evaluate, and the
  match differs (a name for networks; a description and a window for demands).
- **Always call the Scenario Builder and let the hash find duplicates afterwards.** Rejected: simulations
  would not repeat, but every study would pay an LLM call per scenario, which the cost policy forbids
  without need.
- **Let the Coordinator return `NeedsUser` as well.** Rejected: whatever it could ask now depends on the
  database, which it does not read; the Parser already asks about the text.
