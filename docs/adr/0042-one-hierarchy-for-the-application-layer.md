# ADR-0042: One hierarchy for the application layer: one package per use case, stages, step executors, promoters and event handlers

- Status: Accepted (2026-10-13, refactor r24). Amends [ADR-0030](0030-executor-package-and-module-split.md)
  decisions 1 to 3, [ADR-0040](0040-use-cases-are-classes.md) (what a use case is, the Executor's phase
  functions, `StudyDeps`) and [ADR-0041](0041-study-owns-its-lifecycle.md) §10 to §12 (`StudyRecorder`, the
  event handlers), and the rule of [ADR-0024](0024-expert-notes-typed-claims-and-deterministic-status.md)
  that checks a note's evidence against the final round's `EvidenceLedger`. None of them is edited. Folded
  into the ADR consolidation of 2026-10-16
- Date: 2026-10-13
- Architecture reference: ADR-0001, ADR-0024, ADR-0025, ADR-0026, ADR-0030, ADR-0040, ADR-0041; review
  threads of PR #36 (r21) and PR #37 (r23); work-plan §7 row r24

## Context

The layers should read one way every time: the interface calls one use case, and the use case works with
domain objects and ports. The application layer does not read like that after r21 and r23.

Running a **Study** is one use case spread over three kinds of places. `RunStudy` calls `execute_study`, a
set of functions in `application/executor/`. Those functions call `AskExpert`, `WriteNote`, `ComposeReport`
and `UpdateNoteStatus`, which sit in `use_cases/` but are called only by the study flow. Their names are
business verbs, yet `AskExpert` asks nothing and `WriteNote` writes nothing with a model: each one checks an
agent's answer, turns it into its object (the **Promotion** of a **Draft**, ADR-0001) and stores it. `eval/`
and `scripts/` repeat "call the agent, then promote" by hand.

The phase functions take the whole `StudyDeps` bag next to the study and the budget, so every signature
mixes collaborators with request values. `StudyDeps` nests agents, promotions, repositories and inner use
cases, and `StudySettings` and `max_rounds` travel apart from it.

Adding a plan step means editing four `match` statements: the step union, the dispatch in the Executor,
`Study.record_step` and the plan validator's reference table. The steps module (342 lines) mixes the loop,
error translation, id resolution, reuse rules and six step handlers.

`StudyRecorder` holds the current study as state, stores it and publishes its events, and its constructor
does I/O. The note verification handler receives `bus.publish`, so the bus is wired into one of its own
handlers. Rules about a study's own data (which scenarios the note writer may cite, which network is the
study's base) are computed in `closing.py` over repositories.

The Expert's evidence ledger also leaves the Expert round outside the `Study`: the loop keeps it as a local
so that `WriteNote` can check the notes' citations against every tool call of the final round.

## Decision

**1. A use case is an independent, bounded feature.** It can be called on its own and does one job from
start to end. A piece that only one use case calls is part of that use case and lives with it. A use case
may orchestrate other use cases. The use cases are `RunStudy`, `BuildScenario`, `RunSimulation` and
`ScaleDemand`. `AskExpert`, `WriteNote`, `ComposeReport` and `UpdateNoteStatus` are not use cases and go.
ADR-0040's shape (class named by the verb, collaborators in the constructor, one `execute` taking request
values) still holds for every use case.

**2. One package per use case that has parts.** `application/executor/` becomes `application/run_study/`:
`RunStudy`, whose `execute` is the study loop, a `stages` subpackage, a `steps` subpackage and the modules
only it uses (spend, failure translation, plan validation). `execute_study` stops existing. The use cases
that stand alone stay in `application/use_cases/`, and the ADR-0040 structural test checks only that
package. How `run_study` splits further, if it grows, is decided then.

**3. Stages.** Parse, plan, Expert round, notes and compose are classes. Collaborators and process-level
settings go in the constructor. One `execute(study, spend)` returns a `Transition`. A stage decides what
happened and stores nothing; the one exception is the notes stage, which stores the notes, since notes are
an aggregate of their own and not part of the study. Every stage has the same shape.

