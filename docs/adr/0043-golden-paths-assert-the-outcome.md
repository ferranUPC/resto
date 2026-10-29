# ADR-0043: Golden paths assert the outcome, not the route

- Status: Accepted (2026-10-14, refactor r20). Replaces the wording of the DoD §5 ("expected `StepRecord`
  traces", "Trace matches expected for 11/11 golden paths") and the **Expected trace** of the glossary. The DoD
  is frozen and is not edited; where it says "trace", read "outcome". Folded into the ADR consolidation of
  2026-10-16
- Date: 2026-10-14
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §5;
  [ADR-0023](0023-coordinator-split-deterministic-executor.md) (phases, `max_rounds`),
  [ADR-0032](0032-expert-network-scope.md), [ADR-0038](0038-no-counterfactual-intent-contrast-decides-the-arms.md)
  §3 and §4, [ADR-0039](0039-deterministic-planner-replaces-the-coordinator.md); review of PR #34 (E9.1)
  and spec `.scratch/r20-golden-path-outcomes/spec.md`

## Context

E9.1 compares, per phase, the exact sequence of (tool, status) and a set of attributes (`arms`, `reused`,
`basis`, `forced_by_limit`, round). With the scripted agents that works, because the Executor decides the
sequence. With a real model it fails runs in which the system did the right thing by another route.

The case that raised it is `gp3`. It expects two phases only because its script makes the parser read "how
would closing lane 1 of E12 look?" as `describe` and makes the Expert abstain. The DoD's GP-3 ("What if I
close lane 1 of E12?") is, after ADR-0038 §3, one phase that plans both arms. A parser that reads the request
as `compare` is right, and `gp3` would still fail. `gp3` also does not test what its name suggests: the
script dictates that the Expert abstains, so it proves the phase loop runs, not that an Expert can ask for
an arm the plan left out.

The state of `golden/` when this was decided: a golden path is a request, a `PriorState` of stored scenarios
and an `ExpectedTrace`; the only entry is `RunStudy.execute(request)`; the agentic setup is a protocol with
no implementation, so no golden path has run against a real model.

The phases are a recovery mechanism, not a goal. A plan that can be foreseen needs one. Which model solves a
request in one round and which in three is a result of the later study of agents (E12), not a failure.

## Decision

**1. A golden path asserts the outcome.** The **Expected trace** is replaced by an **Expected outcome**. The
number of phases, the order of steps and the number of rounds are not asserted. `max_rounds` stays as the
capacity the system has to react, and is not a count to match. The exact trace stops being an assertion of
`golden/`; the checks of orchestration order stay in the tests of `RunStudy` (`tests/unit`), which already
cover them.

**2. An Expected outcome has five parts**, each left empty (not compared) when a golden path does not
constrain it:

- `resolution`: how the study ends.
- `network`: the study's `network_id` equals the expected one, or the network has the expected **Network
  topology** (decision 4).
- `simulations`: the **Essential simulations** and `max_new_simulations` (decision 5).
- `answer`: the KPIs the Expert gives, read from `ExpertAnswer.values` (typed, authoritative over the prose,
  ADR-0019), each as a `Measure`, its scope and a reference value with a relative tolerance; plus `basis` and
  `forced_by_limit` when the golden path fixes them.
- `demand`: the kind of the demand source and a range for its parameters; the `answer` KPIs; and, when counts
  are given, the calibration fidelity thresholds of the DoD (±15 % on DEV-NET, ±25 % on REAL-NET at the
  control edges). Demand files are never compared, since they depend on the seed. What each golden path
  checks is written when E9.8 defines GP-8, GP-10 and GP-11.

GP-9 is `awaiting_user`, zero new simulations and no answer. GP-1 and GP-5 are zero new simulations. GP-4
keeps the base simulation and `basis` as ADR-0038 §4 states.

**3. The reference is a solution by hand.** A golden path is a case that can happen in real life, and its
expected values come from solving it as an engineer would: the corrected network, the demand, the KPIs. The
tolerance is relative and set per KPI in advance: 42, 43 or 44 s are equivalent; 90 s or 10 s are not. Two
runs that differ in a parameter (a demand scaled by 1.4 or by 1.65) both pass when the question's KPI stays
inside the tolerance; one that scales by 3 fails because the KPI leaves it. The KPI is the judge, with the
parameter range as a guard against a result right by accident.

**4. Network equivalence is topology, not bytes.** `network_id` stays the hash of the `.net.xml`
(`Network.__post_init__`): it is the identity of the stored file, and the reuse lookup depends on it. It is
not a test of equivalence, since the same network written with another element order or another generated id
has another hash. Equivalence is decided on a **Network topology**: junctions, edges with lanes and maximum
speeds, lane connections and traffic light programs. The `NetworkTopology` is a value object of the domain
with its own `==`; a SUMO adapter reads a `.net.xml` into it and the golden path comparator uses both. It is
a view built on demand for the two networks being compared, never stored with `Network`, so it costs nothing
to the application. A comparison first checks `network_id`: equal ids need no parsing.

- An edge is identified by its origin junction, its destination junction and its index among parallel edges,
  not by its own id; maximum speed and lane count are attributes compared after matching, so a difference
  reads "edge A to B has 8 m/s, 13 m/s expected". Junction ids are used, since a derived network keeps the ids
  of what it does not touch (ADR-0032) and a network from OSM inherits stable ones.
- Not compared: geometry (`shape`), element order, the ids the generator assigns, the tool's header.
- Limit: the v1 operations of the Network Author (`add_edge` between existing junctions, lane closure,
  speed, traffic light program) never create a junction. An operation that does would need a full graph
  isomorphism. It is left out of v1 and recorded as task E9.9 (5 pts) of the optional package M52, with a
  test that shows the limit.
- Reading a `.net.xml` takes milliseconds: DEV-NET has 304 edges, 61 junctions and 412 connections in 125 KB;
  REAL-NET is planned at 300 to 800 edges.

**5. Simulations: essential ones present, none redundant, an upper bound.** An **Essential simulation** is a
predicate on the scenario (intervention kind and target, demand kind and a range), not a `scenario_id`, so
equivalent parameters satisfy it. `max_new_simulations` counts the simulations that were not `reused`.
"Redundant" is the same `scenario_id` with the same seeds twice in one study. The margin over the essential
ones is zero unless the golden path states a reason in its definition. The bound is the guard the cost policy
needs: without it, a system that ran 20 simulations and included the 2 required would pass.

**6. Pass or fail is binary, and the severity is a field.** Every part of the outcome is a hard failure now,
which is what the DoD's "11/11 on 3 repeated runs" asks. A check carries its severity as data (default
`hard`), so a future decision to report some checks as warnings (an extra simulation inside the bound, a KPI
the Expert did not cite) changes a value and not the comparator.

