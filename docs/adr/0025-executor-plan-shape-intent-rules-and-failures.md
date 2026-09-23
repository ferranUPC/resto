# ADR-0025: Executor contract — plan shape, planning rules by intent, typed failures, forced last round

- Status: Accepted — completes ADR-0023; amends its free-mode loop (last round) and the §5 GP-11 row
- Date: 2026-09-23
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2, §2.3
  (`Study`, `StudyPlan`, `StepRecord`, `Experiment`, `ExpertRound`), §4.2, §4.8, §5;
  [ADR-0001](0001-tool-agent-port-and-draft-promotion.md), [ADR-0018](0018-network-expert-tools-and-evidence-refs.md),
  [ADR-0023](0023-coordinator-split-deterministic-executor.md); work-plan E3.4, E5.2–E5.11, E6.7, E7.1, E7.3

## Context

ADR-0023 moved plan execution out of the Coordinator into deterministic code (`run_study`, the
Executor) and took `ask_expert`/`compose_report` out of the plan. Writing down who does what in every
flow (normal, failure, each golden path) left gaps that ADR-0023 does not close:

- **Zero-step studies.** GP-1, GP-5 and GP-7 answer from stored results: with `ask_expert` no longer a
  step, their plan has no steps, but `StudyPlan` requires at least one. The plan also has no typed way to
  tell the Executor which network and which existing results the Expert is asked about —
  `reuse_decisions` is free text.
- **Who decides to simulate the treatment.** GP-3 (counterfactual, free) plans only what the baseline
  needs and lets the Expert ask for the treatment (`needs_simulation`); GP-11 plans the treatment up
  front. Two rules for the same kind of request make gold plans (E3.4) arbitrary.
- **Failures and the report.** §5 wants an injected failure to "surface in the final report with the
  failing step named"; ADR-0023's closing status gives a report only to `completed`. `StepRecord.error`
  is a string, so nothing tells the user whether rephrasing, a bigger budget or waiting would help.
- **Rounds exhausted.** ADR-0023's loop stops when `max_rounds` runs out, possibly on an answer that is
  still an abstention: the user gets no answer at all.
- **`Experiment.role`/`purpose` and seeds.** The Executor builds `Experiment`s and calls
  `run_simulation(scenario, seed)`, but nothing says where role, purpose and seeds come from. The role
  cannot be derived: in GP-11 the treatment is a scenario *without* interventions, on the derived network.
- **How the Executor calls agents.** `application/` cannot import `adapters/`, and the existing entry
  points (`run_scenario_builder`, `run_expert`) take the whole infrastructure (writers, paths, repositories)
  as arguments. `ToolAgent` is the port for "run an LLM with tools", not for "run the Scenario Builder".

## Decision

**1. The plan names what the Expert is asked about; zero steps is valid.** `StudyPlan` gains
`network_id: str | FromStep` (the network the study is about — `FromStep` when the plan creates it, as in
GP-8) and `reused: tuple[ReusedExperiment, ...]`, each `ReusedExperiment(scenario_id, role, purpose)`.
`steps` may be empty. The free-text `reuse_decisions` is dropped (`rationale` stays). The Executor turns
every reused scenario into an `Experiment` (its stored *ok* results) and marks it `reused=True`, so the
report's experiment table (§4.8) tells what was run now from what was already there.

**2. What the Coordinator plans depends on `intent`.**

| `intent` | Phase 0 plan |
|---|---|
| `describe`, `diagnose` | ensure baseline results exist (reuse, or build + run the baseline) |
| `counterfactual` | ensure the baseline only; the treatment is simulated only if the Expert asks for it (`needs_simulation`) |
| `run` | the experiments the user asked for (baseline and treatment) |
| `compare` | ensure results exist for every scenario being compared |

Phases ≥ 1 are always planned as `run`: the Expert has asked for that experiment. Mode (free/forced) does
not change the plan, only what the Expert may answer. GP-11 ("add an edge between J7 and J9", trace
unchanged) is a `run` request; a free-mode *counterfactual* topology question follows GP-3's shape, with
`derive_network` + `reroute_demand` in phase 1. This is the rule the gold plans of E3.4 encode.

**3. Failures are typed and rendered without an LLM.** `StepRecord.error: str` becomes
`StepError(kind, message, details)`:

| `kind` | Examples | What the user can do |
|---|---|---|
| `user_input` | unknown edge, intervention the Builder rejected (`rejected[]` reason) | rephrase; the report names the wrong or missing item |
| `budget` | per-agent or per-`Study` budget exhausted | narrow the question, or rerun with an explicitly raised budget |
| `agent` | no valid draft (Network Author never passes sanity; `unresolved[]` lists the edges) | retry or change the approach |
| `infrastructure` | SUMO crash, `netconvert` failure, OSM or repository unavailable | nothing on their side; logs path given |