**4. One transition per action.** `Study.next_action` returns one action per plan step (`RunStep`, carrying
the step) in place of `RunPlan`. The study resolves `FromStep` references from the step records it holds,
so the application keeps no map of produced ids. The study is a local variable of the loop. `RunStudy`
stores the new study when it changed and then publishes the transition's events: two visible lines.
`StudyRecorder` is removed, and the helper that dumps a value for a `StepRecord` moves to a module of its
own.

**5. Promoters.** A promoter takes an agent run and the context the agent was given and returns the
promoted object, or raises `DraftRejected`. It reads and stores nothing. The stage, step executor or use
case that called the agent loads what the promoter needs and stores what it returns. Promoter names end in
`Promoter` and have one public method, `promote`: `ExpertAnswerPromoter`, `NotePromoter`, `ReportPromoter`,
the Scenario Builder's promoter that `BuildScenario` uses, and promoters for the network, demand and
reroute promotions that `StudyPromotions` carries today. They live in `application/promoters/`, outside
`run_study`, so `BuildScenario` and `eval/` import them without the study flow. Only the promotion part of
today's classes is extracted: `BuildScenario` keeps its SUMO load check, which runs a process.

**6. Plan step variants carry their own rules.** Each `PlanStep` variant has `refs()`, the ids it names
directly, and `apply(phase, record, reused)`, its effect on the phase. `Study.record_step` and the plan
validator stop matching on step types. `Experiment` stores the index of the plan step that built it.
`Study.record_step` also adds the network ids a step produced.

**7. Step executors.** One class per plan step type, each in its own module of `run_study/steps/`, with its
collaborator in the constructor and `execute(step, ctx)`. Every executor takes the same `StepContext`. The
composition root builds a registry from step type to executor and gives it to `RunStudy`. A coverage test
fails when a `PlanStep` variant has no executor in the registry, which replaces the `mypy` check that
ADR-0030 §3 kept the `match` for. A shared helper for the "agent, needs user, found, promote" sequence of
`obtain_network` and `obtain_demand` is added only when a third case needs it. Adding a plan step means
writing the step, writing its executor and registering it once.

