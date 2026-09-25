# ADR-0027: Experiment arms and contrasts — only the combinations a question needs

- Status: Accepted (2026-09-24, E5.13, with the contrast-direction rule added to §1) — domain types
  implemented (E5.12, E5.13); planning and plan validation pending (E5.2, E5.10), Expert and Composer
  use pending (E5.3, E5.4)
- Date: 2026-09-23
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3
  (`Question`, `Experiment`), §2.4, §2.5 (Network vs Scenario boundary), §4.1, §4.2;
  [ADR-0023](0023-coordinator-split-deterministic-executor.md), [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md),
  [ADR-0026](0026-expert-notes-per-study-and-prediction-verification.md); work-plan E3.4, E5.1–E5.4, E5.10, E5.12

## Context

A question may combine topology modifications (a different `.net.xml`, done by the Network Author) and
interventions (runtime behaviour on an unchanged network, done by the Scenario Builder). The model already
executes any set of scenarios — each `build_scenario` step is one (network, demand, interventions)
combination, several steps can share one derived network through `FromStep`, and identical requests
deduplicate by `scenario_id` — but three things are missing:

- **A question cannot say which combinations it asks about.** `Question` has one flat
  `interventions[]` and one flat `topology_changes[]`. "Does the new J7–J9 edge compensate the lane
  closure, and how does that compare to retiming J4?" puts three things in those lists with no way to say
  whether they are one combined treatment or alternatives. The same gap already affects `intent=compare`
  without any topology change: "is A better than B?" cannot be told apart from "A and B together".
  Planning every combination (N topology variants × M intervention sets) wastes simulations the question
  never asked for, and on a cheap model it is the Coordinator's taste that decides.
- **What is compared with what is implicit.** `ExperimentRole` is flat (baseline / treatment / comparison).
  With two treatments, nothing says which reference each is measured against: "derived network + closure"
  compared with "derived network" isolates the closure; compared with the base network it measures the
  joint effect. Only the free-text `purpose` says it, and the Expert's `Change` values and the Composer's
  claims need it typed.
- **An intervention cannot target an edge the same question adds.** `AddEdge` has no edge id; the id is
  chosen when the plain XML is edited, after the question and the plan exist, so "close a lane of the new
  edge" cannot be written down.

## Decision

**1. A question names its arms and the contrasts between them.** `Question` gains `arms: tuple[Arm, ...]`
and `contrasts: tuple[Contrast, ...]`.

- `Arm(label, topology_changes, interventions)` is one combination to simulate on the study's network and
  demand. The arm `BASE_ARM = "base"` — no changes, no interventions — is implicit and never listed. An
  arm with neither changes nor interventions is the base arm and is rejected.
- `Contrast(treatment, reference=BASE_ARM)` is one comparison the question asks about, by arm label.
  Labels are unique; a contrast names known arms (or `base`) and two different ones; contrasts do not
  repeat. When `contrasts` is empty, each arm is contrasted with `base`.
- *Added on acceptance (E5.13).* **Of two nested arms, the one contained in the other is the
  reference**, however the contrast was written: `base` is contained in every arm, so it is always a
  reference, and a combination is measured against its part ("derived network + closure" against
  "derived network"). `effective_contrasts` orients every such pair, and a contrast listed both ways
  counts once. Two arms that are not nested (alternatives: "closure or retiming") keep the order the
  question gives. Containment compares what the changes and interventions do, not their free-text
  `description` / `expected_effect`. The direction matters because §2 plans only the reference side
  of a `counterfactual` in phase 0, and a backwards contrast would simulate the wrong arm.
- The flat `interventions` / `topology_changes` stay as the **shorthand for the common case**: one
  treatment against the base. They and `arms` are mutually exclusive; `Question.effective_arms` turns the
  shorthand into one arm labelled `"treatment"`, and `effective_contrasts` supplies the default contrasts,
  so code reads one form only. The shorthand keeps the Input Parser's job small on the default model
  (most questions have one treatment) and keeps the existing question bank valid.

**2. The scenarios to run are derived from the contrasts, by code.** `required_arms(question)` is the
union of the contrasts' endpoints, base included only when a contrast references it. The plan builds or
reuses exactly those arms — never the N×M cross product — and one `derive_network` (+ `reroute_demand`)
per distinct set of `topology_changes`, shared by every arm that has it. The Executor's plan validation
(E5.10) checks that the arms of a plan are exactly those the phase needs; a missing or extra arm is an
invalid plan (`StepError(agent)`), so the saving is enforced by code rather than left to the model.
ADR-0025's rules by `intent` apply per arm: `counterfactual` plans only the reference side of its
contrasts in phase 0 (`reference_arms`); `run` and `compare` plan every required arm; `describe` /
`diagnose` plan the base arm.

