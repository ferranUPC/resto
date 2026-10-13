# ADR-0041: The Study owns its lifecycle; its transitions return domain events

- Status: Accepted (2026-10-13, refactor r23). Supersedes
  [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md) §3 where it says that no valid `Question`
  means no `Study`, and the `StudyStatus` of [ADR-0023](0023-coordinator-split-deterministic-executor.md)
  §4. Amends [ADR-0030](0030-executor-package-and-module-split.md) decisions 1 and 2 and
  [ADR-0040](0040-use-cases-are-classes.md) (the Input Parser runs inside the Executor), and
  [ADR-0026](0026-expert-notes-per-study-and-prediction-verification.md) (when a note is verified). None of
  them is edited
- Date: 2026-10-13
- Architecture reference: ADR-0023, ADR-0025, ADR-0026, ADR-0030, ADR-0040; architecture review
  `docs/private/architecture-review/20261013.html` (candidates A and B); work-plan §7 row r23

## Context

The `Study` checks every state in `__post_init__` (twelve invariants) but has no transition. Each change is
built in the application layer with `dataclasses.replace`: `StudyRecorder` builds the failed, needs-user,
planned and completed states, `steps.py` decides which experiment a run's results join, `planning.py` derives
the arms earlier phases realised, `expert_round.py` computes the round number and `forced_by_limit`, and
`executor.py` decides whether the Expert's answer opens a new phase. Every lifecycle rule is therefore written
twice: once as an invariant in the domain and once as a construction in the Executor. Six application modules
make transitions, and the loop drifted: `open_phase` does not change the status, so phase 1 is planned while
the study reads `running`, and `planning` only ever appears in phase 0.

`ExpertNote` has the same shape. The rule that confirms or refutes a note against a result lives in the use
case `UpdateNoteStatus`; the entity only has `with_status`.

The Input Parser is the only agent called outside the Executor. `RunStudy` parses and the Executor receives
`parse_usage` so that `StudyRecorder` and `StudySpend` can account for a call they did not make. The flow has
two entry points (`RunStudy.execute` and `execute_study`), and tests enter through both.

`StudyRecorder` builds each state, stores it and emits trace events in the same method, so the trace knows
what happened only because the code that built the state also traces it.

## Decision

**1. The use case orchestrates; the domain decides.** Every decision about a study's state is taken by the
domain. When a decision needs data from outside (stored results, stored scenarios), the use case loads the
data, the domain decides with it, and the use case acts. The application keeps translating what happened
outside into facts the domain understands (`failures.py`) and the technical choices (directories, retries,
trace format).

**2. A study starts at the request.** It is created when the request (text and `mode`) is accepted, with no
phases. Parsing is its first stage: the Parser's `Question` opens phase 0, and the Question keeps living in
`phases[0].question`. A Parser failure is a `failed` study at stage `parsing`, stored and traced like any
other; `ParserFailed` is removed. The Parser's ambiguities leave the study `awaiting_user` at stage
`parsing`. The Parser's call is the study's `parse` step, a `StepRecord` kept outside the phases
(`Study.parse`): ok once its Question opened phase 0, failed when the study failed at `parsing`, absent while
the study is parsing. A study is still failed if and only if a step failed, the `parse` step included, and
the Parser's usage counts in the **Study cost** like any other step's.

**3. Stage and resolution replace the status.** Two stored attributes:

| Attribute | Values | Meaning |
|---|---|---|
| `StudyStage` | `parsing`, `planning`, `running`, `consulting_expert`, `closing` | where the study is, or where it stopped |
| `StudyResolution` | `completed`, `failed`, `awaiting_user`; `None` while open | how it ended |

Only the study's transitions write them, and an invariant checks that they agree with the shape of the
phases. A failed study keeps the stage it failed in.

**4. The study exposes its transitions and the questions about its state.** Opening, accepting a plan,
recording a step (ok, failed, needs user), recording an Expert round, opening the next phase, recording notes
and completing are transitions that return the next `Study`. The rules on its own data move with them: which
experiment a run's results join, the arms earlier phases realised, the study's result ids, adding networks
without repeats, the next round's number and whether it is forced. Callers ask the study; they do not inspect
its fields.

