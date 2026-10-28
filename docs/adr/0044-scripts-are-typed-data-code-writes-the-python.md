# ADR-0044: A script is typed data and code writes the Python; no sandbox, no lint

- Status: Accepted (2026-10-14, task E2.5). Supersedes [ADR-0005](0005-traci-api-scripts-as-the-single-dynamic-mechanism.md)
  on who writes a script and on the lint and the sandbox. Amends principle 3 of
  [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) for scripts, the `custom` row of its §2.5
  and DoD §4.6 ("subprocess sandbox"), and answers its §8 open question on compound conditions and
  reversal. None of them is edited
- Date: 2026-10-14
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §1 (principle 3),
  §2.4, §2.5, §4.5, §4.6, §8; ADR-0003, ADR-0005, ADR-0006, ADR-0007; work-plan §1 (E2.5, E2.6, E2.8) and
  §7 row r25

## Context

No ADR states "agents decide, code writes" as a general rule. It exists per module: ADR-0003 (network edits
go through typed tools, never the compiled `.net.xml`), ADR-0007 (static mechanisms are written by
deterministic writers) and ADR-0006 (`reroute_demand` is code). For scripts the record says the opposite.
Principle 3 of the architecture doc ("Agents write networks, demands, scenarios, scripts...") and ADR-0005
have the Scenario Builder write free Python, and the `custom` row of §2.5 lets it write free Python against
`traci_api`. v0.2 had the other design, a declarative `TraciPlan` that LLM agents filled in. ADR-0005 dropped
it for an interpreter-free API.

Free Python from an LLM is what made the rest of ADR-0005 necessary: an AST lint that allows only
`resto.traci_api` imports, a `ScriptSandbox` port, `DeclaredRule`s as strings to say what a script does,
`lint_ok` and `dry_run_ok` flags on `TraciScript`, and a promotion that refuses any scripted scenario until
something sets the flags. None of it exists in working form. `SumoRunner.run_online` raises
`NotImplementedError`, the sandbox adapter is a placeholder, and `RunSimulation` and the study's run step
refuse an online scenario. Every dynamic intervention ends in `rejected[]` or in a failed step.

## Decision

**1. A script is typed data.** `TraciScript` holds its rules directly. A rule is a trigger (`AtTime(t)` or
`When(Condition)`) and an action (`CloseLane`, `OpenLane`, `SetSpeed`, `SetTlsProgram`). They are
discriminated unions of small dataclasses, with no nested "details" object and no strings to parse.
`TraciScript` loses its `ArtifactRef`, `lint_ok`, `dry_run_ok` and `DeclaredRule`: the rules are the declared
rules. The Builder composes rules through tools (blocks, catalogue designed in E2.6) and never writes a
file. This extends the pattern of ADR-0003 and ADR-0007 to scripts. Compound conditions and reversal, the
open question of §8, become blocks and not free Python.

**2. The Builder's responsibility, in one sentence:** the Scenario Builder decides which SUMO mechanism
applies each intervention. Writing the files (XML or Python) is code.

**3. Code writes the Python.** A translator in `adapters/` turns a `TraciScript` into a Python file: one
import from `resto.traci_api`, one registration per rule, `run()` last. It is not in the domain, because
generating Python text is infrastructure. The same `TraciScript` gives a byte-identical file. The
translator's unit tests are the reason the file is trusted.

**4. The file is generated at run time**, like `run.sumocfg` from the scenario cfg. The `Scenario` stores
only the rules. Each run writes `script.py` into its directory as an input artifact and hashes it into its
`content_hash`, so the run directory reproduces the run.

**5. The script ends in `run()`.** The Runner does not call `run()` for the script: the file is the whole
program. The harness calls `start()` before it and `close()` after it.

**6. No sandbox.** The word and the `ScriptSandbox` port go. The lint is covered by the type and the
translator's tests, and the `declared_rules` are the rules. What remains is a subprocess, for technical
reasons only: `traci_api` keeps global state, a crash must not take the study down, and a hung run needs a
timeout.

