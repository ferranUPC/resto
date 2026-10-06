# Coding standards

Read by the reviewer (the Standards axis of `code-review`), not by implementers. Status: draft, for the
maintainer to accept or edit.

Only judgement rules live here. What a tool can decide is enforced by a tool and does not appear in this
file: `ruff` (lint and format), `mypy`, `tests/unit/test_import_boundaries.py` (layer direction, `eval/`
versus `resto`, absolute `resto.*` imports of private names across modules) and the network guard in `conftest.py`. Architecture
rules live in `CLAUDE.md`. Each entry below gives the rule, the reason and one case from this repo.

## Duplication

**One implementation per helper.** Before adding a formatter, loader or step builder, grep for an existing
one and share it. One copy of similar code is a smell to weigh case by case; the third copy of the same
logic is where it must be factored out. Reason: copies drift, and a fix lands in one of them only.
Case: three copies of the same formatter across paid-run modules, found in review (refactor-paid-runs/04);
plan-step builders moved to `tests/unit/domain/_fixtures.py` (refactor-executor/04).

## Shared state

**A shared mutable client or resource is built per worker thread, never shared.** Reason: sumolib queries
and SUMO environments hold state that is not thread-safe, and the failure shows up only under load.
Case: one `SumolibNetworkQuery` was shared across `--workers`; fixed with a per-thread factory and a
Barrier test (refactor-paid-runs/04).

**No temporal coupling through `assert` on instance state.** Do not set `self.x` in one method and
`assert self.x` in another to say "this ran first". Pass the value, or split the object. Reason: the
order is invisible to the reader and to mypy. Case: `self.ledger` set in one executor method and read in
another (refactor-executor spec Findings).

## Design of seams

**Prefer pure, locally testable seams.** Validation is a pure function that returns problems, not logic
that needs a whole `World` of fakes to exercise. A function that always raises returns `NoReturn`, not
`raise AssertionError("unreachable")` at the call site. Reason: the cheap test is the one that gets
written. Case: `plan_problems` in the executor; `_fail` typed `NoReturn` (refactor-executor spec Findings).

## Truthful text

**Docstrings, comments and error messages must not claim a state that is not true.** Check them against
the code and against any rule they cite. Reason: stale prose is read as fact by the next agent. Case: a
module docstring called benchmarks "already migrated" when they were not; a gate message left out a
clause of the CLAUDE.md rule it cited (refactor-paid-runs/03).

## Ports and persistence

**Every divergence between two implementations of one port gets a shared contract test run against both.**
Add the case to `conformance/`, not to one backend's own test file. Reason: a rule tested on one backend
is a rule the other can silently break. Case: the conflict rule of the in-memory repositories had no
counterpart test next to SQLite (r2-database-backends/01, unplanned/02).

**Compare stored values by parsed value, not by text, when the serialization is unordered.** Reason:
`frozenset` JSON order follows `PYTHONHASHSEED`, so equal values can differ as text. Case: the SQLite
`ConflictError` bug found in review (e3-11/01); the two-process `PYTHONHASHSEED` test covers that one case,
not the general rule.
