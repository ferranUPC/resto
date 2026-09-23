# ADR-0026: Expert notes — written once per study, about the network, and predictions made verifiable

- Status: Accepted — extends ADR-0024 (when notes are written, how `provenance` and `scenario_id` are set)
- Date: 2026-09-23
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3
  (`ExpertNote`), §2.4 (Network Expert), §4.7; [ADR-0011](0011-network-expert-knowledge-model.md),
  [ADR-0023](0023-coordinator-split-deterministic-executor.md), [ADR-0024](0024-expert-notes-typed-claims-and-deterministic-status.md),
  [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md);
  [`evaluating-resto.md`](../evaluating-resto.md) §4.8; work-plan E4.6, E4.9, E4.11, E5.10

## Context

A note is not the study's conclusion — that is the `Report`. A note is the Expert's reusable
interpretation *about a network* (`search_notes` is scoped by `network_id`), retrieved in later
questions; `study_id` only records where it came from. ADR-0024 left "calling `write_note` /
`update_note_status` at the right moment of a `Study`" to the Executor. Deciding that moment exposed two
problems in how notes are tied to scenarios:

- **Predictions can never be verified.** A forced counterfactual ("close lane 1 of E12 at peak") answers
  `extrapolated`, e.g. `mean_delay ≈ 95 s`, without simulating. `write_note` stores it as `opinion` with
  `scenario_id = None`, because it sets a scenario only when something was simulated. When a later study
  simulates exactly that scenario (130 s), `update_note_status` requires `note.scenario_id ==
  result.scenario_id` and does nothing: the note stays `unverified` forever. These are precisely the notes
  worth verifying — §4.7's knowledge hygiene ("status updated after the corresponding simulation in 100 %
  of cases") and ADR-0011's point that the learning effect measures verified knowledge, not accumulated
  confidence.
- **Simulation notes would be "verified" by their own data.** A note written after simulating S12 with
  seeds 1–3 carries `scenario_id = S12`. When another study needs S12, `run_simulation` returns the stored
  result (same `result_id`); checking the note against it would confirm it with the data it came from.
- **One note per study is too narrow.** A note is verified against one scenario, but a GP-11 or compare
  study learns about several.

## Decision

- **When.** One note-writing call per `completed` study, after the final Expert round and before
  `compose_report`. In free mode every earlier round is an abstention (`needs_simulation`), with nothing
  to remember; with ADR-0025 the final round always answers. No notes for `failed` or `awaiting_user`.
  A failing note writer (no draft, or `write_note` rejects it) does not fail the study — notes are
  knowledge for later questions, not part of this answer: it goes to the trace, not to a `StepRecord`,
  so ADR-0023's mechanical closing status is unchanged.
- **What.** The call (no tools, as in ADR-0024) returns `ExpertNoteDrafts`: 0 to `MAX_NOTES_PER_STUDY`
  (3) `ExpertNoteDraft`s. Zero is valid (nothing new, e.g. a describe over results that already have
  notes). Each draft is about one thing: one scenario, or the network in general.
- **Which scenario.** Each draft carries `scenario_ref: str | None`, chosen from an allow-list the Executor
  puts in the input: every scenario of the study's `Experiment`s, plus — when the final answer is about an
  intervention that was *not* simulated — its **predicted** `scenario_id`, computed as
  `scenario_id_for(network_id, baseline demand_id, question.interventions, question.context_tags)`. The
  agent references a scenario, it never makes one up: `write_note` rejects a ref outside the allow-list
  (the same pattern as evidence refs, ADR-0018).
- **Provenance.** `write_note` sets `provenance = simulation` only if that scenario has ok results in the
  study; otherwise `opinion`, with `scenario_id` still set when it is a prediction. The domain already
  allows it (`ExpertNote` only requires a scenario for `simulation`, not the converse). This replaces
  ADR-0024's "`simulation` when the note is about a scenario".
- **Verification.** The Executor calls `update_note_status` after every **new** ok `SimulationResult`
  (actually run in this study, not reused by `result_id`), for every `unverified` note of that network with
  that `scenario_id`, found through the existing `search_notes` filters (`scenario_id`, `status`). Reused
  results never trigger it. A prediction is thus settled the first time its scenario is simulated; a
  simulation note is re-checked only when new seeds run it.

## Consequences

- A forced prediction on an intervention becomes checkable; §4.7's "100 % of applicable cases" now
  includes predictions, not only network-wide claims on already simulated scenarios.
- Known limits, accepted: the predicted id misses if the Builder later rejects one of the interventions or
  the context tags differ (a different `scenario_id`); topology predictions cannot be pre-hashed (the derived
  network's `content_hash` does not exist yet), so they stay `unverified`.
- Code (E4.11): `ExpertNoteDrafts` container and `scenario_ref` on `ExpertNoteDraft`; note-writer prompt and
  input (allow-list); `write_note` validates the ref and applies the new provenance rule, storing several
  notes. E5.10 builds the allow-list, computes the predicted id and calls `update_note_status` on new
  results only.
- E4.9 (learning effect) measures a store whose notes now carry predicted scenarios; its protocol does not
  change.

## Alternatives considered

- **One note per study.** Rejected: a note is verified against one scenario, and a study can learn about
  several.
- **A note after every round.** Rejected: non-final rounds are abstentions; it pays calls for nothing.
- **A separate `about_scenario_id` field next to `scenario_id`.** Rejected: `scenario_id` plus the new
  provenance rule already says it; the invariant needs no change.
- **Let the agent name any scenario id.** Rejected: an agent must not write identity; an allow-list keeps
  it a reference to known or deterministically computed ids.
- **Verify against reused results too.** Rejected: circular — a note confirmed by the data it was written
  from.