**7. The Runner trusts the domain object.** A script that imports anything else cannot exist as a
`TraciScript`. DoD §4.6's "rejected before SUMO starts" therefore holds by construction, and the domain and
translator tests are its evidence.

**8. The dry run stays, as a check stage after construction.** For a scenario with a script, `BuildScenario`
runs promotion (invariants, ids exist on the network), then the dry run, then the load check. The dry run
generates the file with the same translator and checks that it parses and has the expected structure (one
import, the rules, `run()` last). Then, in one SUMO session that stores nothing, it runs 50 steps of the real
script, evaluates every condition once and applies every action once, whatever its trigger. That catches ids
only SUMO knows at run time (a TLS program defined in an `.add.xml`) even for a rule that would fire late. A
failed dry run is a `DraftRejected` with SUMO's error, like a failed load check. `dry_run` moves to
`SumoRunner`.

**9. `custom` with free code is out of v1.** A `custom` that no static mechanism or block covers goes to
`rejected[]` with a reason, which DoD §4.5 already allows. A separate agent for free `custom` code is a new
task in the optional package M52, **E2.8** (8 pts, no date). It brings its own isolation and reuses E2.5's
online Runner.

**10. Seed and outputs.** The seed reaches SUMO through `run.sumocfg`, as in batch; the script has no
randomness of its own. The subprocess writes the applied actions to a file in the run directory and the
Runner reads them into the `SimulationResult`. A script that fails at run time (SUMO rejects an id) gives a
`failed` run with the traceback in `error`.

**Split with E2.6.** E2.5 brings `TraciScript` with the blocks the 10 test cases need, the translator, the
online Runner, the dry run wired into `BuildScenario`, and online mode in `RunSimulation` and the study step.
E2.6 widens the block catalogue (compound conditions, reversal), adds the Builder's tools to compose blocks,
and feeds a failed dry run back to the Builder.

## Consequences

- No concept is left that ADR-0005 needed only for free Python: the lint, the sandbox port, `DeclaredRule`
  and the flags go, with the code that produced them. The code gets smaller.
- A scripted scenario stores rules, not a path, so a stored scenario never points at a file that moved, and
  it round-trips through the JSON schemas (DoD §4.9) like any other domain value.
- The expressive range of a dynamic intervention is the block catalogue. A shape no block covers is rejected
  with a reason until E2.6 adds a block or E2.8 adds free code. That is a deliberate narrowing for v1.
- Safety no longer rests on filtering code written by a model. It rests on there being no such code. The
  price is that a translator bug is a bug in every script, which its byte-exact tests and the dry run's
  structure check are there to catch.
- DoD §4.6 still reads "subprocess sandbox" and "rejected before SUMO starts". The architecture doc is
  frozen, so this ADR is what the tracker reads: the subprocess stays, the rejection holds by construction.
- `applied_actions` keeps `origin`. Every action of a v1 script has the origin `rule`; `code` waits for E2.8.
- A failed dry run costs one short SUMO session at build time and saves a failed study step later.

## Alternatives considered

- **Keep free Python with the lint and the sandbox (ADR-0005).** Rejected: it needs the lint, the port, the
  declared rules and a trust model for model-written code, and none of it was built. It also contradicts
  ADR-0003 and ADR-0007, where the same Builder never writes a file.
- **Bring back a declarative `TraciPlan` with its own interpreter.** Rejected for the reason ADR-0005 gave:
  two surfaces to keep in sync. Here the typed rules are translated to calls on the same `traci_api`, so
  there is one mechanism and no interpreter.
- **Store the generated file in the `Scenario`.** Rejected: the file would then be an artifact that can fall
  out of step with `traci_api`. Generating it at run time from the rules cannot.
- **Keep `dry_run` in a sandbox port.** Rejected: with no sandbox it is a SUMO session, and `SumoRunner`
  already owns those.
- **Allow free `custom` code in v1 behind OS-level isolation.** Rejected as out of scope: isolation is its
  own piece of work, and it goes to E2.8.