**5. The Executor's loop.** The study says what comes next (`next_action`), the application performs it
(agents, promotions, SUMO, the budget, failure classification), and the study applies the outcome. The loop
holds no rule about the study's state. Dispatch on the next action is a `match` over a closed union ending in
`assert_never`, as for plan steps (ADR-0030 §3).

**6. Reuse rules are domain decisions.** Which seeds still need a run, reusing a stored scenario with ok
results without calling the Scenario Builder, and accepting a specialist's `Found` only when it names a stored
artifact are decided in the domain over data the Executor loads.

**7. The Input Parser is the Executor's first stage.** It is called like every other agent, through the
study's spend, and `parse_usage` leaves the Executor's interface. `RunStudy.execute(text, *, mode)` stays the
public use case (ADR-0040).

**8. Cost is a fact; the budget is a policy.** Each `StepRecord` keeps its `usage`, so a study knows what it
cost (**Study cost**). The cap on what a study may spend stays in the application (`StudySpend`); the study
only learns that a step failed with `StepError(budget)`.

**9. `ExpertNote` verifies itself.** Given a result, the note returns its next value and the event of its
status change. `UpdateNoteStatus` loads, delegates and stores.

**10. Domain events.** Each transition of `Study` and `ExpertNote` returns the domain events it produced. The
event types live in `domain/`. The use case stores the new value first, since storing is the application's
decision and not a reaction, and then publishes the events.

**11. A synchronous, in-process event bus** in `application/` carries domain events only. Handlers run in
order before `publish` returns. A handler that fails never changes a study's outcome: the bus reports the
failure as telemetry and goes on. Two handlers subscribe: the trace, and note verification, which leaves the
simulation step. Notes are verified when the study records the step's results, after every seed of the step
has run, instead of seed by seed.

**12. Telemetry is not an event.** `ModelCall`, `NoteWriterFailed` and the bus's handler failures are
operational facts, not changes to any aggregate. They go straight to the `Tracer` port. The tracer therefore
has two entries with one meaning each: a bus subscriber for domain events and a port for telemetry.
`StudyRecorder` is left with storing and publishing.

## Consequences

- `Study.json` is regenerated; `render.py` and the CLI read stage and resolution. A Parser failure is now
  rendered as a failed study instead of an error message.
- Lifecycle rules are tested in `tests/unit/domain/test_study.py` without agents or repositories. The
  end-to-end `run_study` suite stays as the safety net during the refactor; the cases that only repeat a
  rule the domain tests cover are removed at the end.
- Trace events keep their names where they still apply; `TraceEvent` types that are domain events move to
  `domain/`.
- Not decided here and recorded for later (`docs/private/architecture-review/reflexiones.md`): the ADR-0025
  §3 failure table as a domain rule, and resuming or linking studies (E11.2). A rerun is still a new study.

## Alternatives considered

- **Keep the study born with its `Question` (ADR-0025 §3).** Rejected: the study is the unit stored and
  traced from the moment a request is accepted, and a failed parse is worth auditing like any failed step.
- **Derive the stage from the phases instead of storing it.** Rejected: the maintainer wants the lifecycle
  readable on the stored study. Storing is safe because only the study's transitions write it and an
  invariant checks it.
- **The study only exposes transitions and the Executor keeps the loop's order.** Rejected: the order is
  the ADR-0023 §3 and ADR-0025 §4 rules, which are domain decisions.
- **The recorder derives events by comparing two studies, or the Executor emits them.** Rejected: the
  transition is what knows what happened.
- **Events returned without a bus.** Considered first; the bus was chosen because note verification is a
  second listener.
- **An asynchronous bus.** Rejected: the order of traces and verifications would depend on the scheduler,
  and a study must replay deterministically (ADR-0023).
- **The study's budget as a domain rule.** Rejected: a spending cap is an operational limit, not part of
  what a study is.
