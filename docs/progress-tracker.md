# Progress tracker

Tracks completion of every task in [`tfm-work-plan.md`](tfm-work-plan.md) (**v0.4**, restructured 2026-10-02, re-baselined
2026-09-24). Task descriptions here are shortened for scanning — the source of truth for scope, points
and due dates is `tfm-work-plan.md` §1, and for DoD thresholds `tfm-architecture-and-dod.md` §4.x.

Status (decided 2026-09-24, wayfinder #3 — exact wording, applied by the `progress-review` skill):

- ⬜ not started · 🔄 in progress · ✅ done.
- ⏳ **awaiting measurement**: the work is built and every development run it needs has been done; the
  only thing between it and ✅ is a measurement suite in `eval/measurement-plans.md` (the table
  `docs/evaluating-resto.md` §7.2 used to carry, before that file was split into `eval/` on 2026-10-06),
  which runs in Validation 1 or 2. The Notes name the suite and say whether the development evidence
  (e.g. a 1-repetition sweep) already meets the threshold. A deferred paid run is never a reason for 🚧.
- 🚧 **blocked**: cannot proceed for a stated reason outside our control (an external person, data or
  service); the Notes say what unblocks it.
- 🚫 **cancelled**: the work plan marks the row cancelled directly (this repo keeps no `.scratch/` spec
  files, so the cancellation note lives in `tfm-work-plan.md` itself, e.g. "*(cancelled yyyy-mm-dd,
  rNN: ...)*"). A cancelled task is not pending work: left out of the done and pending-points counts,
  and never named as "next". Its Notes say why and name the refactor or task that absorbed its scope.

Last updated: 2026-10-07

**Summary: 34 / 82 tasks done (41.5 %), 6 awaiting measurement, 2 in progress, 2 cancelled** (⏳: E4.2,
E4.3, E4.4, E4.5, E4.7, E5.1, 92 pts, counted apart from done; 🔄: E3.7 (2 pts), E5.3 (14 pts); 🚫: E5.2,
E5.5 (their 14 pts together leave the plan, r14); E9.7 is Stretch, never scheduled, excluded from the
count per work plan §5; E5.15 is new this review, +1 to the denominator).

Since the last review (`f39bb10`, merged 2026-10-06 07:59), one very dense day landed as three PRs
(#19-#21) plus small direct pushes, all dated 2026-10-06. A refactor removes `counterfactual` from
`Intent` (r9-r11, ADR-0038). A bigger one deletes the Coordinator agent outright and replaces it with a
pure domain function (r13, ADR-0039). E3.9 adds the evaluation-budget document. The work-plan
bookkeeping (r14) follows from both.

- **The Coordinator agent is gone. Not refactored, not stubbed. Deleted.** `18801b4` (PR #20, ADR-0039,
  Accepted) adds `src/resto/domain/services/planner.py`, a pure `plan_study(question, context) ->
  StudyPlan` function, called directly by the Executor (`application/executor/planning.py`). Verified
  now: `CoordinatorAgent`, `ClarificationRequest`, `Phase.clarification` and the `coordinator.py`
  adapter/tool placeholders are all gone from `src/`; `grep -rn "CoordinatorAgent\|ClarificationRequest"
  src/` returns nothing. A planning failure is now `StepErrorKind.PLANNING`, not an agent call. This is
  the single biggest change to the plan since M0. It **deletes** two tasks rather than building them.
- **r14 cancels E5.2 and E5.5 because r13 already did their work.** E5.2 ("Planner: the pure function
  `plan(question, context) -> StudyPlan`...") is now 🚫. r13 built exactly that function, oracle
  included (r13-03's 14+1 hand-frozen plans). E5.5 ("Executor Done: `StepRecord` trace, zero redundant
  simulations, failure injection") is 🚫 too, but its three pieces are **not dropped**, only reassigned.
  The trace checks and the zero-redundant-simulations counter move to E5.3; failure injection, including
  the planning error already covered by r13-07, moves to E9.3. Checked now: `grep -rn "redundant"` in
  `src/` and `tests/` finds only the pre-existing idempotency comments in `run_simulation.py`,
  `build_scenario.py` and `scale_demand.py`. No counter test exists yet for "a scenario a later Expert
  round needs again is never re-simulated." That piece of E5.5's old scope has moved to E5.3's row, not
  been built.
- **E3.9 (evaluation budget document) is done. Flips ⬜ → ✅.** `b61d918` (12 commits across one PR)
  builds `eval/budget/`, with a cost model (`model.py`, `cost-data.toml`) over three tiers (minimum,
  planned, extended), a short English version (`short-version.md`, one row per suite: measures,
  threshold, pass, size, measured-vs-proxy share) and a full plan (`full-plan.md`) with per-suite token
  counts and $ ranges. Verified by reading both files directly: the plan-bank routing suite is correctly
  absent (ADR-0039 made it a deterministic test, not a paid run), and the totals table states the
  reference cap plainly: the "planned" tier is $20.58-32.47 combined, over the $30 reference by up to
  $2.47 at the high end, with "that possible excess is what the funding request can ask for." An
  interactive page (`eval/budget/page.html`+`page.py`) lets a reader change tiers, models and
  repetitions and export the choice. 52 new tests (`test_budget_model.py`, `test_budget_page.py`,
  `test_budget_render.py`, `test_budget_short.py`), all green. Built 16 days before its own due date
  (23 Oct) and before the ~24 Oct funding request this task exists for. The one external-deadline risk
  the last review flagged is now closed.
- **E3.7 stays 🔄, now at 2 pts, was 4. The human review still has not happened.** r13 absorbed the
  rules-script half of E3.7's old scope into the domain planner, so what is left is purely the review.
  `corrected.json` is still `{"plans": {}}` (checked now, same empty placeholder as last review), and
  `test_plan_review.py`'s own docstring still says the real review "is not part of the repo." r9/r13
  also regenerated `plans.json` through the new planner, so the maintainer's earlier read of the
  pipeline's output is now partly stale. `528cda8`/`9d32660` add a `reviewed_snapshot.json` (frozen at
  `29fcc09`, before r9/r13) and a diff tool (`annotation/changes.py`) that marks, on the review page,
  which plans moved since that snapshot. Verified now: **30 of the 54 plans are flagged changed**,
  ignoring the `run_simulation` steps r13 added to every plan (which would otherwise flag 51/54 and tell
  nothing apart). The review that was "ready to review" last time is now a review of a moving target.
  The task is smaller in scope but not closer to done.
- **E3.10 (trim the decisions log) is further from done than last review, not closer.** The target file
  was renamed `eval/decisions-log.md`, split out of the old `docs/evaluating-resto.md`, and **grew**:
  `2d83178` adds 71 lines to it, still one long paragraph per decision, not the "one line per decision"
  the task asks for. Checked now: 72 lines, same shape as before the rename. Still ⬜.
- **E5.1's Parser moved to `PARSER_VERSION = v8`** (`2d83178`) to track the `counterfactual`-intent
  removal. A fresh dev sweep (`v8-dev`, 255 requests, $0.21) clears every §4.1/arm-structure dev
  threshold (intent 95.6 %, arm structure 90.7 %, the rest 94-99 %). This is development evidence on the
  dev split only. The task's own Done bar is the **held-out** N4 measurement, still reserved for
  Validation 2 per the last review's finding (v6-heldout's 93.9 % intent agreement across 3 runs, below
  the ≥95 % bar). Status unchanged: ⏳.
- **The previous review's doc-hygiene paper cut is fixed.** `docs/study-flows.md`'s dangling references
  are gone. `tfm-work-plan.md`'s E9.1 row now reads "the file is pending regeneration, out of scope for
  now" instead of pointing at a deleted file, and ADR-0030 annotates its own references the same way.
- **E5.15 is new this review (r13/r14, 1 pt) and is not started.** Its job is to search the repo for
  Coordinator leftovers (`CoordinatorAgent`, `StudyPlan | Clarification`, `allow_script`, adapter/tool
  placeholders) outside the ADRs and history, and regenerate schemas. Checked now: `allow_script` is
  still named as part of `ScenarioTask` in the live architecture table of
  `docs/tfm-architecture-and-dod.md` (§2.4), and that same table still lists "Coordinator" as a live
  agent row with `StudyPlan` output. No commit has touched that file since before this review's work
  started (`git log` on it stops at `2d83178`, which did not reach this table). This is a real,
  checkable leftover the task's own DoD asks to find, not a nitpick. ⬜.
- E5.4, E6.1 and E7.1's agent files are all still confirmed 4-line placeholders; E9.1's golden-path
  framework still does not exist.

By plan points: **396 of 973 (40.7 %)** are in ✅ tasks (391 + E3.9's 5), 92 in ⏳, 16 in 🔄 (E3.7's 2 +
E5.3's 14, down from 18 now that E3.7 dropped to 2 pts), 14 🚫 (E5.2's 3 + E5.5's 11, left the plan with
r14), leaving 469 in ⬜. This is consistent with the work plan's own running total (1003 → 991 after
ADR-0039 → 973 after r14, §7).
Verified now in a fresh system Python 3.11 venv (no `resto` conda env in this container, same limitation
as every prior review): `pip install -e ".[dev]"` succeeded cleanly, installing `eclipse-sumo` 1.27.1,
`sumolib`, `traci`, `mcp`, `openai`, `pydantic` from PyPI and putting the `sumo` binary on `PATH` once the
venv is activated. `pytest -q` **2269 passed, 1 skipped** (same pre-existing fixture needing a
locally-generated, uncommitted run directory), up from 1718. `ruff check .` clean, and `ruff format
--check .` clean too (format is now CI-enforced, `2d83178`). `mypy` (the CI invocation, over the `files`
list in `pyproject.toml`) clean over **338** source files, up from 322. See
`docs/feasability-analisis/2026-10-07.md`.

---

## E0 — Foundations (70 pts, 8 tasks) · DoD §2

| ID | Task | Status | Notes |
|---|---|---|---|
| E0.1 | Repo skeleton: hexagonal layout, packaging, ruff, pytest, CI | ✅ | 2026-09-11: layout restructured to architecture v0.3 (`domain/`, `application/{ports,use_cases,tools,schemas.py}`, `adapters/{llm,sumo,sandbox,web,persistence,tracing}`, `interface/{mcp,cli}`, `eval/`); placeholders for every module; 28 tests green, `ruff check .` clean. `ci.yml` already targets `master`; not yet pushed, so still no workflow run to confirm CI green. 2026-09-13: pushed; `gh run list` shows 3 CI runs on `master` (`1d1578b`, `a0e1fa2`, `554086c`), all `success` → output "repo + green CI" met (closed 11 Sep, 1 day after its 10 Sep due date) |
| E0.2 | Pin SUMO 1.27.1 from PyPI; reproducible environment incl. Postgres + `pgvector`; record in README | ✅ | 2026-09-11: SUMO 1.27.1 pinned as `pyproject.toml` dependencies, installed and verified in the `resto` env; README rewritten. 2026-09-14: the Postgres + `pgvector` service is no longer part of the design — ADR-0012 (architecture v1.0, A1) moves the DatabaseMCP reference backend to SQLite + in-process cosine. The residual paper-cut noted in an earlier review is fixed: commit `749b393` rewrote the stale "Postgres + `pgvector`" wording in `tfm-work-plan.md` E0.2/E1.3 to describe the SQLite backend |
| E0.3 | Domain dataclasses (aggregates, value objects, tasks, drafts) + `schemas.py` TypeAdapters, JSON-schema export, round-trip tests | ✅ | 2026-09-14: committed in `32672d5`. Six aggregates + value objects incl. `drafts.py` (`NetworkDraft`/`DemandDraft`/`ScenarioDraft`/`ExpertNoteDraft`), `schemas.py` TypeAdapters, 18 files in `schemas/` with a drift test, `test_serialisation.py` round-tripping every domain dataclass, `test_drafts.py`. Verified now: `pytest` 186 passed, `ruff check .` clean, CI green on `master` (run `34816761408`) |
| E0.4 | DatabaseMCP contract spec (six capability groups incl. `demands`, `query_edgedata`; error codes) | ✅ | 2026-09-14: `docs/DATABASE_MCP_CONTRACT.md` committed (`0ea81ac`, CI green). Six capability groups (§5.1–5.6), error codes (§7), conformance checklist (§8, for E1.5 to implement against), SQLite reference impl (§9). §10 open points 1–2 resolved by architecture amendment A2 (`Network.label`, note-ranking as a pure domain algorithm — ADR-0013/0014); open point 3 (`historical_demand` shape) is *deliberately* left open until E7.4 per the doc's own text, not a gap in this task. Cosmetic-only issue: the file's own title/header still literally read "v1.0-draft" despite the architecture freeze — worth a one-line fix, doesn't affect content completeness |
| E0.5 | DEV-NET: grid + hand edits (bottleneck, signalised corridor) | ✅ | 2026-09-14, commit `5e48e03` (CI green): `netgenerate` 5×5 grid, scripted (`generate.sh`, reproducible, no manual GUI edits), 2→1 lane merge bottleneck on `B0C0`→`C0D0` isolated from the row-2 signalised corridor (5 TLS junctions), 0 U-turn connections, fully strongly connected — all verified and documented in `eval/dev-net/README.md` with concrete counts (80 edges, 25 nodes, one expected `netconvert` warning) |
| E0.6 | Demand profiles low/peak/incident on DEV-NET (trips + routes) + synthetic counts at control edges | ✅ | 2026-09-14, commit `e5f1ef5` (CI green): `low`/`peak`/`incident` trips+routes (seed 1), `control_counts.json` at 5 control edges, `verification.ipynb` sweeping simulation seeds 1–9 per profile. `peak` measured at 16.5% mean congestion (inside the 10–20% target), `incident` isolates the `B0C0` bottleneck (26× peak occupancy). Not reopened for the ADR-0028 clock-time move — that migration is E3.8, still ⬜; this task's own output (seconds-based demand, verified) still meets its own Done bar |
| E0.7 | Trace logging: run id, step, tool call, artifacts, tokens → JSONL | ✅ | 2026-09-14, commit `bcca11c` (CI green): `Tracer` port + `JsonlTracer` adapter (`{root}/{study_id}.jsonl`, one JSON object per line, tolerates dataclasses/`Enum`/`Path` payloads). `test_jsonl.py` covers ordering, per-study isolation, unknown-study read, and payload serialisation of `StepStatus`/`Usage`/`Path` — 5 tests, all passing |
| E0.8 | Architecture doc frozen as v1.0 + ADRs for §7 decisions | ✅ | 2026-09-14, commit `7745324` (CI green): `tfm-architecture-and-dod.md` header now reads "v1.0 — Status: frozen (2026-09-14, E0.8/M0)"; 14 ADRs under `docs/adr/` (0001–0014) with an index (`README.md`); §9 amendments A1/A2 reconciled into the body and superseded as prose by their ADRs |

## E1 — MCP servers and `traci_api` (94 pts, 6 tasks) · DoD §4.9

| ID | Task | Status | Notes |
|---|---|---|---|
| E1.1 | NetworkMCP (7 read tools + tests incl. error case) | ✅ | 2026-09-14, commit `daf304d` (CI green): all 7 tools (`get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`, `edges_in_bbox`, `capacity_estimate`, `get_tls`) live as `application/tools/network.py` functions, wrapped by `interface/mcp/network_server.py` (ADR-0009: MCP layer is protocol plumbing only). Coverage is layered rather than duplicated per file: `tests/unit/adapters/sumo/test_netxml.py` carries the real ≥3-tests-incl.-error-case bar per method (25 tests, every one of the 7 query methods plus `has_edge`/`has_lane`/`has_tls` has an explicit unknown-id `KeyError` case), `tests/unit/application/tools/test_network.py` (10 tests) checks delegation + `Tool` wrapping, `tests/unit/interface/mcp/test_network_server.py` (4 tests) checks the server wires those tools and surfaces an unknown-id error as `UnexpectedToolError`. Verified now: full suite green |
| E1.2 | `traci_api` (8 primitives + `at_time`/`when` + `applied_actions`) and TraciMCP over it | ✅ | 2026-09-14, commit `4301d1c` (CI green): `adapters/sumo/traci_api.py` has all 8 primitives (`close_lane`, `open_lane`, `set_speed`, `set_tls_program`, `get_edge_occupancy`, `get_edge_speed`, `get_vehicle_count`, `step`) plus `at_time`/`when`/`run`/`applied_actions`/`registered_rules`, each `AppliedAction` tagging `origin=CODE` vs `origin=RULE`. `interface/mcp/traci_server.py` exposes the 8 primitives over MCP (deliberately not `at_time`/`when`, documented reasoning: callables can't cross the JSON wire — a design call, not a gap). `tests/unit/adapters/sumo/test_traci_api.py` (20 tests) runs with a **real SUMO/traci session** against DEV-NET, not mocks — covers every primitive, an unknown-id `TraciException` case for the mutating ones, `at_time` firing once, `when`'s rising-edge semantics, `origin` tagging, and `run(until=...)`. `test_traci_server.py` (3 tests) + `test_traci_api_facade.py` (35 tests) round it out |
| E1.3 | DatabaseMCP reference impl (SQLite + in-process cosine, ADR-0012; six capability groups incl. `demands`) + `mcp_client` adapter | ✅ | 2026-09-14, commits `1a3c930` + `8ee4380` (CI green): `adapters/persistence/sqlite/repositories.py` implements the 5 required capability groups (`networks`, `demands`, `scenarios` incl. `find_similar_scenario`, `results` incl. `query_edgedata`, `notes` incl. `search_notes`) over `interface/mcp/database_server.py` (17 tools, contract error codes as `"CODE: message"`-prefixed `ToolError`s per §7). `adapters/persistence/mcp_client.py` speaks *real* MCP (`ClientSession` over any `mcp.client` transport, sync/async bridging documented in-file) rather than calling the server in-process — this is what the conformance suite (E1.5) actually exercises. `historical_demand` (6th, optional group) is deliberately unimplemented, per contract §10 point 3, deferred to E7.4 — not a gap in this task. Tests: 25 in `test_repositories.py`, 18 in `test_mcp_client.py`, 8 in `test_database_server.py` |
| E1.4 | `find_similar_scenario` + `search_notes` + `query_edgedata` (10 + 5 + 5 test cases) | ✅ | 2026-09-14, commit `8ee4380` (CI green): the 10+5+5 bar is met in `conformance/` (run through the real `mcp_client` adapter, per §4.9's own framing of this bar as a conformance requirement): `test_find_similar_scenario.py` 10 tests, `test_search_notes.py` 5 tests, `test_query_edgedata.py` 5 tests. Additional unit-level coverage in `test_repositories.py` (5 find_similar + 5 search_notes) and `test_edgedata.py` (8 tests) |
| E1.5 | DatabaseMCP conformance suite | ✅ | 2026-09-14, commit `8ee4380` (CI green): `conformance/` (56 tests) is parametrized over every DatabaseMCP backend the project ships (`_BACKENDS` dict, currently `sqlite-reference`) and reaches every backend only through `interface/mcp/database_server.py` + `adapters/persistence/mcp_client.py` over a real (in-memory) MCP `ClientSession`, never a backend's repository classes directly |
| E1.6 | Capability-listing helper for Coordinator; latency benchmark | ✅ | 2026-09-14, commit `c77692b` (CI green, verified now): `application/capability_negotiation.py` derives capability groups from a backend's advertised tool names (`capabilities_of`) and hard-fails start-up on a missing required one (`negotiate_capabilities`, `MissingRequiredCapabilityError`), with `historical_demand` treated as optional per contract. `eval/benchmarks/latency.py` + `eval/benchmarks/latency-report.md`: all 32 MCP tools benchmarked at 50 reps each on DEV-NET, every one well under the §4.9 <1s threshold (slowest 4.84 ms max) |

## E2 — Scenario Builder & Simulation Runner (110 pts, 7 tasks) · DoD §4.5, §4.6

| ID | Task | Status | Notes |
|---|---|---|---|
| E2.1 | Runner batch mode (+ ephemeral mode for probe/calibration) + reproducibility test (20 runs) | ✅ | 2026-09-15, commit `1e23009` (CI green, verified now): `adapters/sumo/runner.py`'s `SubprocessSumoRunner.run_batch` derives a run cfg, runs `sumo -c`, collects edgedata/tripinfo/statistics/summary as `ArtifactRef`s. `application/use_cases/run_simulation.py`: `run_simulation` computes `result_id = hash(scenario_id, seed, mode, sumo_version)` before running, returns an existing *ok* result unrun; `run_ephemeral` is the unstored probe/calibration path. `test_twenty_runs_with_the_same_seed_are_byte_identical` runs 20 real SUMO batch runs and asserts a single distinct content-hash tuple. Online mode (`run_online`) still raises `NotImplementedError`, correctly deferred to E2.5. 2026-09-29, commit `d72f880` (ADR-0031, found in this review): fixes a real crash, retrying a failed seed under the SQLite backend raised `ConflictError` instead of re-running, because a second `failed` attempt's content always differs from the first. Only an `ok` result is stored now; `run_simulation` takes a required `attempt` label and stages each attempt's SUMO output separately, promoting it to the canonical path on success. This task's own Done bar (byte-identical reproducibility over 20 runs) was already met and is unaffected; the fix matters for V1/V2 runs that will retry failed seeds for real |
| E2.2 | Builder Minimal (agent + writer tools): static `lane_closure`/`speed_limit` → `.add.xml` + `sumocfg` | ✅ | 2026-09-15, commit `ee85dad` (CI green, verified now): `adapters/llm/agents/scenario_builder.py` assembles the `AgentTask`/tool list/budget and calls the shared `ToolAgent` port; system prompt restricts it to `lane_closure`/`speed_limit` on a single lane with a fixed window, "no silent coercion" (ADR-0007). `application/tools/scenario_builder.py` binds real `Tool`s; `application/use_cases/build_scenario.py::build_scenario` promotes an `AgentRun[ScenarioDraft]` in the DoD §2.4 order. Real `OpenRouterToolAgent` (`adapters/llm/anthropic_client.py`) wired with `RESTO_LLM_DEFAULT_MODEL=deepseek/deepseek-v4.1-flash` as the hard default per CLAUDE.md's cost policy |
| E2.3 | Builder static: `edge_closure`, `signal_program` (WAUT), `demand_scale` | ✅ | 2026-09-15, commit `7ad97c5` (verified now): rerouter writer dispatches on `edge_closure` (with `disallow="all"` fixed in `bc46212`), `write_tls_program` for static `signal_program`/WAUT, `scale_demand` (deterministic resample + `duarouter`) for `demand_scale`. Covered end-to-end by the E3.1 matrix against real SUMO |
| E2.4 | Effect-verification harness | ✅ | 2026-09-15, commit `bc46212` (verified now): `verify/effects.py` implements the DoD §4.5 checks (edge flow, completion rate, speed limit, signal-program coverage+revert, demand-scale departed count), one `test_*.py` per intervention type running the real `SubprocessSumoRunner` against DEV-NET. `pytest -q conformance/ verify/` → 61 passed (verified now, still green) |
| E2.5 | Runner online mode: `ScriptSandbox` (lint, dry-run, subprocess) + 10 script test cases | ⬜ | Wave 2. Replaces the v0.2 `TraciPlan` interpreter. No commits since the last review; still not started. Work plan flags this as having no fallback: "without it GP-6 and the script half of §4.5 cannot pass" |
| E2.6 | Builder scripts: `condition` → `when(...)`, `custom` interventions, `rejected[]` | ⬜ | Wave 2. Depends on E2.5 |
| E2.7 | Builder bank (25–30 specs incl. `custom`) run to ≥27/30 | ⬜ | Wave 2 (build) / measured in V2. Depends on E2.5, E2.6 |

## E3 — Evaluation assets & harness (97 pts, 10 tasks)

| ID | Task | Status | Notes |
|---|---|---|---|
| E3.1 | Scenario matrix DEV-NET/peak (15–25 rows × 3 seeds) | ✅ | 2026-09-15, commit `3900171` (verified now): `eval/scenario_matrix/` hand-authors 20 rows × 3 seeds = 60 `SimulationResult`s, promoted through the real `build_scenario`/`run_simulation` use cases and stored through an actual MCP `ClientSession`. Each row's DoD §4.5 effect is re-checked before it counts as built. 2026-09-25, commit `5be77ab`: **rebuilt in clock time by E3.8 (now ✅)**. All 20 rows re-pass their §4.5 effect check on the 08:00–09:00 window; this task's own Done bar was already met before the rebuild and stays met after it |
| E3.2 | Question templates + generator + gold answers (≥60 on DEV-NET) | ✅ | 2026-09-17, commit `10c85a6`: 117 questions on DEV-NET/peak (floor: 60) — 40 descriptive, 20 diagnostic, 57 counterfactual — over the E3.1 20-row matrix. Verified now: `question-bank.json` has exactly 117 entries. 2026-09-25, commit `5be77ab`: **rebuilt in clock time by E3.8 (now ✅)**, same reasoning as E3.1. Question text reads clock times, gold answers unchanged except the `signal_program` rows' windows, still 117 entries |
| E3.3 | Metrics harness (exact match, Jaccard, direction, band, Brier, abstention P/R) | ✅ | 2026-09-17, commit `2a9d3cd`: `eval/expert_benchmark/` scores exact-set/±5%/Jaccard≥0.6/direction/band/Brier against DoD §4.7 thresholds, mean±std, report generation. 2026-09-22, commit `12276fb`: `abstention_recall`/`abstention_false_requests` landed (thresholds `>= 0.70`/`<= 0.30`), covered by `test_expert_abstention.py`. The harness implements every metric family this task lists — the *measured* threshold on real data is E4.5/E4.7's job (now ⏳, gated on the EXP-01 Validation-2 run), not this task's |
| E3.4 | Request bank (text → `Question`, Input Parser): concepts expanded by variants, dev/held-out split by concept | ✅ | 2026-09-23, commits `1f21429`/`398129d` (bank built, 65 concepts → 306 requests), grown by later tasks (E3.11's described-demand concepts, r9-r11's `counterfactual`-intent removal touching 32 gold concepts' `intent`, per the ADR-0038 deviation row). Checked now directly against `eval/request_bank/concepts.py`/`bank.py` rather than trusting this row's own stale figures: **80 concepts, 378 requests, 255 dev / 123 held-out (32.5 %)**. This row had been left at "73/346" for at least one review past when the bank actually grew; figures corrected here. Still normal bank maintenance on a task already meeting its Done bar (concepts × variants, reviewed, frozen with provenance, dev/held-out fixed by concept), not scope creep |
| E3.7 | Plan bank (`Question` → `StudyPlan`), reshaped by ADR-0037 and, since ADR-0039/r14, a **regression snapshot reviewed by the maintainer** (the planner itself is E5.2's old job, delivered by r13): one gold plan per E3.4 concept with a gold `Question` (54 of 80), independent of the planner only through r13-03's 14+1 hand-frozen plans; ADR-0025 §2/ADR-0027/ADR-0037/ADR-0038 plan rules | 🔄 | 2026-10-05, commit `29fcc09`: the original rules script and phase-1 generator, superseded 2026-10-06 (below). 2026-10-06, `18801b4` (r13): the rules script `propose.py` is deleted. Its logic becomes `domain/services/planner.py::plan_study`, called by the Executor, with `bank.py` renamed to call it (`gold_plan_of`). `plans.json` is regenerated through the planner; `phase1.json` is deleted outright, since the phase-1 case set (57 cases, built from real Expert requests, not E3.4 concepts) is no longer E3.7's, it is r13's own deliverable. `2d83178` (r9) touches the plans again for the `counterfactual`-intent removal. `528cda8`/`9d32660` add a `reviewed_snapshot.json` that freezes the gold fields as they stood at `29fcc09` (before r9/r13), plus `annotation/changes.py`, which diffs today's `plans.json` against it, ignoring the `run_simulation` steps r13 added everywhere (else 51/54 would flag). Verified now: **30 of the 54 plans are marked changed** on the review page since that snapshot. `corrected.json` is still `{"plans": {}}`, checked by reading the file directly, same empty placeholder as last review. `test_plan_review.py`'s own docstring still says "the reviews here are synthetic: the maintainer's real review is not part of the repo." The row's own Done bar (54 plans reviewed, changes marked, regression + corrected-concepts tests green) is not met. The changes-marking machinery is now built, but the review itself still has not happened. 🔄, not ✅. Points drop 4 → 2 (r14): the rules-script half of the old scope is r13's now |
| E3.8 | *(new 2026-09-24)* ADR-0028 migration to clock time: DEV-NET demands `[0,3600)` → `[28800,32400)` (08:00–09:00), scenario matrix and question bank rebuilt in clock time, `verify/` and the expert-benchmark bank loader updated | ✅ | 2026-09-25, commit `5be77ab`: all three DEV-NET demands now depart in `[28800, 32400)` (checked: `depart="28800.00"` … `depart="32400.00"` in the `.trips.xml` files), same `randomTrips` seed shifted by exactly 28800 s so `verification.ipynb` reproduces every figure byte for byte (peak 16.5 %, 0 teleports over 9 seeds; `ea4d9d9` reruns this check over 19 seeds, 16.1 %, still 0 teleports). `eval/question_bank/templates.py`'s `DEFAULT_WINDOW` is now `TimeWindow(28800.0, 29100.0)`; the scenario matrix, question bank (117 questions), `verify/`, the runner test and the expert-benchmark bank loader are all rebuilt/updated on clock time in the same commit. `EXPERT_VERSION` stays v2; this is logged as a measurement fix, not a tuning change |
| E3.9 | *(new 2026-09-24)* Evaluation budget document for supervisors: one row per measurement suite, cost vs the $30 cap | ✅ | 2026-10-06, commit `b61d918` (PR #21, 12 commits): builds `eval/budget/`, with `model.py`/`cost-data.toml` (cost model across minimum/planned/extended tiers), `short-version.md` (one row per suite: measures, threshold, pass, size, measured-vs-proxy share), `full-plan.md` (per-suite token counts and $ ranges, excluding the plan-bank routing suite per ADR-0039), and an interactive `page.html` (tier/model/repetition selector, exportable choice). Verified now by reading `short-version.md` and `full-plan.md` directly: the totals table states plainly that the "planned" tier reaches $20.58-32.47 combined (V1+V2) with contingency, over the $30 reference by up to $2.47 at the high end, named as "what the funding request can ask for" rather than hidden. 52 new tests across `test_budget_model.py`/`test_budget_page.py`/`test_budget_render.py`/`test_budget_short.py`, all green. Built 16 days before its own 23 Oct due date, closing the one external-deadline risk the 2026-10-06 review flagged |
| E3.10 | *(new 2026-09-24)* Trim the decisions log to one line per decision | ⬜ | Wave 1b. 2026-10-06, `2d83178`: the target moved. `docs/evaluating-resto.md` was split, and its §5 is now the standalone `eval/decisions-log.md`, which grew: +71 lines in the same commit. Checked now: 72 lines, every decision still a full paragraph, not one line. Further from trimmed than at the last review, not closer |
| E3.11 | *(new 2026-09-30, widened by its own grilling the same day)* ADR-0035 described demand: `Demand.description`/`labels`, Coordinator demand resolution, `network_only`, request-bank concepts, Parser prompt rules | ✅ | 2026-09-30, commit `73edb96` adds ADR-0035, amended same day (`f529fa9`). Ticket 1 (`4cfa009`): `Demand`/`DemandDraft` gain a required `description` and free `labels`; a real SQLite idempotency bug the new `frozenset` field exposed is fixed by comparing parsed values instead of JSON text. `bb9eaaf` updates GP-10's text to ask for a demand instead of falling back to random trips. 2026-10-01, tickets 2–6: `129d687` adds `dev_net_demand(profile)` describing DEV-NET's three demands. `c88f15c`/`4cccb12`/`d78e4bb` add `Question.network_only` with its own excluded-fields invariant, scored by presence. `e80a2e2` rewrites the request-bank concepts for the ADR: concepts name a demand or spread it across the text, 3 network-only `describe` concepts plus a traffic counterexample, 3 concepts on networks outside the DB (Berlin-Mitte, the Eixample, a 4×4 grid). `0f55736`/`f719782`/`9c3237d` regenerate and review the variants (dev bank now 255 requests, up from 232). `b815e32` lands the Parser's contract change as **v7**: `demand_ref` a short phrase scored by presence, `time_window` for every intent, the `network_only` rule, `network_ref` over a described network. Verified now by reading `v7-dev.json` directly (255 requests): every E5.1 dev threshold met (validity 99.6 %, intent 99.5 %, interventions/topology/metrics 100 %, ambiguity 95.6 %, arm structure 100 %), new fields reported (`network_only` 100 %, `demand_ref` 93.3 %, `time_window` 84.1 %, not graded). Meets the task's own Done bar (bank rebuilt and verified, Parser dev thresholds still met, tests green — 1298 passed this review) |
| E3.12 | *(new 2026-10-01, from the E3.7 grilling, ADR-0037)* Resolution banks for the specialists: DB states built by functions in `eval/` from `matrix.db` (nothing/network/network+demands/results exist), distractors, the 32-row demand resolution table, gold per case reviewed on an annotation page | ⬜ | Wave 3. New today alongside ADR-0037; this is the DB-state/resolution machinery E3.7 used to carry. No `eval/`-side resolution-bank code or commits found this review. Depends on E6.1, E7.1 per the build DAG |

## E4 — Network Expert (142 pts, 10 tasks) · DoD §4.7 · research focus

| ID | Task | Status | Notes |
|---|---|---|---|
| E4.1 | Refactor v1 Expert onto `ToolAgent` (`ExpertTask` → `ExpertAnswer`); facts via tools; `evidence[]` | ✅ | 2026-09-17, commit `d7683b3` (ADR-0018): `ExpertTask` in, `ExpertAnswer` out, facts only through NetworkMCP + result tools, every tool call recorded in an `EvidenceLedger` so `ask_expert` rejects any unresolved `evidence[]` ref. Verified now: 39 tests pass across `test_expert.py` (agent), `test_ask_expert.py` (use case), `test_expert.py` (tools) |
| E4.2 | Descriptive questions: tune until a development sweep **on the E3.8 (clock-time) bank** meets ≥90 % (→ ⏳) | ⏳ | 2026-09-25, commit `07c1705`: `v2-e38-forced-1rep` (117 questions × 1 repetition, forced, `EXPERT_VERSION = v2`, $0.99) scores descriptive 20/20 + 20/20 = 1.00 ≥ 0.90 on the rebuilt clock-time bank. No tuning change was needed. **Measured in V2 by EXP-01** (117 × 3, held-out repetitions); this 1-repetition dev sweep is the development evidence, already above the bar |
| E4.3 | Diagnostic questions: tune until a development sweep on the E3.8 bank meets Jaccard ≥0.6, "why" ≥70 % (→ ⏳) | ⏳ | Took three extra Expert versions past `v2-e38-forced-1rep`'s 0.80 Jaccard. ADR-0029 (`22ce79a`) added a typed Bottleneck `cause` per edge, scored as `diag_cause_accuracy` (`537d910`); v3 (`c759a21`) regressed to Jaccard 0.10 on the 20-question diagnostic subset (`v3-diag-1rep`, $0.32) because the Expert guessed traffic-light ids and hunted lane drops instead of answering (`3be6555`); v4 (prompt-only, same commit) recovers to Jaccard 0.60 ≥ 0.60, cause accuracy 0.89 ≥ 0.70 (`v4-diag-1rep`, $0.28), on the bar with no margin. 2026-09-30: v5 (`af57bc3`, per-tool guidance moved into tool descriptions, no information change) is noise (11/20 answered vs v4's 12/20, Jaccard 0.55). v6 (`7cdc34d`) makes `get_tls` answer an unknown traffic-light id instead of raising, which stopped the Expert from splitting lookups one id at a time. `v6-diag-1rep` ($0.156 billed) answers 19/20, **Jaccard 0.95 ≥ 0.6, cause accuracy 0.93 ≥ 0.70**, budget stops down from 9 to 1, a real margin above both bars now, not the zero-margin result this row previously carried. v7 (`1f65d85`, ADR-0032 network scope, same day) is a structural change only, the Expert now takes a network scope instead of one id, with no sweep: `docs/expert-tuning-log.md` states the hypothesis (scores match v6) is unmeasured since the benchmark's tasks are single-network. **Measured in V2 by EXP-01**, which will run on whichever `EXPERT_VERSION` is current when V2 starts; dev evidence on v6 clears both bars with margin, pending confirmation that v7's scope change doesn't regress it |
| E4.4 | Counterfactual, forced mode: tune until a development sweep on the E3.8 bank meets direction ≥75 %, band ≥50 % (→ ⏳) | ⏳ | 2026-09-25, commit `07c1705`: same `v2-e38-forced-1rep` sweep scores CF direction 19/19 = 1.00 ≥ 0.75 and CF band 19/19 = 1.00 ≥ 0.50 on the rebuilt clock-time bank. No tuning change was needed. **Measured in V2 by EXP-01**; this 1-repetition dev sweep is the development evidence, already above both bars |
| E4.5 | Free mode: abstention policy, `proposed_experiment`. **Measured in V2** by EXP-01's free-mode leg | ⏳ | *(was 🚧; reclassified this review per the new rule — a deferred paid run is never a reason for 🚧, see legend)* 2026-09-22, commit `12276fb`: the abstention *policy* (`Mode.FREE`, `needs_simulation`, `proposed_experiment`, `ask_expert`'s mode checks) and the `eval/expert_benchmark` harness support to run/score it (`--mode {forced,free,both}`, pairing in `report.py`) are both built and tested. `e45-smoke` ($0.056, 4 questions × both modes) validated the harness end to end but gave no abstention signal by design (tiny sample). The DoD threshold (`abstention_recall ≥ 70 %`, `false_requests ≤ 30 %`) needs EXP-01 in Validation 2, after E3.8's migration and after E4.2–E4.4's dev sweeps establish forced-mode accuracy on the new bank |
| E4.6 | `ExpertNote` writing + RAG + status update; hygiene probes (20) | ✅ | 2026-09-22, commit `4b3f78d` (ADR-0024): `run_expert_note` + `write_note` promote against the round's `EvidenceLedger`; `update_note_status` confirms/refutes `Quantity` claims at ±5%. RAG wired into the agent prompt. `eval/hygiene_probes/`: 20 probes run for real (`hygiene-v1`, $0.112) — 0 violations, pass rate 1.00 ≥ 1.00 required |
| E4.7 | DEV-NET benchmark report from EXP-01 (V2): all §4.7 metrics, 3 runs, mean±std | ⏳ | *(was 🚧; reclassified this review, same rule as E4.5)* Wave F. `docs/expert-tuning-log.md` (report generation) and `parser`/`expert` benchmark tooling are implemented and unit-tested; the report itself needs the EXP-01 run, which needs E3.8's migration first (a report built on the pre-migration `v1-forced-1rep` sweep would need re-running anyway). Still also needs E4.2–E4.4 (accuracy-to-Done work) before it covers the DoD's full scope |
| E4.9 | Learning-effect experiment (0/5/15/25, CIs, plot), moved to **DEV-NET** in v0.3 | ⬜ | Wave 5 (setup, after V1); measured in V2. No commits since the last review |
| E4.10 | Calibration analysis + ablation | ⬜ | Wave F |
| E4.11 | Notes per study: 0–3 `ExpertNoteDraft`s, `scenario_ref` allow-list, `provenance=simulation` rule | ✅ | 2026-09-23, commit `40b5e2c`: `ExpertNoteDraft.scenario_ref` + container; `write_note` checks every draft before storing any. Verified now: `test_write_note.py` — 12 tests covering simulation vs opinion provenance, predictions, allow-list rejection, atomic all-or-nothing storage |

## E5 — Input Parser, Planner, Executor, Output Composer (113 pts, 15 tasks incl. 2 cancelled) · DoD §4.1, §4.2, §4.8

| ID | Task | Status | Notes |
|---|---|---|---|
| E5.1 | Input Parser (own agent, ADR-0023): text → `Question`, no tools, retry-then-fail, `ambiguities[]` → `awaiting_user`; tuned on dev (§4.1 + arm structure ≥90%). **Measured in V2:** held-out, second use (N4) | ⏳ | 2026-09-23, commit `ed8be9b`, tuned further in `32a5cd5` (2026-09-24): `PARSER_VERSION` reached **v6** after settling, with the user, the gold `intent` convention. `v6-dev` meets every threshold; **held-out run (`v6-heldout`, 114×3) executed 2026-09-24** meets every per-run threshold but **`intent` agreement across the 3 runs is 93.9 %, below the ≥95 % bar. E5.1 is not Done.** Per the N4 rule, the held-out split is now spent for tuning; a second, final measurement is reserved for Validation 2. 2026-10-06, `2d83178` (r9-r11, ADR-0038): `PARSER_VERSION` moves to **v8** to track the `counterfactual`-intent removal. A fresh dev sweep `v8-dev` (255 requests, $0.21) clears every threshold again (intent 95.6 %, arm structure 90.7 %, rest 94-99 %). That is development evidence only, on dev, not the held-out measurement this row is actually waiting on. Still ⏳ |
| E5.2 | *(cancelled 2026-10-06, r14: delivered by r13, ADR-0039)* ~~Planner: the pure function `plan(question, context) -> StudyPlan` in the domain layer~~ | 🚫 | Delivered by `18801b4` (PR #20, r13) as `src/resto/domain/services/planner.py::plan_study`, called directly by the Executor; the oracle is r13-03's 14+1 hand-frozen plans. No agent, prompt or port was ever built or needed. The planner replacing the Coordinator (ADR-0039, Accepted) made this task's whole premise, an LLM agent that plans, obsolete rather than merely late. 0 pts (was 3 after ADR-0037, 8 before it) |
| E5.3 | Loop closure (ADR-0023): `needs_simulation` → the planner plans a new phase → Executor runs it → re-ask; `max_rounds`/`forced_by_limit`; multi-network `ExpertTask`; GP-3/4/5 passing; **zero redundant simulations across rounds** (moved here from E5.5, r14) | 🔄 | 2026-09-23 (`6ccb66b`): the Executor-side mechanics are implemented and tested against fake ports. 2026-09-30: the multi-network `ExpertTask` risk is resolved by ADR-0032/refactor r4 (`network_ids` scope). 2026-10-06 (r13, `18801b4`): the loop now calls the real deterministic planner instead of waiting on an agent that no longer exists. The "real Coordinator agent" gap this row used to name is gone by design, not by being filled. What is still missing, checked now: no test anywhere asserts "a scenario a later round needs again is not re-simulated" (`grep -rn "redundant"` finds only unrelated idempotency comments). That counter moved here from the now-cancelled E5.5 but has not been built yet; GP-3/4/5 as golden-path tests still wait on E9.1 (still ⬜) |
| E5.4 | Output Composer Minimal (agent): closed `Study` → `Report` (claims with `evidence_refs`) → Markdown with evidence table | ⬜ | Wave 1b. `application/ports/agents/composer.py` exists; `adapters/llm/agents/composer.py` confirmed still the 4-line placeholder |
| E5.5 | *(cancelled 2026-10-06, r14: its pieces have an owner, ADR-0039)* ~~Coordinator Done: routing ≥90% vs gold plan bank; zero redundant simulations; failure injection → named failing step~~ | 🚫 | Its "routing vs gold plan bank" half died with the Coordinator agent (ADR-0039: planning is a deterministic function, checked by tests, not measured by routing accuracy). Its two other pieces are reassigned, not dropped: `StepRecord` traces → E9.1/E5.3, failure injection incl. the planning error (already covered by r13-07) → E9.3, zero-redundant-simulations counter → E5.3. 0 pts (was 11 after ADR-0039, 18 before it) |
| E5.6 | Capability negotiation with DatabaseMCP; GP-10 | ⬜ | Wave 5 (after V1) |
| E5.7 | Output Composer Done: automatic traceability checker; faithfulness rubric on 20 V2 reports | ⬜ | Wave 5 (checker) / F (rubric) |
| E5.8 | Stability: 3 repeated runs of the Input Parser benchmark, read from V2 (N4) | ⬜ | Wave F. 2026-10-06 (r13): the Coordinator half of this row is gone with the agent (ADR-0039); pts drop 8 → 5. Parser half still reads N4 (E5.1's second held-out use), still pending |
| E5.9 | Domain change (ADR-0023/0025): `Phase`, `Study.phases`, typed `PlanStep` union, `StepError`, `ExpertRound.forced_by_limit`; schemas regenerated | ✅ | 2026-09-23, commit `a3a363a`: `domain/entities/study.py` gains `Phase`/`Study.phases`, `domain/value_objects/study_plan.py` gains the discriminated `PlanStep` union. Schemas and `docs/class_diagram.md` regenerated same commit. Verified now: `test_study.py`/`test_study_plan.py` exercise the invariants directly |
| E5.10 | Executor (`run_study`, deterministic code): resolves `FromStep`, calls specialists, guards in code, runs `ask_expert`/`compose_report` itself; agent ports + composition root; note writer | ✅ | 2026-09-23, commit `6ccb66b` (976 new lines): parse → `Study` → per-phase plan → semantic validation → step execution → forced-last-round Expert loop → note writer → report, `StepError` classified into `user_input`/`budget`/`agent`/`infrastructure`. Verified now: `test_run_study.py` (965 lines, 29 test functions) covers GP-1/GP-2/GP-3-shaped scenarios, forced mode, every `StepError.kind`, budget accounting. 2026-09-29 (`f2d73bc`…`974b933`, ADR-0030): moved verbatim out of `run_study.py` into `application/executor/` as nine modules by responsibility (steps, Expert round, closing, plan validation, failure table, recorder, spend, planning); `TODO(E5.3)`'s multi-network `ExpertTask` gap is still open. Still no behaviour change, this task's own Done bar was already met and stays met. Later the same day (`d72f880`, `ddc8e41`, `384b57d`): `executor/steps.py` was updated to pass the new required `attempt` label into `run_simulation` (ADR-0031, see E2.1) and `executor/failures.py`'s `draft_of` now delegates to the shared `promotion.require_draft` instead of importing per-module exceptions; the classification behaviour these tests already covered (`test_run_study.py`, `test_failures.py`, both still green) is unchanged, only where the exception types live |
| E5.11 | Deterministic rendering (ADR-0025) of `failed`/`awaiting_user` studies in `interface/render.py`; CLI error when no `Study` is created | ✅ | 2026-09-23, commit `9f13608`: `render_study` produces the three-block failure render and an `awaiting_user` render. Verified now: `test_render.py` parametrises every `StepErrorKind`; `test_main.py` covers both CLI paths |
| E5.12 | Domain change (ADR-0027): `Arm`, `Contrast`, `Question.arms`/`contrasts`, `required_arms`/`reference_arms`, `AddEdge.edge_id`, `arm` on plan/experiment types | ✅ | 2026-09-23, commit `cfb9711`: `domain/value_objects/arm.py`, `Question.arms`/`.contrasts` with `effective_arms`/`effective_contrasts`. This task's own scope is domain-only, met: `test_arm.py` + `test_experiment_design.py`. ADR-0027 itself is now **Accepted** (2026-09-25, E5.13, ✅) |
| E5.13 | *(new 2026-09-24)* Accept or change-then-accept ADR-0027 (arms and contrasts), roots E3.7, E5.2, E5.4, E9.8 | ✅ | 2026-09-25, commit `c912797`: `docs/adr/0027-experiment-arms-and-contrasts.md`'s status line now reads "Accepted (2026-09-24, E5.13, with the contrast-direction rule added to §1)". The change resolved during acceptance: of two nested arms, the one contained in the other is always the reference regardless of how a request wrote the contrast (`Question.effective_contrasts` now orients every such pair). The blind annotation for E5.1 had written two of three multi-arm contrasts backwards, and both had scored as correct under the old rule. Planning/plan-validation use is now live (the domain planner applies `effective_contrasts`/`effective_arms` directly, delivered by r13 in place of the cancelled E5.2); Expert/Composer use (E5.3/E5.4) remains pending. This task's own scope (accept, or change-then-accept) was already met |
| E5.14 | *(new 2026-10-01, from the E3.7 grilling, ADR-0037)* Refactor of what E5.9/E5.10 built: `GenerateNetworkStep`/`GenerateDemandStep` → `obtain_network`/`obtain_demand`; `StudyPlan` loses `reused` and zero-step plans; the `NeedsUser` outcome renders via E5.11; Executor looks a scenario up by hash before building; study window derived by code | ✅ | 2026-10-02, five commits (`e371a60`/`8551b8d`/`ab3dcfa`/`7d4a4d8`/`b08973d`), each ticketed to one piece of the ADR-0037 refactor: `obtain_network`/`obtain_demand` plan steps, the study window derived by code, `NeedsUser` leaving the `Study` in `awaiting_user`, scenario reuse found by the Executor via a hash lookup instead of planned (`StudyPlan.reused` dropped), and the class diagram/contract docs regenerated to name the specialist. Verified now: `GenerateNetworkStep`/`GenerateDemandStep` no longer appear anywhere in `src/`, `NeedsUser` exists in `domain/value_objects/outcomes.py`, and dedicated tests back every piece (`test_obtain_steps.py`, `test_needs_user.py`, `test_scenario_lookup.py`, plus `test_experiment_design.py` for the window). Meets the task's own Done bar (unit tests on both outcomes and on the lookup, schemas and `docs/class_diagram.md` regenerated) |
| E5.15 | *(new 2026-10-06, refactor r13/ADR-0039, 3 → 1 pts by r14)* Verification after r13 (PR #20): search the code, published schemas, `GLOSSARY.md` and the indexes for leftovers of the Coordinator (`CoordinatorAgent`, `StudyPlan \| Clarification`, the clarification `Phase` field, adapter/tool placeholders, the composition-root slot, `allow_script`); regenerate schemas; add the thesis architecture text if still missing | ⬜ | Not started; no commit mentions E5.15. Checked now: `docs/tfm-architecture-and-dod.md` §2.4's agent table still lists "Coordinator" as a live row with `StudyPlan` output, and still names `allow_script` as part of `ScenarioTask` for the Scenario Builder. `git log` on that file stops at `2d83178`, before r13 landed. This is exactly the kind of leftover this task's own DoD asks to find. It has not been run yet |

## E6 — Network Author (42 pts, 2 tasks) · DoD §4.3

| ID | Task | Status | Notes |
|---|---|---|---|
| E6.1 | Network Author Minimal (agent): OSM snapshot → `netconvert` → `Network` with recipe; v1 tool catalogue + `probe_run`; now also resolves `network_ref` (ADR-0037: `find_network`, `Found`/draft/`NeedsUser`) | ⬜ | Wave 3. Domain side done (`NetworkRecipe`, `TopologyModification`, `ProbeReport`); ports defined. Checked now: `adapters/llm/agents/network_author.py` and `application/tools/network_author.py` are both still 4-line placeholders. 2026-10-01: ADR-0037 adds `network_ref` resolution to this task's scope (16→18 pts); still ⬜ |
| E6.2 | Network Author Done (sanity + probe, 10/10 GEN-LOCATIONS, replay determinism, agent stability, derivation bank) | ⬜ | Wave 3 (build) / measured in V2 |

## E7 — Demand Generator (65 pts, 6 tasks) · DoD §4.4

| ID | Task | Status | Notes |
|---|---|---|---|
| E7.1 | Demand Generator Minimal (agent): `randomTrips` + `duarouter` → trips + routes; `reroute_demand`; now also resolves `demand_ref` on the resolved network (ADR-0037) | ⬜ | Wave 3. Checked now: `adapters/llm/agents/demand_generator.py` and `application/tools/demand_generator.py` both still 4-line placeholders. 2026-10-01: ADR-0037 adds `demand_ref` resolution to this task's scope (10→13 pts); still ⬜ |
| E7.2 | *(new 2026-10-01, ADR-0036)* Raw demand data: `RawDemandData` aggregate, DatabaseMCP `raw_demand_data` group (`list_demand_data`/`get_demand_data`/optional `store_demand_data`) replacing `historical_demand`, SQLite backend + conformance | ⬜ | Wave 3. New today; `DATABASE_MCP_CONTRACT.md` gained a pointer to ADR-0036 but is, by its own text, "not edited until E7.2". No code found this review |
| E7.3 | *(new 2026-10-01, ADR-0036)* `od_matrix` content (`ZoneMap`, edge roles `source`/`sink`/`both`) and the Demand Generator's OD-matrix-to-`Demand` path via a `kind → fitter` registry | ⬜ | Wave 3. New today, depends on E7.2. No code found this review |
| E7.4 | Demand Generator Done (calibration loop to fidelity ±15%/±25% with evidence, history-driven, reroute test) | ⬜ | Wave 3 (build) / measured in V2 |
| E7.5 | *(new 2026-10-01, ADR-0036)* External demand-data import: `resto import` for counts (CSV) and OD (CSV + SUMO TAZ file), checked against the network; same content under another description is a conflict | ⬜ | Wave 5. New today, depends on E7.3. No code found this review |
| E7.6 | *(new 2026-10-01, ADR-0036)* `flows` content (a measurement over a whole edge) and its fitting path in the generator; lowest priority of the four | ⬜ | Wave 5. New today, depends on E7.3. No code found this review |

## E8 — REAL-NET (60 pts, 5 tasks) · DoD §4.7 (REAL-NET), assets

| ID | Task | Status | Notes |
|---|---|---|---|
| E8.1 | REAL-NET: choose district, hand-clean on plain XML, freeze, log every fix | ⬜ | Wave 1b (no prerequisite, "can start any week"; falls back to wave 3 if missed). No `real-net.*` files found in the repo this review |
| E8.2 | Demand profiles low/peak/incident on REAL-NET (clock-time, ADR-0028) | ⬜ | Wave 4 |
| E8.3 | Scenario matrix REAL-NET/peak | ⬜ | Wave 4. Depends on E8.1 (REAL-NET frozen) |
| E8.4 | Question bank REAL-NET (40+) | ⬜ | Wave 4. Depends on E8.3 |
| E8.5 | Port to REAL-NET, full benchmark | ⬜ | Wave 4 |

## E9 — Integration (62 pts, 8 tasks, 1 Stretch) · DoD §5

| ID | Task | Status | Notes |
|---|---|---|---|
| E9.1 | Golden-path test framework; GP-1…GP-5 and GP-9 (moved here in v0.3) | ⬜ | Wave 1b. No `golden/` directory or golden-path test framework found in the repo this review |
| E9.2 | GP-6 (dynamic path) and GP-7 (compare) | ⬜ | Wave 2 |
| E9.3 | Failure-injection suite across golden paths (incl. script lint/dry-run, agent budget) | ⬜ | Wave 5 |
| E9.4 | Cost/latency per golden path recorded | ⬜ | Wave F, reads V2 traces per E9.5. 2026-09-29 (`e064862`): `Usage.cost_usd` now carries OpenRouter's real per-study cost next to the estimate, so a trace can show it once golden paths exist. The measurement itself still waits on E9.1/E9.5 |
| E9.5 | Full run: 11/11 golden paths × 3 → V2 measurement | ⬜ | Wave F |
| E9.6 | Code freeze: tag, README, reproducibility package (packaging only after feature freeze, v0.3 scope change) | ⬜ | Wave F, deadline Wed 10 Feb |
| E9.7 | *(Stretch)* usability session with 2–3 DLR engineers | ⬜ | Not counted — only attempted if M7 lands on time |
| E9.8 | GP-8 (new place name) and GP-11 (add an edge) passing | ⬜ | Wave 3. Depends on E6.1, E7.1, E5.13 (ADR-0027) |

## E10 — Thesis document (120 pts, 8 tasks) · rolling, concentrated 1 → 18 Feb

| ID | Task | Status | Notes |
|---|---|---|---|
| E10.1 | Outline + state-of-the-art chapter | ⬜ | Wave W (Oct) |
| E10.2 | Architecture & contracts chapter | ⬜ | Wave W (Nov), once ADR-0027 is settled and the planner spine (E3.7 → E5.15 → E5.3, ADR-0039) closes |
| E10.3 | Evaluation methodology chapter | ⬜ | Wave W, before V1 |
| E10.4 | Module sections written at each Done | ⬜ | Wave W, rolling |
| E10.5 | Results chapter | ⬜ | Wave F |
| E10.6 | Discussion, limitations, conclusions | ⬜ | Wave F |
| E10.7 | Full draft to supervisors; revision round | ⬜ | **M8**, 18 Feb (v1) / M9 window (v2, not planned) |
| E10.8 | Final delivery | ⬜ | **M9**, May 2027 (TBC), recorded not planned |

---

## Milestone status

M2–M7 are **build milestones**: met when every task they list is ✅ or ⏳ (v0.4 §0.2, §2). Their
measurement happens in Validation 2. Plan v0.4 renumbered M3–M9; the equivalence is in the work plan §8.

| ID | Target | Deadline | Milestone | Status | Notes |
|---|---|---|---|---|---|
| M0 | Fri 18 Sep | Fri 18 Sep | Foundations frozen | ✅ | 2026-09-14, 4 days early: all 8 E0 tasks ✅, CI green on `master`, DEV-NET runs its three demand profiles, architecture v1.0 frozen |
| M1 | Fri 16 Oct | Fri 16 Oct | Tooling complete | ✅ | 2026-09-15, a month early: E1 fully ✅, E2.1/E2.2 (Runner/Builder Minimal) ✅, E3.1 (20×3 scenario matrix stored via real DatabaseMCP) ✅ |
| M2 | Tue 20 Oct | Fri 13 Nov | Expert built on DEV-NET | ✅ | 2026-09-25: E3.8 ✅, E4.2/E4.3/E4.4 ⏳ (dev sweep on the E3.8 bank meets every DoD bar), E4.5 ⏳ (EXP-01 ready to run in V2). Every listed task is ✅ or ⏳. 2026-10-01: the work plan re-baselined this milestone's target from Fri 9 Oct to Tue 20 Oct (deadline unchanged), a re-baselining rather than a slip, since M2 was already met and is now 25 days ahead of the new target instead of 11. The measurement itself (EXP-01, all four §4.7 families at full scale) still runs in Validation 2, per the build/measurement split this milestone type is defined around |
| M3 | Mon 26 Oct | Fri 27 Nov | Planner loop built | ⬜ | Needs E5.13, E3.11, E3.7, E5.14, E5.15, E5.3, E5.4 ✅ (or ⏳) and GP-1…5/GP-9 passing (E9.1); E5.2 is cancelled, r14, since the planner is r13's, delivered. E5.13/E3.11/E5.14 ✅. 2026-10-06: r13 (ADR-0039) delivers the planner itself, removing what used to be this milestone's biggest open risk, an agent that routes from a live model. The spine's remaining work is now the E3.7 human review, E5.15's leftover search, the zero-redundant-simulations counter on E5.3, E5.4's placeholder, and E9.1's golden-path framework, none of which exist yet. |
| M4 | Fri 6 Nov | Fri 11 Dec | Builder and Runner built | ⬜ | E2.5, E2.6 ✅, E2.7 ✅ or ⏳; GP-6 and GP-7 passing (E9.2). Renumbered by plan v0.4 (§8); the next `progress-review` refreshes the evidence. |
| M5 | Mon 30 Nov | Fri 15 Jan | Generators built | ⬜ | E6.1, E7.1, E3.12, E7.2, E7.3 ✅; E6.2, E7.4 ✅ or ⏳; GP-8 and GP-11 (E9.8). Renumbered by plan v0.4 (§8); the next `progress-review` refreshes the evidence. |
| M6 | Tue 8 Dec | Fri 22 Jan | REAL-NET ready (built) | ⬜ | E8.1 frozen; E8.2, E8.3, E8.4 ✅; E8.5 ⏳. Renumbered by plan v0.4 (§8); the next `progress-review` refreshes the evidence. |
| M7 | Fri 15 Jan (~~Fri 11 Dec~~) | ~~Fri 5 Feb~~ Fri 29 Jan | All modules built | ⬜ | E5.6, E5.7 (checker), E9.3, E7.5, E7.6 ✅ or ⏳; E4.9 ⏳ (setup); 11 golden paths as tests. E5.5 is cancelled (r14): its failure-injection half is now E9.3's, its zero-redundant-simulations half is E5.3's. Renumbered by plan v0.4 (§8); the next `progress-review` refreshes the evidence. |
| V1 | Mon 14 → Fri 18 Dec | Fri 18 Dec | Validation 1 | ⬜ | Reduced checkpoints of every module built by 11 Dec on dev splits, interim figures. Wave 5 is not in V1 |
| FF | Fri 22 Jan | Fri 29 Jan | Feature freeze | ⬜ | No behaviour change after it |
| V2 | Mon 25 → Fri 29 Jan | Fri 5 Feb | Validation 2 | ⬜ | Every measurement suite run once at definitive size, held-out included |
| M8 | Thu 18 Feb | Thu 18 Feb | End of full-time work | ⬜ | Code frozen/tagged, V2 done, results chapter written, full draft v1 to supervisors |
| M9 | May 2027 (TBC) | — | Delivery | — | Recorded only, not planned in v0.4 (revision round, final delivery, defense prep) |

---

## Update ritual

Update this file whenever a task's status changes (not just on the Friday ritual from `tfm-work-plan.md`
§6) — flip its ⬜/🔄/⏳/🚧 and refresh the summary line at the top. A task only becomes ✅ once it meets
its DoD in the pass that measures it (never just because related code exists), and a ⏳ task turns ✅
only on its measurement suite's result in Validation 1 or 2.
