# ADR-0031: Only `ok` `SimulationResult`s are persisted; a failed attempt lives in the trace

- Status: Accepted
- Date: 2026-09-28
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3
  (identity policy), §2.4; `DATABASE_MCP_CONTRACT.md` §3, §5.4 (amended by this ADR);
  [ADR-0017](0017-runner-configuration-and-kpi-derivation.md)

## Context

`result_id = hash(scenario_id, seed, mode, sumo_version)` (§2.3): it names a request, computed
before SUMO runs. `run_simulation` reused an existing result only when its status was `ok`, so a
`failed` result was re-run on the next call — the Executor's `_existing_ok` already treated a
stored `failed` row as missing. `SqliteResultRepository.store` and `InMemoryResultRepository.store`
disagreed about what a second `store` under the same id, with different content, means:
`_idempotent_store` (§3) raised `ConflictError`, matching the contract's rule that different
content under a hash-derived id is a broken hash or a corrupted store; the in-memory repository
overwrote in place, so only the SQLite path — the one the CLI actually wires — hit the crash. Two
honest runs also disagree in `wall_clock_s` alone, so even a `failed` → `failed` retry conflicted.

The root cause is a mismatch between what the id names and what the record holds: `result_id`
identifies a request, `SimulationResult` describes the outcome of one attempt at it, and §3 assumes
everything stored under a request-shaped id is deterministic. A `failed` outcome is not — the same
request can fail once and succeed the next time SUMO runs it — so it does not belong under §3's
umbrella at all.

## Decision

1. **`result_id` names the simulation** (scenario, seed, mode, sumo_version), not one attempt at
   it. One row per id in the results store; attempt history, if wanted, is a trace concern.
2. **Only an `ok` result is stored.** `run_simulation` returns a `failed` `SimulationResult` to its
   caller — the entity still carries `status`/`error` (DoD §2.3: "failed ⇒ error non-empty") — but
   never calls `results.store` on it. The Executor reports the failure through the `StepRecord`,
   the trace, and the attempt's own logs; the Network Expert and every other reader already filter
   on `ok` (`_existing_ok`, the Expert's result lookups), so nothing needed a stored `failed` row.
   `DATABASE_MCP_CONTRACT.md` §3 keeps its general rule; §5.4 gains one line naming this a caller
   obligation, not a check a store performs.
3. **A staging directory per attempt, promoted to the canonical path on success.** SUMO writes to
   `<out_dir>/<result_id>.<attempt>/`, where `attempt` is the caller's own label (the Executor's
   `study_id`; `eval/scenario_matrix` and `eval/question_bank` use their own row id). On `ok`, that
   directory is renamed to `<out_dir>/<result_id>/` — replacing a leftover directory with no
   matching store row, the trace of a crash between an earlier rename and its `store` — and the
   result's artifacts are re-pointed there before `store`. On failure, the attempt directory is
   left in place: its logs are the record of that attempt, keyed by whoever asked for it.
4. **The in-memory repository matches SQLite's conflict rule.** `InMemoryResultRepository.store`
   raises `ConflictError` on an existing id with different content, the same as
   `SqliteResultRepository`. The other in-memory repositories were checked against their SQLite
   counterparts for the same divergence and brought in line (`Network`'s `label` exemption
   included); `Study` is excluded on purpose — it is a mutable, UUID-keyed, framework-only
   aggregate (§2.3), not one of the four hash-derived ids §3 governs.

## Consequences

- A study that fails a seed and is re-run (a new `Study`, so a new `study_id`) now succeeds at
  `store` instead of crashing after SUMO has already run.
- `run_simulation` takes a new required `attempt: str` keyword argument. Every caller (the
  Executor, `eval/scenario_matrix/build.py`, `eval/question_bank/build.py`, and the unit tests)
  passes one explicitly.
- A failed attempt's directory is never cleaned up by `run_simulation` itself; nothing in this
  ADR adds a retention policy for it.
- `test_a_failed_run_is_stored_with_sumos_message_and_rerun_next_time` is renamed and rewritten:
  the failed run is returned but not stored, the retry stores the `ok` one, and the failed
  attempt's own directory survives the retry untouched.

## Alternatives considered

- **Allow an `ok` to replace a `failed` under the same id, as a `Network.label`-style exception.**
  Rejected: it needs the same exception written into the contract, the SQLite adapter, and the
  DatabaseMCP server, for a case with only one direction (never the reverse) and no reader that
  needs the `failed` row visible in between. Simpler to never store it.
- **Keep overwriting in the in-memory repository, conflict-check only SQLite.** Rejected: it is the
  same bug this ticket started from — a test double that disagrees with the reference backend
  passes tests the real deployment fails.
- **Version `result_id` by attempt (`result_id.1`, `result_id.2`, …).** Rejected: it turns a
  request-shaped id into an attempt-shaped one, breaking "zero redundant simulations" — the whole
  point of hashing the request is that a repeat of it looks up the same row.