**3. Experiments carry their arm.** `BuildScenarioStep`, `ReusedExperiment` and `Experiment` gain `arm:
str`, the label of the arm they realise. Within a plan every arm is realised once. The Expert and the
Composer compute each contrast as the difference between the experiments of its two arms, so a `Change`
always has a known reference. A contrast is a pair of arms, not a field of one experiment, because one arm
can be on either side of several contrasts (the combined arm against the base *and* against the
topology-only arm). `role` stays for now; with contrasts it becomes derivable and may be dropped later.

**4. An added edge carries its id.** `AddEdge.edge_id: str | None`. When given, the plain-XML editor uses it
verbatim, so an intervention in the same arm can target it. An arm rejects interventions that target an
edge its own changes remove (`RemoveEdge`), or a lane its own `SetLanes` leaves out. Whether a target
exists in the network is still checked by the Scenario Builder's promotion (`StepError(user_input)`).

**5. The free-mode loop may ask for arms.** `proposed_experiment` is a `Question`, so it may carry arms and
contrasts. The Expert reuses the original question's label when it proposes one of its arms, so the
experiments of later phases satisfy the original contrasts; a new combination gets a new label.

## Consequences

- Domain (E5.12, done with this ADR): `Arm`, `Contrast`, `BASE_ARM`, `Question.arms` / `contrasts` /
  `effective_arms` / `effective_contrasts`, `required_arms` / `reference_arms`, `AddEdge.edge_id`, `arm` on
  `BuildScenarioStep`, `ReusedExperiment` and `Experiment`; schemas and class diagram regenerated.
- E5.1: the Input Parser emits arms and contrasts when a question has more than one treatment, the
  shorthand otherwise. E3.4: the request bank gains combined and multi-arm requests with gold arms,
  contrasts and plans.
- E5.2 / E5.10: the Coordinator plans per arm; the Executor validates arm coverage and shares derivations.
- E5.3: this makes ADR-0023's open point concrete — the Expert gets results on several networks when arms
  differ in topology. E5.4: the Composer's experiment table and claims are organised by contrast.
- ADR-0026: the predicted `scenario_id` of an unsimulated arm is computable only for arms without
  `topology_changes`; the rule of skipping it otherwise stands.
- E5.13 (acceptance): the direction rule above is enforced in `Question.effective_contrasts`, so the
  Parser's prompt rule ("a combination compared with one of its parts has that part as reference")
  is no longer load-bearing. Evidence that it was needed: in the first blind annotation of held-out,
  the user wrote two of three multi-arm contrasts backwards (R022 `base` vs `new_edge`; R023
  `new_edge` vs `edge_and_close`), and both still scored as correct arm structure. The Parser scoring
  is unchanged: once nested pairs are oriented, comparing contrasts as unordered pairs is the same as
  comparing them ordered, and the bank's only non-nested contrasts are alternatives in `compare`
  requests (R021, R065), where the order means nothing. Re-scoring the stored runs changed no score.
- Not yet decided: whether the Expert may answer about contrasts the user did not ask for; whether `role`
  is dropped; cross-phase label consistency is a convention for the Expert, not a domain invariant, until
  E5.3 shows whether it needs enforcing; whether a `counterfactual` between two arms that are not
  nested ("what would A do instead of B") should keep the user's order or ask, decided in E5.2 if the
  plan bank (E3.7) has such a request.

## Alternatives considered

- **Plan the full factorial of topology variants × intervention sets.** Rejected: simulations the question
  does not need, and the cost grows multiplicatively.
- **Let the Coordinator choose the combinations from the flat lists.** Rejected: the combinations are
  what the user asked, not a planning decision; gold plans would depend on the model's taste.
- **Replace the flat fields with arms everywhere.** Rejected for now: every single-treatment question
  would pay the extra structure, the question bank would need rebuilding, and the Parser's field-level
  metrics (§4.1) would change meaning.
- **`Experiment.compared_to` instead of contrasts.** Rejected: one experiment can be on either side of
  several contrasts; a single reference field cannot express that.
- **Contrast direction as a convention of the Parser's prompt** (the rule before E5.13). Rejected: a
  backwards contrast plans the wrong arm and the scoring did not see it; an invariant the
  application relies on belongs in the type, not the prompt.
- **Reject a backwards contrast at validation.** Rejected: the direction of a nested pair is fully
  determined by its content, so correcting it loses nothing, while rejecting it would spend the
  Parser's only retry on a question that was already clear.
- **A late-bound reference to the added edge (`NewEdgeRef(change_index)`).** Rejected: plain XML needs an
  edge id anyway; fixing it in the question is simpler and needs no resolution step.