**7. The two-phase case is a different golden path.** The case of an Expert that asks for an arm the plan did
not have is not GP-3. It tests the Expert in isolation: the agentic setup replaces the planner with one that
returns a plan without that arm (`FakePlanner(*plans)` already does it in the test world), the parser and the
Expert are real, and phase 0 runs for real. The expected outcome is the same as if the plan had been complete:
the missing arm ends up simulated, or the Expert answers with `basis` set and says so. Nothing in it counts
phases. It needs no new `RunStudy` entry and no persisted phase 0; starting a study from a stored phase 0 was
considered and rejected (see below). Which golden path it is called and where it lives is decided when the
tickets are cut.

**8. The setups.** Both setups run the same golden paths against the same outcome. The scripted setup stays,
because the cost policy forbids model calls in CI and it is the only thing that tests the comparator and the
definitions without cost; it is not a goal of the thesis. The agentic setup is what the golden paths exist
for and arrives with E12.1. Decision 1 removes the exact trace from `golden/`, so the scripted setup no longer
needs a script that reproduces a route; its scripts only have to leave the outcome.

**9. The trace is recoverable from every run.** `python -m golden.run` writes, by default, one JSONL file per
golden path and repetition, `golden-traces/<UTC time>/<gp>/<repetition>.jsonl`, with the existing JSONL
tracer (`adapters/tracing/jsonl.py`). `--no-trace` turns it off and `--trace-dir DIR` moves it. If the
file system cannot be written, it warns and the run goes on; a golden path never fails for that. The
directory is git-excluded. The default is on because the files show the decisions a model took when a
golden path passes through a route nobody expected, and a failed run with a paid model should not be repeated
only to see why.

**10. What this changes.** See Consequences. The DoD §5 text is not edited. The previous notion of "expected
trace" is replaced in `GLOSSARY.md`, which now has **Expected outcome**, **Essential simulation** and
**Network topology**.

## Consequences

