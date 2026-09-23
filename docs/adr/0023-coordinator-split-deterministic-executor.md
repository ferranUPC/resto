# ADR-0023: Coordinator split — Input Parser, one-shot Coordinator, deterministic Executor; `Study` in phases

- Status: Accepted — supersedes ADR-0001's Coordinator consequence and the `Study` shape in ADR-0002;
  plan shape, failures and the loop's last round completed by [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md)
- Date: 2026-09-22
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §1 (principles
  3, 5, 6), §2.2, §2.3 ("The loop with this model"), §2.4 (Coordinator), §4.1, §4.2, §5, §8;
  [ADR-0001](0001-tool-agent-port-and-draft-promotion.md), [ADR-0002](0002-domain-model-aggregates-and-identity-policy.md),
  [ADR-0018](0018-network-expert-tools-and-evidence-refs.md)

## Context

The v1.0 Coordinator is one tool-using agent that turns user text into a `Question` and a `StudyPlan`,
calls the specialists as tools, and closes the `Study` — its output column in §2.2 reads "`Question` +
`StudyPlan` first, then `StudyOutcome`". `ToolAgent.run` returns one `output: T` per call, so that is
either two calls or one call with an unspecified shape; ADR-0001 names the tension ("still fit the draft
shape") without resolving it, and it has been carried unresolved since v0.2.

The Input Parser was merged into the Coordinator in v0.2 for plan-cost reasons only ("may be merged… if it
stays trivial"), yet the DoD still evaluates it separately (§4.1 vs §4.2). A single agent holding 13
tools over the whole study is also the hardest agent in the system to make reliable on the cheap default
model (CLAUDE.md cost policy).

Looking at what the Coordinator decides once a plan exists, nothing needs an LLM: walking the plan in
dependency order, the guards (§2.4), and the closing status are mechanical, and §4.2 puts "replanning on
failure" in *Stretch* — *Done* only asks that a failure yield a failed step by name. The one real decision
after planning is the free-mode Expert asking for a new experiment, and that request is already a typed
`Question` (`ExpertAnswer.proposed_experiment`).

## Decision

**1. Three pieces, two of them agents.**

| Piece | Kind | Input → output | Tools |
|---|---|---|---|
| Input Parser | `ToolAgent` | user text → `Question` | none |
| Coordinator | `ToolAgent`, **one `run` per `Question`** | `Question` + DB state → `StudyPlan` or a clarification request | read-only: `find_network`, `find_demand`, `find_scenario`, `list_results` |
| Executor (`run_study`) | deterministic code | walks plans, calls specialists, promotes, records | — |

- The Input Parser has no database access, so `Question.network_ref` is a textual reference ("Gran Via"),
  resolved by the Coordinator. Non-empty `ambiguities[]` puts the `Study` in `awaiting_user` before the
  Coordinator is called.
- The Coordinator can also return a clarification request instead of a plan, for ambiguities only the
  database reveals (e.g. two networks match "Gran Via"). Asking the user is an *output* of either agent,
  never a tool: `ask_user` leaves the catalogue.
- `StudyOutcome` is dropped. The closing status is mechanical: ambiguity (from either agent) →
  `awaiting_user`; any failed step → `failed`; report composed → `completed`.

**2. Plans are typed, immutable and only produce evidence.**

- `PlanStep` becomes a discriminated union, one variant per use case the plan may call:
  `generate_network`, `derive_network`, `generate_demand`, `reroute_demand`, `build_scenario`,
  `run_simulation`. Each variant carries the fields of that use case's typed task.
- Ids that do not exist at planning time (every content-hash id of an artifact the plan itself produces)
  are written as `FromStep(i)`; the Executor substitutes the id produced by step `i`. Invariant: every
  `FromStep(i)` in a step is also in its `depends_on`. This makes a plan syntactically validatable
  (ADR-0001 step 1), which `inputs: Mapping[str, Any]` could not be.
- `ask_expert` and `compose_report` are not plan steps: the Executor runs them (below), so a plan cannot
  forget the Expert or the report.
- A plan is never revised once promoted. A rejected specialist draft or a failed tool call is a failed
  step by name and fails the `Study`; there is no re-ask with a corrected task. This resolves §8's open
  question (zero re-asks in Minimal/Done; replanning stays §4.2 Stretch).

**3. The free-mode loop plans a new phase; it never replans.**

```python
round = ask_expert(original_question, result_ids_of_all_phases)
while round.needs_simulation and rounds_left:
    plan = coordinator(round.answer.proposed_experiment)     # a new plan for a new Question
    execute(plan)
    round = ask_expert(original_question, result_ids_of_all_phases)
compose_report(study)
```

- The Expert is always asked the **user's original question**, with the results of every phase so far.
  The proposed experiment is more evidence for the same question, not a question to be answered on its
  own.
- `proposed_experiment` is a full `Question`: other demand, other time window, other interventions, and
  `topology_changes` are all allowed. Since any topology change is a different `.net.xml`, it is planned
  as `derive_network` (+ `reroute_demand`) from the current network. `ask_expert`'s existing check stays:
  `network_ref` must be `None` or the current network — the base network the changes apply to, not
  another place.
- If the Coordinator returns a clarification request for a proposed experiment, there is no user to ask
  (the Expert asked): the round fails by name.
- Phases never produce a report. The Output Composer runs once, at the end, over the whole `Study`. The
  Expert reads results directly through its own tools, so its evidence stays in its own call ledger
  (ADR-0018) and it never cites another agent's summary (principle 6).
- Forced mode: one phase, no loop.

**4. `Study` is stored in phases.**

```python
@dataclass(frozen=True, slots=True)
class Phase:
    question: Question               # phases[0]: the Input Parser's; then each proposed_experiment
    plan: StudyPlan | None = None
    steps: tuple[StepRecord, ...] = ()
    experiments: tuple[Experiment, ...] = ()
    round: ExpertRound | None = None

@dataclass(frozen=True, slots=True)
class Study:
    study_id: str
    status: StudyStatus
    phases: tuple[Phase, ...]
    report: Report | None = None
    network_ids: tuple[str, ...] = ()
    note_ids: tuple[str, ...] = ()
    max_rounds: int = DEFAULT_MAX_ROUNDS

    @property
    def question(self) -> Question:
        return self.phases[0].question
```

Invariants (`__post_init__`): `phases[k+1].question == phases[k].round.answer.proposed_experiment`; rounds
≤ `max_rounds` (3); forced ⇒ exactly one phase; a phase with steps has a plan; ambiguous question ⇒ one
phase, no steps, `awaiting_user`; `completed` ⇒ report. `ExpertRound.triggered_experiments` is removed,
because each phase's experiments already belong to it.

**5. A total budget per `Study` is required.** A round can now run the Network Author and the Demand
Generator, not just one simulation, so the per-`Study` budget guard of §2.4 is mandatory, not optional.

## Consequences

- Seven agents on the one `ToolAgent` port (Input Parser added); every one is task in, one draft out,
  one call. ADR-0001's single-port decision stands; its Coordinator consequence is replaced by this ADR.
- Principle 5 extends to orchestration: with the `Question`, the plans and the `ExpertAnswer`s stored, a
  `Study` replays without an LLM.
- §4.2 routing: "`StudyPlan` vs gold plan" is the agent metric; "`StepRecord` trace vs expected" becomes
  a property of deterministic code, covered by unit tests with the fake `ToolAgent`. Gold plans in the
  request bank (§3) contain no `ask_expert`/`compose_report` steps. The §5 golden-path traces are
  unchanged (GP-3 already reads "Expert (`needs_simulation`) → Coord → Builder → Runner → Expert").
- In free mode the executed steps are not all in `phases[0].plan`; that is expected, not a routing error.
- Domain changes: `Phase`, `Study.phases`, typed `PlanStep` + `FromStep`, `ExpertRound` without
  `triggered_experiments`; `schemas/Study.json` and `docs/class_diagram.md` regenerated when implemented.
- The v1.0 body (the "Changes vs v0.2" agents bullet, §2.1 Coordinator row, §2.2 Coordinator rows, §2.3 `Study` invariants and
  loop, §2.4 Coordinator paragraph, §4.1 heading, §7 ADR-0001 bullet, §8 re-ask question) is superseded
  here, not edited, per the frozen-document rule.
- **Open:** `ExpertTask.network_id` holds one network, but after a `derive_network` phase the results sit
  on two (base and derived). The re-ask needs `ExpertTask` to carry the networks of the results it is
  given; decided when E5.3 is implemented.

## Alternatives considered

- **Keep one Coordinator agent (v1.0).** Rejected: two outputs from one `run`, a long 13-tool horizon on
  the cheap model, and orchestration decisions that are not reproducible without the LLM.
- **Coordinator in two calls (plan, then `StudyOutcome`).** Rejected: every closing decision is
  mechanical.
- **Executor as a fourth `ToolAgent`.** Rejected: once the plan and the proposed experiments are typed,
  no decision is left that needs judgment.
- **Re-invoke a planner when a specialist draft is rejected.** Rejected: that is replanning on failure,
  §4.2 Stretch.
- **Restrict `proposed_experiment` to new interventions on the inherited network, demand and window.**
  Rejected: too narrow — a topology change is a different network and a different window needs a
  different demand, both legitimate Expert hypotheses.
- **A child `Study` per proposed experiment, feeding its Composer's report back.** Rejected: the Expert
  would cite another agent's summary instead of simulation data (principle 6; `_check_evidence` could not
  resolve it), a Composer run would be paid per round, and status/report would be split across studies.
