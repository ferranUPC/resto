# ADR-0039: Planning is a deterministic function; the Coordinator agent is removed

- Status: Accepted (2026-10-06, refactor r13). Replaces the Coordinator row and the agent half of
  the clarification text of [ADR-0023](0023-coordinator-split-deterministic-executor.md) decision 1, and the
  `CoordinatorAgent` port and the role/purpose clause of [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md)
  (decisions 5 and 6, in part). Amends [ADR-0037](0037-specialists-resolve-network-and-demand.md),
  [ADR-0027](0027-experiment-arms-and-contrasts.md), [ADR-0038](0038-no-counterfactual-intent-contrast-decides-the-arms.md)
  and [ADR-0030](0030-executor-package-and-module-split.md) only where they name the Coordinator. Removes
  `allow_script` from the plan and the Builder task
- Date: 2026-10-06
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.4 (Coordinator),
  §4.1, §4.2 (routing metric), §7; ADR-0023, ADR-0025, ADR-0027, ADR-0037, ADR-0038; work-plan E3.7, E3.9,
  E5.2, E5.5, E5.8

## Context

After ADR-0037 and ADR-0038 the Coordinator decides nothing that code does not already decide.

- It has no database tools (ADR-0037), so it asks no clarifications and reads nothing from the database.
- The contrast fixes the arms (ADR-0038). `needed_arms` and the study window are domain code.
- The Executor rejects a plan with a missing or extra arm (ADR-0027, `plan_problems`). An agent can only
  match the rules or break them.
- The gold plan is already proposed by a rules script that imports nothing from the Coordinator, and the
  maintainer's review has corrected none of it.

The agent is almost entirely unbuilt: its adapter and tool module are placeholders. The cost is in the plan:
E5.2 (8 points), E5.5 (18 points, three repetitions in V2), part of E5.8, and a routing suite inside the $30
evaluation budget. Measuring the agent against that gold would measure how well a model imitates a script.

The reasoning behind it is a design finding: an agent belongs where the uncertainty is linguistic or about the
domain (the Parser, the specialists, the Expert, the Composer), not where rules suffice.

## Decision

**1. Planning is a pure function.** `plan(question, context) -> StudyPlan`, in the domain layer. The planning
context holds the current network id and the arms earlier phases realised. The Executor calls it where it
called the agent. The `StudyPlan` keeps its shape: typed steps, `FromStep`, `obtain_network` always first, a
network-only question is a plan of one `obtain_network`. The plan stays a typed, persisted artifact that the
study stores and replays. The planner is not merged into `run_study`: keeping it apart keeps the plan a value
and the rules testable alone (principle 5 of ADR-0023).

**2. The rules come from the gold script.** The logic of the existing plan-bank script moves into the domain
layer, since it imports only domain types. It follows ADR-0025 §2, ADR-0027 and ADR-0038 unchanged, and gains
the phase 1 case: a missing `network_ref` is replaced by the context's network id, and a
`proposed_experiment` plans as a `run`. Arms that earlier phases realised are not planned again. One
`derive_network` is planned per distinct topology, in phase 1 too.

**3. Failure is named.** A question the rules cannot plan raises a typed planning error. The Executor turns it
into a failed step with its own `StepError` kind, not an agent error. Nothing is improvised.

**4. `purpose` and `rationale` are templates** that name the arm, its role and its interventions. The Expert's
note writer still reads them. They are not gold.

**5. The Parser keeps the language work.** Turning a condition ("when occupancy on E4 exceeds 0.8") into a
typed `Condition` stays in the Input Parser. The planner copies interventions to the `build_scenario` of their
arm without interpreting them. The Builder chooses the mechanism, as today.

**6. `allow_script` is removed.** The field exists on `BuildScenarioStep` and on `ScenarioTask` and defaults
to `True`. Nothing sets it to `False`: the Executor copies it from the step to the task and the Builder does
not read it. Fixing it by planner policy would make the planner decide how a condition is implemented, which
the planner must not know (decision 5). It leaves both types and the regenerated schemas. If a real need to
forbid scripts appears (for example from the TraCI sandbox of E2.5/E2.6), it comes back as a Builder setting,
not a plan field.

**7. What is removed.** The `CoordinatorAgent` port and its `StudyPlan | Clarification` output, the
clarification request and the phase field that held it, the agent adapter and tool placeholders, the
composition-root slot for the agent, the agent-call spend of the planning phase, and the published schema of
the clarification request. A study keeps `awaiting_user` through the Parser's ambiguities and the specialists'
`NeedsUser`, which do not change.

**8. Vocabulary.** Code, glossary, ADR index and work plan say "the planner" for the function and "the
Executor" for the code that walks the plan. The glossary entries for Coordinator, clarification request and
gold plan are rewritten: the gold plan stays as the regression snapshot the planner is compared with. Earlier
ADRs keep their text, since they are an append-only record; their status lines say how to read them.