- r20 rebuilds `golden/`: `ExpectedOutcome` and its comparator replace `ExpectedTrace`, `ExpectedPhase`, the
  phase-wise comparator and `allowed_events` in `golden/framework/`; GP-1 to GP-5 and GP-9 are rewritten as
  outcomes; the trace flag of decision 9 is added. E9.1 is closed and receives nothing. r20 is a pull
  request of its own, independent of PR #34, which is merged.
- `NetworkTopology` is not built in r20. GP-1 to GP-5 and GP-9 do not touch the network, so `network` starts
  as "the same `network_id`". The topology comparison arrives with E9.8 (GP-8 and GP-11), when networks are
  created or derived. The full isomorphism is E9.9, a task of M52.
- E9.2 and E9.8 write their golden paths as outcomes, so both are blocked by r20 (their specs say it). E9.3,
  E9.4 and E9.5 inherit the block through them.
- E9.5: the reproducibility of GP-2 (identical `result_id`s and hashes) is a property between repetitions, not
  of one outcome. It is a check of its own of that golden path and is not part of `ExpectedOutcome`.
- E3.14: the free-text judge is used only where no typed value exists. `ExpertAnswer.values` carries the
  KPIs, so its scope is smaller than the plan assumed.
- E12.1: the agentic setup is implemented against `ExpectedOutcome`, including the planner replacement of
  decision 7, and prints `estimate_cost` before any model call, as the cost policy requires.
- The `docs/tfm-work-plan.md` has the §7 row r20, the new task E9.9 (plan 1071 → 1076 pts, no slack taken),
  the node r20 and its edges in the build DAG (§4.1) and §4.8. The progress tracker is not edited by hand; the next
  review will show E9.1 as done.
- `docs/tfm-architecture-and-dod.md` is not edited. Where the DoD §5 lists "Expected trace" for GP-1 to
  GP-11, read the outcome of decision 2. The GP-3 row ("Expert `needs_simulation` then Coord") was already
  replaced by ADR-0038 §3, and GP-4's "no simulation" by §4.
- A golden path whose reference values come from a SUMO run depends on the pinned version (ADR-0010) and the
  seeds. A change of either regenerates the reference values.

## Alternatives considered

- **Keep the exact trace and compare it in both setups.** Rejected: with a model it fails runs that did the
  right thing another way, and it measures imitation of a script, not quality. The trace is still recorded.
- **Keep both types, `ExpectedTrace` for the scripted setup and `ExpectedOutcome` for the agentic one.**
  Rejected: two expectations per golden path to maintain, and the glossary says a golden path says what must
  happen and never how.
- **Assert only the number of phases as a maximum.** Rejected: `max_rounds` already limits it, and which
  model needs one round or three belongs to the comparison of agents.
- **Start a golden path from a stored phase 0** (a persisted plan and its results, with a new `RunStudy` entry
  to resume). Rejected: a new use case that only evaluation would call, and a stored state to keep valid. The
  planner replacement gives the same isolation of the Expert with the code that exists.
- **Compare networks by the hash of the file, with the header removed.** Rejected: it is true only for the
  same bytes. A different order of elements or different ids give a different hash for the same network, and
  stripping the header by a pattern breaks if SUMO changes it. Canonicalizing the XML does not reorder
  elements or rename ids either.
- **Make `network_id` a semantic hash of the topology.** Rejected for now: `network_id` equals the content
  hash of the file by invariant and by the DatabaseMCP contract, and the reuse lookup depends on it.
- **Compare networks by full graph isomorphism now.** Rejected for v1: it is expensive in general and the v1
  catalogue never needs it. Kept as task E9.9 of M52.
- **Match edges by their id.** Rejected: an `add_edge` generator and a golden path may give different ids to
  the same edge. Matching by endpoints and attributes covers the catalogue.
- **Compare demand by files or by `scenario_id`.** Rejected: demand depends on the seed, and a 1.4 and a 1.65
  scale can give the same KPI. The intention (a range) and the effect (the KPI with its tolerance) are
  compared.
- **Leave demand out of the outcome until later.** Rejected: it has the same problem as the topology and the
  pieces to state it (a range, the KPI tolerance, the DoD fidelity) already exist.
- **Warnings instead of failures from the start.** Rejected for now: the DoD asks for 11 of 11, and the
  severity is a field in case that changes.
- **The trace only with a flag.** Rejected: a CI with no writable file system is handled by `--no-trace` and a
  write that fails without failing the run, and a default of writing avoids losing the one failed run with a
  paid model.
