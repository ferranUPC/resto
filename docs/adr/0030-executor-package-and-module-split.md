# ADR-0030: The Executor lives in `application/executor/`, one module per stage of the study flow

- Status: Accepted
- Date: 2026-09-28
- Architecture reference: [ADR-0023](0023-coordinator-split-deterministic-executor.md),
  [ADR-0025](0025-executor-plan-shape-intent-rules-and-failures.md),
  [ADR-0026](0026-expert-notes-per-study-and-prediction-verification.md),
  [ADR-0027](0027-experiment-arms-and-contrasts.md); `docs/study-flows.md` (pending regeneration) §2-§3

## Context

ADR-0023 names the Executor "`run_study`". Until this refactor the Executor was a private class inside
`application/use_cases/run_study.py`, about 700 of the module's 980 lines. That one class planned,
validated plans, ran steps, kept the experiment bookkeeping, counted the study's spend, classified
failures, stored and traced the `Study`, asked the Expert and closed the study. Its mutable state was
spread across the object, and the Expert round wrote the evidence ledger that the note writer read
later behind an `assert`. Nothing in the tree showed that the Executor existed, and an ADR rule such as
the ADR-0025 §3 failure table could not be read in one place.

## Decision

1. **Location.** The Executor is the package `application/executor/`, next to `use_cases/`, `tools/`
   and `ports/`. `run_study` stays the public use case (since refactor r5 it also takes a `StudySettings`): it calls the Input
   Parser, raises `ParserFailed` when there is no `Question` (so no `Study` exists), applies the user's
   `mode` and calls the Executor.
2. **Entry point.** The Executor is a function, `execute_study(question, parse_usage, deps, settings,
   *, max_rounds) -> Study`, not a class. It holds the phase loop and nothing else. It creates the two
   stateful objects (`StudyRecorder`, `StudySpend`) and owns two locals: the study's network id and the
   last evidence ledger. It passes them explicitly to each phase function, so the coupling between the
   Expert round and the note writer is visible in `write_notes`' signature.
3. **Module split.** Each module has one job:

   | Module | Job |
   |---|---|
   | `__init__` | re-exports `execute_study` and the dependency types |
   | `deps` | `StudyAgents`, `StudyPromotions`, `StudyDeps`, `StudyBudget`, `StudySettings` (the composition root's contract) |
   | `executor` | the phase loop |
   | `failures` | the ADR-0025 §3 classification: `StepFailed`, `fail() -> NoReturn`, `draft_of`, `promote`, `crash` |
   | `recorder` | `StudyRecorder`, the only writer of the `Study`: builds each state with `replace`, stores it, traces it |
   | `spend` | `StudySpend`: tokens, agent calls and simulations, checked against `StudyBudget` before spending |
   | `planning` | one phase's Coordinator call and its `ClarificationRequest` |
   | `plan_validation` | `plan_problems(...) -> list[str]`, tested directly against in-memory repositories |
   | `steps` | `execute_plan`: `FromStep` resolution, one handler per step kind, the experiment bookkeeping |
   | `expert_round` | `ask_expert_round -> (ExpertRound, EvidenceLedger)`, the forced last round |
   | `closing` | `write_notes`, `allow_list`, `compose` |

   Step dispatch is a `match` over the closed `PlanStep` union ending in `assert_never`, so a new step
   kind without a handler fails `mypy`. We rejected a handler registry because it loses that check.
   `mode_for` and `needed_arms` moved to `domain/services/experiment_design.py`, next to the other
   arm rules.
4. **`StudyPromotions` is temporary.** It is the seam for the promotions the Executor cannot call
   directly yet (network, demand, reroute, report). It is not a port. It goes away when E5.4, E6.1
   and E6.2 land and the step handlers call those use cases directly, as they already do with
   `build_scenario`. Each promotion is called from exactly one handler.

## Consequences

- ADR-0023 is not edited. Where it and `docs/study-flows.md` say "Executor (`run_study`)", read
  `application/executor/`, entered through `run_study`. `docs/study-flows.md`, once regenerated, points to the package.
- Behaviour did not change: messages, error kinds, trace events, stored states, the order of checks
  and the budget arithmetic are the same. The end-to-end `run_study` suite changed only its imports
  and the invalid-plan cases, which moved to `test_plan_validation.py`. Failure classification has its
  own test file.
- The experiment bookkeeping stays keyed by build-step index. Two build steps in one plan can produce
  the same `scenario_id`, so a key by scenario id would merge them.
- Follow-ups: E5.3 (one network per `ExpertTask`), which touches only `expert_round`. The
  `StudySettings` follow-up (refactor r5) is done: `budget`, `has_historical_demand` and `out_dir` live
  in `StudySettings`, passed beside `StudyDeps` to `run_study` and `execute_study`.