The Executor classifies each failure when it records the step (promotion exceptions and
`SimulationResult.status == failed` — which is a returned value, not an exception). On the first failure
it stops, skips the pending steps and persists. The Output Composer runs only for `completed`;
`failed` and `awaiting_user` studies are rendered deterministically by `interface/render.py` in three
blocks: what happened, what was done (reusable: a rerun reuses everything already promoted), what the user
can do. `awaiting_user` lists the ambiguities (Parser) or the candidates (Coordinator, e.g. two networks
labelled "Gran Via"). This rendering is the "final report" of §5 for failed studies. A Parser that cannot
produce a valid `Question` creates no `Study` (it cannot exist without one); the CLI reports the error.

**4. The last round is forced.** In a free study, rounds `1 … max_rounds − 1` are free and round
`max_rounds` (3) is sent with `ExpertTask.mode = forced`, so a free study always ends with an answer.
`ExpertRound` gains `forced_by_limit: bool`; `compose_report`'s promotion (code, not the Composer) adds a
fixed limitation line when the last round carries it. The loop of ADR-0023 becomes:

```python
round = ask_expert(original_question, all_results, mode=mode_for(round_no=1))
while round.needs_simulation:                    # only possible while mode_for(...) is free
    plan = coordinator(round.answer.proposed_experiment)
    execute(plan)
    round = ask_expert(original_question, all_results, mode=mode_for(round_no + 1))
```

**5. The Coordinator declares role and purpose; seeds are Executor policy.** The `build_scenario` plan
step and `ReusedExperiment` carry `role` (baseline / treatment / comparison) and `purpose`. `run_simulation`
steps use `DEFAULT_SEEDS = (1, 2, 3)` — the scenario matrix's seeds, so studies reuse matrix results by
`result_id` — unless the step overrides them.

**6. One port per agent.** `application/ports/agents.py` defines one narrow protocol per agent, task in,
run out: `InputParserAgent(text) -> AgentRun[Question]`, `CoordinatorAgent(question, context) ->
AgentRun[StudyPlan | Clarification]`, `NetworkAuthorAgent(NetworkTask)`, `DemandGeneratorAgent(DemandTask)`,
`ScenarioBuilderAgent(ScenarioTask)`, `ExpertAgent(ExpertTask, ledger)`, `NoteWriterAgent(round, …)`
(ADR-0026), `ComposerAgent(study)`. The existing `run_<agent>` functions are the implementations, with the
infrastructure bound in the composition root (`interface/cli`). Promotion use cases keep taking a finished
`AgentRun`, as `build_scenario` and `ask_expert` already do.

## Consequences

- Domain (E5.9): `StudyPlan` with `network_id`, `reused` and possibly no steps; `ReusedExperiment`;
  `role`/`purpose` on the `build_scenario` step variant; `Experiment.reused`; `StepError` replacing the
  string; `ExpertRound.forced_by_limit`. Schemas and `docs/class_diagram.md` regenerated.
- Executor (E5.10): step classification into `StepError`, `mode_for`, `DEFAULT_SEEDS`, the ports of
  decision 6. Each specialist task that builds an agent (E5.1, E5.2, E6.1, E6.2) also provides its port
  implementation.
- Rendering of failed and `awaiting_user` studies is new work (E5.11); the failure-injection suite (E7.3)
  asserts on `StepError.kind` and on the rendered blocks, not on message strings.
- Gold plans (E3.4) contain `network_id`, `reused` and role/purpose, follow decision 2, and may have zero
  steps. Golden-path traces start with the Input Parser (ADR-0023).
- §5's GP-11 row is read as a `run` request; its trace is unchanged. The frozen v1.0 body is not edited.
- `docs/study-flows.md` documents every flow under this ADR and replaces `study_flow_diagram.md` and
  `agent_communication_diagram.md` (moved to `docs/_old/`).
- Still open, unchanged: `ExpertTask` over a base and a derived network (ADR-0023), decided in E5.3.

## Alternatives considered

- **Keep `ask_expert` as a mandatory plan step so no plan is empty.** Rejected: ADR-0023 took it out so a
  plan cannot forget the Expert; putting it back reintroduces that failure.
- **Let the Coordinator decide per request whether to simulate a counterfactual's treatment.** Rejected:
  gold plans become a matter of taste, and it hides the Expert's abstention decision — the thing
  abstention recall and the learning effect measure.
- **Run the Output Composer on failed studies too.** Rejected: an LLM call to explain a failure that code
  already knows, and one more thing that can fail.
- **After max rounds, report the abstention as the answer.** Rejected: the user gets no answer; a forced
  answer marked `extrapolated`, with the limitation stated, is more useful and just as honest.
- **When a phase ≥ 1 fails, fall back to a forced round instead of failing the study.** Not adopted: it
  reports a completed study after a failed step, against §4.2/§5 ("never partial success reported as
  success"). Can be revisited once failure-injection results exist.
- **Derive `role` from the scenario (no interventions ⇒ baseline).** Rejected: wrong for topology
  experiments, where the treatment has no interventions.
- **Let the Executor call `run_<agent>` functions directly.** Rejected: `application/` would import
  `adapters/` and carry every agent's infrastructure arguments.