**8. Rules about the study's own data are domain rules.** Given the final round and the scenarios and
networks the notes stage loaded, the `Study` answers the note writer's task: the allow-list (every scenario
of the study, plus the predicted id of each unrealised arm that keeps the topology, ADR-0026) and the base
network (the study's network not derived from another). Reusing a stored scenario with ok results is
decided by the domain reuse service over what the executor loaded.

**9. Notes stay at closing and are not a plan step.** Closing is two stages: notes, then compose. Every
study that reaches closing tries to write notes. A note writer failure is telemetry (`NoteWriterFailed`) and
never fails the study, so a study is failed if and only if a step failed. Notes are not a step for two
reasons. They are written once, after the final Expert round, when the plan of every phase has already
run, so no plan could hold them. And a step's failure fails the study (ADR-0023, ADR-0041 §2), while a note
writer's failure must not (ADR-0026): notes are knowledge for later questions, not part of this answer.
Making them a step would need a step kind whose failure does not count, an exception to the rule that keeps
a study's resolution mechanical. No `StudyClosed` event is added until a third subscriber needs it.

**10. A note cites only what the final answer cited.** A note's evidence must be in the final Expert
answer's evidence (`final.answer.evidence`). Before, it had to match any tool call of the final round's
`EvidenceLedger` (ADR-0024). The note writer sees only the answer's evidence and has no tools, so the rule
matches what its prompt already asks. It also removes the only value that crossed from the Expert round to
closing outside the `Study`, so the notes stage keeps the `execute(study, spend)` shape. `NotePromoter`
takes no ledger.

**11. Event handlers.** `application/event_handlers/` holds the trace handler and the note verification
handler. An `EventHandler` protocol has `name` and `__call__`, and a call returns the events the handler
produced. The bus keeps only the mechanism: it subscribes handlers by event type, queues the events they
return and documents the handler order, with the trace first. No handler holds a reference to the bus.
Note verification is one handler that loads each unverified note, asks it to verify itself, stores it and
returns the `NoteStatusChanged` events; it absorbs `UpdateNoteStatus`. `NoteStatusChanged` gains
`study_id`.

**12. Spend.** `StudySpend` takes the budget, the tracer and the study id and emits `ModelCall` itself, so
the loop has no callback that only binds the tracer and the study id.

**13. Steps run in plan order.** The assumption is written where the pending steps are computed, with a
`TODO(dag)` where the next and skipped steps are chosen.

**14. No dependency bags.** `StudyDeps`, `StudySettings`, `StudyAgents` and `StudyPromotions` are removed.
`interface/dependencies.py` builds every use case, stage, step executor, promoter and handler. Each setting
goes to the constructor of whoever reads it, and `max_rounds` and the study budget to `RunStudy`'s.
ADR-0040's rules on the composition root (decision 3 to 5) and on callers outside `interface/` hold.

## Consequences

- ADR-0030 keeps its text. Where it says `application/executor/`, `execute_study`, the module table,
  `StudyRecorder`, the step `match` or `StudyPromotions`, read decisions 2 to 7 and 14 of this ADR.
- ADR-0040 keeps its text. Its list of use case names (decision 2) and its `StudyDeps` wiring (decision 3)
  are replaced by decisions 1 and 14; its consequence that the phase functions stay functions is replaced by
  decision 3.
- ADR-0041 keeps its text. §10's "the use case stores, then publishes" is `RunStudy` itself, with no
  recorder; §11's note verification is the handler of decision 11; §12's last sentence about
  `StudyRecorder` no longer applies.
- ADR-0024 keeps its text. Where it says `write_note` checks a note's evidence against the round's
  `EvidenceLedger`, read decision 10: a note that cites a tool call the final answer did not cite is now
  rejected. The note-writing call still has no tools.
- Behaviour does not change for the CLI user: messages, exit codes, error kinds, stored studies and budget
  arithmetic stay as they are. The trace changes on purpose in two places: `NoteStatusChanged` carries
  `study_id`, and the handler order is the documented one.
- The `World` suite over `RunStudy.execute` stays the safety net. Tests that entered the Executor through
  internal functions move to that seam. Promoters are tested with an agent run and a context and no
  repository; rules moved to the domain are tested on `Study` and the reuse service.
- The import boundary test learns the new packages: a promoter that imports a repository port or
  `run_study`, or an event handler that imports `run_study`, fails the build.
- E6.1 and E7.1 add their agents, promoters and steps in this shape.

## Alternatives considered

- **Keep the inner classes as use cases.** Rejected: "use case" would then mean "any class with
  `execute`", and the word would not say whether a piece can be called on its own.
- **Keep the Executor's phase functions with a smaller bag.** Rejected: any bag mixes collaborators with
  request values in the same signature, which is what ADR-0040 removed from use cases.
- **Keep the `match` over step types (ADR-0030 §3).** Rejected: it made a new step edit four places. A
  registry plus a coverage test catches a missing executor before a model calls it, and the step's own
  `refs()` and `apply()` remove the other three `match`es.
- **Notes as a plan step.** Rejected, see decision 9.
- **Keep checking note citations against the ledger.** Rejected: the note writer cannot see the ledger,
  and carrying it to closing would give the notes stage a second input outside the `Study`.
- **Promoters that store what they promote.** Rejected: storing is I/O and belongs where the agent was
  called; a pure promoter is tested without a repository and reused by `eval/`.
- **Handlers that publish through an injected bus.** Rejected: the bus would be wired into its own
  handlers. Returned events keep the order in one place, the bus.
- **A `StudyClosed` event for notes.** Rejected for now: notes are one stage of closing, and an event
  earns its place with a third subscriber.
