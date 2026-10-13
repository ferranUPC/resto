# ADR-0040: Use cases are classes, collaborators go in the constructor, one composition root builds them

- Status: Accepted (2026-10-13, refactor r21). Amends [ADR-0030](0030-executor-package-and-module-split.md)
  decision 1 (the public use case is `RunStudy.execute`, not the function `run_study`) and decision 3
  (`StudyDeps` also holds the inner use-case instances). ADR-0030 is not edited
- Date: 2026-10-13
- Architecture reference: [ADR-0030](0030-executor-package-and-module-split.md), [ADR-0023](0023-coordinator-split-deterministic-executor.md);
  `CODING_STANDARDS.md` (dependency direction); work-plan §7 row r21

## Context

A use case is a module-level function whose signature mixes two kinds of argument. Some describe the request
(the user's text, a task, a seed). The rest are collaborators (repositories, the SUMO runner, the network query
loader, output directories) that are the same for every call in a process. The Executor passes six keyword
arguments to `build_scenario` and five to `run_simulation`, all read from `StudyDeps` or `StudySettings`.
`run_study(text, deps, settings, *, mode, max_rounds)` carries the whole object graph next to the user's text.
Wiring is spread over `build_deps` in the CLI, the Executor, the Scenario Builder's tools, `scripts/` and `golden/`.

## Decision

1. **Shape.** Every implemented use case in `application/use_cases/` is a class. Its constructor takes the
   collaborators and the process-level settings. One public method, `execute`, takes only the values that
   describe the request. The class has no other public method.
2. **Name.** The class is named by the use case's verb: `RunStudy`, `BuildScenario`, `RunSimulation`,
   `AskExpert`, `WriteNote`, `UpdateNoteStatus`, `ComposeReport`, `ScaleDemand`. No use-case name equals an
   agent name in `GLOSSARY.md` (Scenario Builder, Expert, Composer).
3. **Composition root.** `resto/interface/dependencies.py` builds every object. It builds the inner use
   cases first and passes the instances to whatever calls them: the Executor through `StudyDeps`, the
   Scenario Builder's tools through `BuilderCollaborators`. It returns a ready `RunStudy`. The CLI asks it for
   a `RunStudy` and calls `execute`. Nothing in `application/` wires objects.
4. **Split rule.** `dependencies.py` becomes the package `interface/dependencies/`, one module per use case,
   when one use case's wiring makes the reader scroll past another's. A line count is not the trigger. The
   public entry points keep their names, so no caller changes. The first split is expected around E6.1 and E7.1.
5. **Callers outside `interface/`.** `scripts/` use the composition root for a whole study and construct the
   class directly for a single use case. `eval/` constructs the classes directly and does not import the
   interface layer.
6. **Enforcement.** A test next to `tests/unit/test_import_boundaries.py` fails when a module in
   `application/use_cases/` defines a public top-level function, or a public class without `execute`. The
   placeholder modules (`derive_network`, `generate_demand`, `generate_network`, `reroute_demand`) are
   excluded until E6.1 and E7.1 write them as classes.

## Consequences

- ADR-0030 keeps its text. Where it says `run_study` is the public use case, read `RunStudy.execute`. Where it
  says `deps` holds the agents, the promotions and the repositories, it also holds the inner use-case instances.
  A `StudyDeps` field that only fed an inner use case leaves once the Executor stops reading it.
- `execute_study` stays a function (ADR-0030 decision 2). The Executor's phase functions do not become classes.
- Behaviour does not change: messages, error kinds, trace events, stored states and budget arithmetic stay as
  they are.
- No dependency-injection library. Wiring is plain constructor calls.
- MCP servers in `interface/mcp/` do not call use cases today and are out of scope.