**9. The Definition of Done is reinterpreted, not edited.** The frozen v1.0 document is not touched. The
routing metric of §4.2 stops being an agent metric and becomes a deterministic test suite that must pass at
100 %. This ADR supersedes the row.

## Acceptance criterion

The ADR moves to `Accepted` when the maintainer reads it and the refactor tickets can start. The refactor is
done when all of these hold:

- The planner returns a valid plan for every valid `Question`, including a phase 1 `Question` with no
  `network_ref`, and every plan passes the Executor's plan validation.
- No reference to the agent remains in code, schemas, glossary, ADR index or work plan. The ADRs that record
  history are the only place the name appears.
- The eleven golden paths pass with the same trace shape.
- The routing target of the Definition of Done is restated as a test that passes at 100 %.

## How the planner is validated without circularity

The planner and the gold script are the same code, so the old routing percentage no longer measures anything.
Validation does not rest on that comparison:

1. **Hand-frozen oracle.** About 12 to 15 plans written by hand before the code moves, independently of the
   planner: a multi-arm question, the two conditional concepts, a network-only question, the seven-arm concept
   and a phase 1 case. The planner is never its own oracle.
2. **Properties on every plan** it returns: the arms equal the required arms, one `derive_network` per
   distinct topology, every `FromStep` appears in its step's `depends_on`, step ids are unique.
3. **Metamorphic tests:** permuting the arms changes the order but not the set of experiments; a `run` does
   not plan a base.
4. **Regression snapshot.** The existing plan bank (54 plans) runs against the planner and any difference is
   a visible diff to review. It is a snapshot, not evidence.
5. **Phase 1 cases** rebuilt from real Expert requests, since the first bank does not exercise them.
6. **External reading.** The supervisor reads five hard plans.

The Executor is evaluated once, through the golden paths and the failure-injection suite.

## Risks

- **Gold and rules are the same code.** The routing percentage is no longer evidence. Mitigation: the checks
  above, with the oracle written first.
- **Parser intent errors propagate deterministically.** A wrong `intent` yields the plan for that intent.
  "When in doubt, `compare`" (ADR-0038) bounds the damage, and an agent in the middle would not correct it
  either: it would see the same `Question`.
- **`purpose` and `rationale` become templates.** The Expert's note writer reads them. The loss is expected to
  be small because the arm, role and interventions carry the content; the ticket that moves the rules checks
  it by reading the notes of the golden paths.
- **The thesis loses an agent and its routing metric.** It gains a recorded design finding (see Context):
  agents stay where the uncertainty is linguistic or about the domain. Chapters E10.2 and E10.4 state it.

## Consequences

Effect on the work plan (1003 points today). The spec's estimates for E5.2, E5.5 and E5.8 are confirmed; its
net is corrected.

| Task | Now | After | Change | Why |
|---|---|---|---|---|
| E5.2 | 8 | 3 | -5 | Rules moved into the domain layer, oracle and property tests; no agent, prompt or port |
| E5.5 | 18 | 11 | -7 | Keeps the loop, the failure injection and the zero-redundant-runs counter; loses the routing harness and the three measured repetitions |
| E5.8 | 8 | 5 | -3 | Parser repetitions only |
| Refactor r13 (new task) | 0 | 3 | +3 | Wiring and deleting on the already built Executor, schemas, glossary, thesis architecture text |
| E3.7 | 4 | 4 | 0 | The plan bank stays as the snapshot; the phase 1 set is rebuilt inside the refactor |
| E3.9 | 5 | 5 | 0 | Loses the routing suite row (up to $4.5 of the $30, to confirm in E3.9) |

The net is about 12 points fewer of 1003 (11 to 14, depending on where E5.5 lands between -6 and -8). The
spec's first guess of 15 to 20 fewer is corrected to this, because the lines it listed add up to 11 to 14. The
E3.7, E5.2, E5.3 spine shortens, and M3 and M7 gain slack. The work plan edits follow this ADR once accepted.

- `Coordinator` leaves the code, schemas, glossary and plan. Other ADRs still name it where they recorded the
  past; each gets an amendment note in its status line.
- The domain has two functions that are both called a plan function (the planning rules and the request-id
  lookup of the plan bank). One is renamed in the ticket that moves the rules.
- Moving real-network goals and thresholds out of `obtain_network` is noted, not done here.
- Replanning on failure stays Stretch.

## Alternatives considered

- **Keep the agent and measure it against the gold.** Rejected: it measures imitation of a script, costs
  about 26 points in the plan and evaluation money, and cannot beat the rules.
- **Merge planning into `run_study`.** Rejected: the plan stops being a typed, persisted value and the rules
  are no longer testable alone.
- **Keep a thin agent for the wording of `purpose` and `rationale`.** Rejected: the arm, role and
  interventions carry the content, and the Expert is the one that reads and interprets.
- **Fix `allow_script` by planner policy.** Rejected: the planner would have to know how a condition is
  implemented.
- **Hide the Coordinator behind another name.** Rejected: the maintainer wants the idea removed, so a new
  reader does not look for an agent that does not exist.
