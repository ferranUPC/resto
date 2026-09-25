# Progress tracker

Tracks completion of every task in [`tfm-work-plan.md`](tfm-work-plan.md) (**v0.3**, re-baselined
2026-09-24). Task descriptions here are shortened for scanning — the source of truth for scope, points
and due dates is `tfm-work-plan.md` §1, and for DoD thresholds `tfm-architecture-and-dod.md` §4.x.

Status (decided 2026-09-24, wayfinder #3 — exact wording, applied by the `progress-review` skill):

- ⬜ not started · 🔄 in progress · ✅ done.
- ⏳ **awaiting measurement**: the work is built and every development run it needs has been done; the
  only thing between it and ✅ is a measurement suite in `docs/evaluating-resto.md` §7.2, which runs in
  Validation 1 or 2. The Notes name the suite and say whether the development evidence (e.g. a
  1-repetition sweep) already meets the threshold. A deferred paid run is never a reason for 🚧.
- 🚧 **blocked**: cannot proceed for a stated reason outside our control (an external person, data or
  service); the Notes say what unblocks it.

Last updated: 2026-09-25

**Summary: 29 / 76 tasks done (38.2 %), 3 awaiting measurement, 1 in progress, 0 blocked** (⏳: E4.5,
E4.7, E5.1 — 36 of 954 pts, counted apart from done; 🔄: E5.3; E7.7 is Stretch, never scheduled —
excluded from the count, per work plan §5). The denominator grows from 72 to 76: v0.3 re-baselined the
plan (`b9dead2`) and added four tasks — E3.8 (ADR-0028 clock-time migration), E3.9 (evaluation budget
doc), E3.10 (Decisions-log trim), E5.13 (accept/change ADR-0027) — none built yet.

Since the last review (`92beb2c`, 2026-09-24) four commits landed: `32a5cd5` tunes the Input Parser
v4→v6 and runs it once on held-out (`v6-heldout`: every per-run threshold met, but `intent` agreement
across 3 runs is 93.9 % < the 95 % bar, so **E5.1 is not Done**; a second, final held-out use is reserved
for Validation 2 per the new N4 rule) and adds inter-annotator infrastructure
(`eval/request_bank/annotation/`) used to settle the gold `intent` rule along the way; `dd816f2` and
`b9dead2` re-baseline the plan to v0.3 (story points, the ⏳ status, build milestones with target +
deadline, the new tasks above, a fallback order); `24243ea` teaches the GitHub Pages progress site to
parse v0.3 (not a tracked task). **E4.5 and E4.7 move from 🚧 to ⏳**: under the new rule a deferred paid
run is never a reason for 🚧 — both were only ever blocked on the `EXP-01` cost, now explicitly deferred
to Validation 2, not on anything outside our control.

By plan points, 362 of 954 (37.9 %) are in ✅ tasks, 36 in ⏳, 14 in 🔄. Verified now (system Python 3.11
venv, no `resto` conda env in this container — `sumo` from the `eclipse-sumo` PyPI wheel put on `PATH`
instead): `pytest -q` 892 passed, 1 skipped (a fixture that needs a locally-generated, uncommitted run
directory); `ruff check .` clean; `mypy` clean (259 source files, per `pyproject.toml`'s `[tool.mypy]`
file list — `eval/dev-net/demand/sim_utils.py` is deliberately excluded there, pre-existing, unrelated to
this review). See `docs/feasability-analisis/2026-09-25.md`.

---

## E0 — Foundations (70 pts, 8 tasks) · DoD §2

| ID | Task | Status | Notes |
|---|---|---|---|
| E0.1 | Repo skeleton: hexagonal layout, packaging, ruff, pytest, CI | ✅ | 2026-09-11: layout restructured to architecture v0.3 (`domain/`, `application/{ports,use_cases,tools,schemas.py}`, `adapters/{llm,sumo,sandbox,web,persistence,tracing}`, `interface/{mcp,cli}`, `eval/`); placeholders for every module; 28 tests green, `ruff check .` clean. `ci.yml` already targets `master`; not yet pushed, so still no workflow run to confirm CI green. 2026-09-13: pushed; `gh run list` shows 3 CI runs on `master` (`1d1578b`, `a0e1fa2`, `554086c`), all `success` → output "repo + green CI" met (closed 11 Sep, 1 day after its 10 Sep due date) |
| E0.2 | Pin SUMO 1.27.1 from PyPI; reproducible environment incl. Postgres + `pgvector`; record in README | ✅ | 2026-09-11: SUMO 1.27.1 pinned as `pyproject.toml` dependencies, installed and verified in the `resto` env; README rewritten. 2026-09-14: the Postgres + `pgvector` service is no longer part of the design — ADR-0012 (architecture v1.0, A1) moves the DatabaseMCP reference backend to SQLite + in-process cosine. The residual paper-cut noted in an earlier review is fixed: commit `749b393` rewrote the stale "Postgres + `pgvector`" wording in `tfm-work-plan.md` E0.2/E1.3 to describe the SQLite backend |
| E0.3 | Domain dataclasses (aggregates, value objects, tasks, drafts) + `schemas.py` TypeAdapters, JSON-schema export, round-trip tests | ✅ | 2026-09-14: committed in `32672d5`. Six aggregates + value objects incl. `drafts.py` (`NetworkDraft`/`DemandDraft`/`ScenarioDraft`/`ExpertNoteDraft`), `schemas.py` TypeAdapters, 18 files in `schemas/` with a drift test, `test_serialisation.py` round-tripping every domain dataclass, `test_drafts.py`. Verified now: `pytest` 186 passed, `ruff check .` clean, CI green on `master` (run `34816761408`) |
| E0.4 | DatabaseMCP contract spec (six capability groups incl. `demands`, `query_edgedata`; error codes) | ✅ | 2026-09-14: `docs/DATABASE_MCP_CONTRACT.md` committed (`0ea81ac`, CI green). Six capability groups (§5.1–5.6), error codes (§7), conformance checklist (§8, for E1.5 to implement against), SQLite reference impl (§9). §10 open points 1–2 resolved by architecture amendment A2 (`Network.label`, note-ranking as a pure domain algorithm — ADR-0013/0014); open point 3 (`historical_demand` shape) is *deliberately* left open until E6.5 per the doc's own text, not a gap in this task. Cosmetic-only issue: the file's own title/header still literally read "v1.0-draft" despite the architecture freeze — worth a one-line fix, doesn't affect content completeness |
| E0.5 | DEV-NET: grid + hand edits (bottleneck, signalised corridor) | ✅ | 2026-09-14, commit `5e48e03` (CI green): `netgenerate` 5×5 grid, scripted (`generate.sh`, reproducible, no manual GUI edits), 2→1 lane merge bottleneck on `B0C0`→`C0D0` isolated from the row-2 signalised corridor (5 TLS junctions), 0 U-turn connections, fully strongly connected — all verified and documented in `eval/dev-net/README.md` with concrete counts (80 edges, 25 nodes, one expected `netconvert` warning) |
| E0.6 | Demand profiles low/peak/incident on DEV-NET (trips + routes) + synthetic counts at control edges | ✅ | 2026-09-14, commit `e5f1ef5` (CI green): `low`/`peak`/`incident` trips+routes (seed 1), `control_counts.json` at 5 control edges, `verification.ipynb` sweeping simulation seeds 1–9 per profile. `peak` measured at 16.5% mean congestion (inside the 10–20% target), `incident` isolates the `B0C0` bottleneck (26× peak occupancy). Not reopened for the ADR-0028 clock-time move — that migration is E3.8, still ⬜; this task's own output (seconds-based demand, verified) still meets its own Done bar |
| E0.7 | Trace logging: run id, step, tool call, artifacts, tokens → JSONL | ✅ | 2026-09-14, commit `bcca11c` (CI green): `Tracer` port + `JsonlTracer` adapter (`{root}/{study_id}.jsonl`, one JSON object per line, tolerates dataclasses/`Enum`/`Path` payloads). `test_jsonl.py` covers ordering, per-study isolation, unknown-study read, and payload serialisation of `StepStatus`/`Usage`/`Path` — 5 tests, all passing |
| E0.8 | Architecture doc frozen as v1.0 + ADRs for §7 decisions | ✅ | 2026-09-14, commit `7745324` (CI green): `tfm-architecture-and-dod.md` header now reads "v1.0 — Status: frozen (2026-09-14, E0.8/M0)"; 14 ADRs under `docs/adr/` (0001–0014) with an index (`README.md`); §9 amendments A1/A2 reconciled into the body and superseded as prose by their ADRs |

## E1 — MCP servers and `traci_api` (94 pts, 6 tasks) · DoD §4.9

| ID | Task | Status | Notes |
|---|---|---|---|
| E1.1 | NetworkMCP (7 read tools + tests incl. error case) | ✅ | 2026-09-14, commit `daf304d` (CI green): all 7 tools (`get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`, `edges_in_bbox`, `capacity_estimate`, `get_tls`) live as `application/tools/network.py` functions, wrapped by `interface/mcp/network_server.py` (ADR-0009: MCP layer is protocol plumbing only). Coverage is layered rather than duplicated per file: `tests/unit/adapters/sumo/test_netxml.py` carries the real ≥3-tests-incl.-error-case bar per method (25 tests, every one of the 7 query methods plus `has_edge`/`has_lane`/`has_tls` has an explicit unknown-id `KeyError` case), `tests/unit/application/tools/test_network.py` (10 tests) checks delegation + `Tool` wrapping, `tests/unit/interface/mcp/test_network_server.py` (4 tests) checks the server wires those tools and surfaces an unknown-id error as `UnexpectedToolError`. Verified now: full suite green |
| E1.2 | `traci_api` (8 primitives + `at_time`/`when` + `applied_actions`) and TraciMCP over it | ✅ | 2026-09-14, commit `4301d1c` (CI green): `adapters/sumo/traci_api.py` has all 8 primitives (`close_lane`, `open_lane`, `set_speed`, `set_tls_program`, `get_edge_occupancy`, `get_edge_speed`, `get_vehicle_count`, `step`) plus `at_time`/`when`/`run`/`applied_actions`/`registered_rules`, each `AppliedAction` tagging `origin=CODE` vs `origin=RULE`. `interface/mcp/traci_server.py` exposes the 8 primitives over MCP (deliberately not `at_time`/`when`, documented reasoning: callables can't cross the JSON wire — a design call, not a gap). `tests/unit/adapters/sumo/test_traci_api.py` (20 tests) runs with a **real SUMO/traci session** against DEV-NET, not mocks — covers every primitive, an unknown-id `TraciException` case for the mutating ones, `at_time` firing once, `when`'s rising-edge semantics, `origin` tagging, and `run(until=...)`. `test_traci_server.py` (3 tests) + `test_traci_api_facade.py` (35 tests) round it out |
| E1.3 | DatabaseMCP reference impl (SQLite + in-process cosine, ADR-0012; six capability groups incl. `demands`) + `mcp_client` adapter | ✅ | 2026-09-14, commits `1a3c930` + `8ee4380` (CI green): `adapters/persistence/sqlite/repositories.py` implements the 5 required capability groups (`networks`, `demands`, `scenarios` incl. `find_similar_scenario`, `results` incl. `query_edgedata`, `notes` incl. `search_notes`) over `interface/mcp/database_server.py` (17 tools, contract error codes as `"CODE: message"`-prefixed `ToolError`s per §7). `adapters/persistence/mcp_client.py` speaks *real* MCP (`ClientSession` over any `mcp.client` transport, sync/async bridging documented in-file) rather than calling the server in-process — this is what the conformance suite (E1.5) actually exercises. `historical_demand` (6th, optional group) is deliberately unimplemented, per contract §10 point 3, deferred to E6.5 — not a gap in this task. Tests: 25 in `test_repositories.py`, 18 in `test_mcp_client.py`, 8 in `test_database_server.py` |
| E1.4 | `find_similar_scenario` + `search_notes` + `query_edgedata` (10 + 5 + 5 test cases) | ✅ | 2026-09-14, commit `8ee4380` (CI green): the 10+5+5 bar is met in `conformance/` (run through the real `mcp_client` adapter, per §4.9's own framing of this bar as a conformance requirement): `test_find_similar_scenario.py` 10 tests, `test_search_notes.py` 5 tests, `test_query_edgedata.py` 5 tests. Additional unit-level coverage in `test_repositories.py` (5 find_similar + 5 search_notes) and `test_edgedata.py` (8 tests) |
| E1.5 | DatabaseMCP conformance suite | ✅ | 2026-09-14, commit `8ee4380` (CI green): `conformance/` (56 tests) is parametrized over every DatabaseMCP backend the project ships (`_BACKENDS` dict, currently `sqlite-reference`) and reaches every backend only through `interface/mcp/database_server.py` + `adapters/persistence/mcp_client.py` over a real (in-memory) MCP `ClientSession`, never a backend's repository classes directly |
| E1.6 | Capability-listing helper for Coordinator; latency benchmark | ✅ | 2026-09-14, commit `c77692b` (CI green, verified now): `application/capability_negotiation.py` derives capability groups from a backend's advertised tool names (`capabilities_of`) and hard-fails start-up on a missing required one (`negotiate_capabilities`, `MissingRequiredCapabilityError`), with `historical_demand` treated as optional per contract. `eval/benchmarks/latency.py` + `eval/benchmarks/latency-report.md`: all 32 MCP tools benchmarked at 50 reps each on DEV-NET, every one well under the §4.9 <1s threshold (slowest 4.84 ms max) |

## E2 — Scenario Builder & Simulation Runner (110 pts, 7 tasks) · DoD §4.5, §4.6

| ID | Task | Status | Notes |
|---|---|---|---|
| E2.1 | Runner batch mode (+ ephemeral mode for probe/calibration) + reproducibility test (20 runs) | ✅ | 2026-09-15, commit `1e23009` (CI green, verified now): `adapters/sumo/runner.py`'s `SubprocessSumoRunner.run_batch` derives a run cfg, runs `sumo -c`, collects edgedata/tripinfo/statistics/summary as `ArtifactRef`s. `application/use_cases/run_simulation.py`: `run_simulation` computes `result_id = hash(scenario_id, seed, mode, sumo_version)` before running, returns an existing *ok* result unrun; `run_ephemeral` is the unstored probe/calibration path. `test_twenty_runs_with_the_same_seed_are_byte_identical` runs 20 real SUMO batch runs and asserts a single distinct content-hash tuple. Online mode (`run_online`) still raises `NotImplementedError`, correctly deferred to E2.5 |
| E2.2 | Builder Minimal (agent + writer tools): static `lane_closure`/`speed_limit` → `.add.xml` + `sumocfg` | ✅ | 2026-09-15, commit `ee85dad` (CI green, verified now): `adapters/llm/agents/scenario_builder.py` assembles the `AgentTask`/tool list/budget and calls the shared `ToolAgent` port; system prompt restricts it to `lane_closure`/`speed_limit` on a single lane with a fixed window, "no silent coercion" (ADR-0007). `application/tools/scenario_builder.py` binds real `Tool`s; `application/use_cases/build_scenario.py::build_scenario` promotes an `AgentRun[ScenarioDraft]` in the DoD §2.4 order. Real `OpenRouterToolAgent` (`adapters/llm/anthropic_client.py`) wired with `RESTO_LLM_DEFAULT_MODEL=deepseek/deepseek-v4.1-flash` as the hard default per CLAUDE.md's cost policy |
| E2.3 | Builder static: `edge_closure`, `signal_program` (WAUT), `demand_scale` | ✅ | 2026-09-15, commit `7ad97c5` (verified now): rerouter writer dispatches on `edge_closure` (with `disallow="all"` fixed in `bc46212`), `write_tls_program` for static `signal_program`/WAUT, `scale_demand` (deterministic resample + `duarouter`) for `demand_scale`. Covered end-to-end by the E3.1 matrix against real SUMO |
| E2.4 | Effect-verification harness | ✅ | 2026-09-15, commit `bc46212` (verified now): `verify/effects.py` implements the DoD §4.5 checks (edge flow, completion rate, speed limit, signal-program coverage+revert, demand-scale departed count), one `test_*.py` per intervention type running the real `SubprocessSumoRunner` against DEV-NET. `pytest -q conformance/ verify/` → 61 passed (verified now, still green) |
| E2.5 | Runner online mode: `ScriptSandbox` (lint, dry-run, subprocess) + 10 script test cases | ⬜ | Wave 2. Replaces the v0.2 `TraciPlan` interpreter. No commits since the last review; still not started. Work plan flags this as having no fallback: "without it GP-6 and the script half of §4.5 cannot pass" |
| E2.6 | Builder scripts: `condition` → `when(...)`, `custom` interventions, `rejected[]` | ⬜ | Wave 2. Depends on E2.5 |
| E2.7 | Builder bank (25–30 specs incl. `custom`) run to ≥27/30 | ⬜ | Wave 2 (build) / measured in V2. Depends on E2.5, E2.6 |

## E3 — Evaluation assets & harness (94 pts, 10 tasks)

| ID | Task | Status | Notes |
|---|---|---|---|
| E3.1 | Scenario matrix DEV-NET/peak (15–25 rows × 3 seeds) | ✅ | 2026-09-15, commit `3900171` (verified now): `eval/scenario_matrix/` hand-authors 20 rows × 3 seeds = 60 `SimulationResult`s, promoted through the real `build_scenario`/`run_simulation` use cases and stored through an actual MCP `ClientSession`. Each row's DoD §4.5 effect is re-checked before it counts as built. **Rebuilt in clock time by E3.8 (⬜, not started); this task is not reopened** — its own output (seconds-based matrix, checks passed) still meets this task's own Done bar |
| E3.2 | Question templates + generator + gold answers (≥60 on DEV-NET) | ✅ | 2026-09-17, commit `10c85a6`: 117 questions on DEV-NET/peak (floor: 60) — 40 descriptive, 20 diagnostic, 57 counterfactual — over the E3.1 20-row matrix. Verified now: `question-bank.json` has exactly 117 entries. **Rebuilt in clock time by E3.8 (⬜); not reopened**, same reasoning as E3.1 |
| E3.3 | Metrics harness (exact match, Jaccard, direction, band, Brier, abstention P/R) | ✅ | 2026-09-17, commit `2a9d3cd`: `eval/expert_benchmark/` scores exact-set/±5%/Jaccard≥0.6/direction/band/Brier against DoD §4.7 thresholds, mean±std, report generation. 2026-09-22, commit `12276fb`: `abstention_recall`/`abstention_false_requests` landed (thresholds `>= 0.70`/`<= 0.30`), covered by `test_expert_abstention.py`. The harness implements every metric family this task lists — the *measured* threshold on real data is E4.5/E4.7's job (now ⏳, gated on the EXP-01 Validation-2 run), not this task's |
| E3.4 | Request bank (text → `Question`, Input Parser): concepts expanded by variants, dev/held-out split by concept | ✅ | 2026-09-23, commits `1f21429`/`398129d` (bank built, 65 concepts → 306 requests). Since the last review, `32a5cd5` (2026-09-24) grew it further while settling the `intent` convention with the user (see E5.1): six new `run` concepts (R066–R071) and two new `diagnose` concepts (R072/R073) so every `intent` is represented in both splits. Current size (`eval/request_bank/bank.py`, `parser-tuning-log.md`): **73 concepts, 346 requests, 232 dev / 114 held-out (33 %)**. This is normal bank maintenance on a task already meeting its Done bar (concepts × variants, reviewed, frozen with provenance), not scope creep — the split stays fixed by concept (a test pins the pre-existing concepts' side) |
| E3.5 | Scenario matrix REAL-NET/peak | ⬜ | Wave 3. Depends on E6.3 (REAL-NET frozen) |
| E3.6 | Question bank REAL-NET (40+) | ⬜ | Wave 4. Depends on E3.5 |
| E3.7 | Plan bank (`Question` → `StudyPlan`, Coordinator): gold phase-0 plan per E3.4 request for a fixed DB state, the 4 canonical DB states, ADR-0025/0027 plan rules | ⬜ | Wave 1b. Nothing built yet. Blocked on two prerequisites per the v0.3 build DAG: E3.8 (clock-time migration, ⬜ — the "fixed DB state" this task plans against) and E5.13 (accept/change ADR-0027, ⬜ — arms/contrasts still *Proposed*). E3.4's gold `Question`s (its other input) are ✅ |
| E3.8 | *(new 2026-09-24)* ADR-0028 migration to clock time: DEV-NET demands `[0,3600)` → `[28800,32400)` (08:00–09:00), scenario matrix and question bank rebuilt in clock time, `verify/` and the expert-benchmark bank loader updated | ⬜ | Wave 1a, first item on the Coordinator-spine critical path and a prerequisite for any Expert sweep (E4.2–E4.4) and for E3.7/E5.2. Checked now: `eval/dev-net/demand/*.trips.xml` still departs in `[0, 3600)` seconds (e.g. `depart="3597.00"`), `eval/question_bank/templates.py`'s `DEFAULT_WINDOW = TimeWindow(0.0, 300.0)` — the migration has not started. Work plan: "A sweep on the pre-ADR-0028 bank is paid again after the rebuild", so nothing downstream (E4.2–E4.4's dev sweeps, EXP-01) can legitimately reuse the old `v1-forced-1rep` sweep from before this review period |
| E3.9 | *(new 2026-09-24)* Evaluation budget document for supervisors: one row per measurement suite, cost vs the $30 cap | ⬜ | Wave 1b, due before the ~24 Oct funding request. No `docs/*budget*` file exists yet; `evaluating-resto.md` §7.2 still carries the table this task is meant to take over |
| E3.10 | *(new 2026-09-24)* Trim `evaluating-resto.md`'s Decisions log (§5) to one line per decision | ⬜ | Wave 1b. Checked now: §5 still has ~35 entries, several multi-paragraph (the `intent` convention history from this week's Parser tuning added more, not fewer) — not trimmed |

## E4 — Network Expert (166 pts, 11 tasks) · DoD §4.7 · research focus

| ID | Task | Status | Notes |
|---|---|---|---|
| E4.1 | Refactor v1 Expert onto `ToolAgent` (`ExpertTask` → `ExpertAnswer`); facts via tools; `evidence[]` | ✅ | 2026-09-17, commit `d7683b3` (ADR-0018): `ExpertTask` in, `ExpertAnswer` out, facts only through NetworkMCP + result tools, every tool call recorded in an `EvidenceLedger` so `ask_expert` rejects any unresolved `evidence[]` ref. Verified now: 39 tests pass across `test_expert.py` (agent), `test_ask_expert.py` (use case), `test_expert.py` (tools) |
| E4.2 | Descriptive questions: tune until a development sweep **on the E3.8 (clock-time) bank** meets ≥90 % (→ ⏳) | ⬜ | Wave 1a. An earlier sweep (`v1-forced-1rep`, pre-E3.8) already showed descriptive 1.00 ≥ 0.90 on the old seconds-based bank, but v0.3's own text is explicit that a sweep on the pre-migration bank does not count once E3.8 exists as a task — E3.8 is ⬜, so this stays ⬜ until a fresh dev sweep runs on the rebuilt bank |
| E4.3 | Diagnostic questions: tune until a development sweep on the E3.8 bank meets Jaccard ≥0.6, "why" ≥70 % (→ ⏳) | ⬜ | Wave 1a. Same reasoning as E4.2 — the old sweep's diagnostic Jaccard 0.70 ≥ 0.60 was on the pre-migration bank |
| E4.4 | Counterfactual, forced mode: tune until a development sweep on the E3.8 bank meets direction ≥75 %, band ≥50 % (→ ⏳) | ⬜ | Wave 1a. Same reasoning — the old sweep's cf-dir 1.00/cf-band 1.00 was on the pre-migration bank |
| E4.5 | Free mode: abstention policy, `proposed_experiment`. **Measured in V2** by EXP-01's free-mode leg | ⏳ | *(was 🚧; reclassified this review per the new rule — a deferred paid run is never a reason for 🚧, see legend)* 2026-09-22, commit `12276fb`: the abstention *policy* (`Mode.FREE`, `needs_simulation`, `proposed_experiment`, `ask_expert`'s mode checks) and the `eval/expert_benchmark` harness support to run/score it (`--mode {forced,free,both}`, pairing in `report.py`) are both built and tested. `e45-smoke` ($0.056, 4 questions × both modes) validated the harness end to end but gave no abstention signal by design (tiny sample). The DoD threshold (`abstention_recall ≥ 70 %`, `false_requests ≤ 30 %`) needs EXP-01 in Validation 2, after E3.8's migration and after E4.2–E4.4's dev sweeps establish forced-mode accuracy on the new bank |
| E4.6 | `ExpertNote` writing + RAG + status update; hygiene probes (20) | ✅ | 2026-09-22, commit `4b3f78d` (ADR-0024): `run_expert_note` + `write_note` promote against the round's `EvidenceLedger`; `update_note_status` confirms/refutes `Quantity` claims at ±5%. RAG wired into the agent prompt. `eval/hygiene_probes/`: 20 probes run for real (`hygiene-v1`, $0.112) — 0 violations, pass rate 1.00 ≥ 1.00 required |
| E4.7 | DEV-NET benchmark report from EXP-01 (V2): all §4.7 metrics, 3 runs, mean±std | ⏳ | *(was 🚧; reclassified this review, same rule as E4.5)* Wave F. `docs/expert-tuning-log.md` (report generation) and `parser`/`expert` benchmark tooling are implemented and unit-tested; the report itself needs the EXP-01 run, which needs E3.8's migration first (a report built on the pre-migration `v1-forced-1rep` sweep would need re-running anyway). Still also needs E4.2–E4.4 (accuracy-to-Done work) before it covers the DoD's full scope |
| E4.8 | Port to REAL-NET, full benchmark | ⬜ | Wave 4 |
| E4.9 | Learning-effect experiment (0/5/15/25, CIs, plot), moved to **DEV-NET** in v0.3 | ⬜ | Wave 4 (setup); measured in V2. No commits since the last review |
| E4.10 | Calibration analysis + ablation | ⬜ | Wave F |
| E4.11 | Notes per study: 0–3 `ExpertNoteDraft`s, `scenario_ref` allow-list, `provenance=simulation` rule | ✅ | 2026-09-23, commit `40b5e2c`: `ExpertNoteDraft.scenario_ref` + container; `write_note` checks every draft before storing any. Verified now: `test_write_note.py` — 12 tests covering simulation vs opinion provenance, predictions, allow-list rejection, atomic all-or-nothing storage |

## E5 — Input Parser, Coordinator, Executor, Output Composer (140 pts, 13 tasks) · DoD §4.1, §4.2, §4.8

2026-09-22, commit `7f16aed`: [ADR-0023](adr/0023-coordinator-split-deterministic-executor.md) splits the
single-agent Coordinator into an Input Parser agent (E5.1), a one-shot Coordinator agent (E5.2) and a
deterministic Executor (`run_study`, E5.10). 2026-09-23: [ADR-0025](adr/0025-executor-plan-shape-intent-rules-and-failures.md)
and [ADR-0026](adr/0026-expert-notes-per-study-and-prediction-verification.md) complete the Executor
contract; [ADR-0027](adr/0027-experiment-arms-and-contrasts.md) (still **Proposed**, not Accepted — E5.13
is v0.3's task to resolve this) adds `Arm`/`Contrast` domain types (E5.12). The Input Parser is now a real
agent (E5.1), tuned to v6 and run once on held-out (missed the intent-agreement bar, see E5.1's row); the
Coordinator and Output Composer agents (`adapters/llm/agents/{coordinator,composer}.py`) are still 4-line
placeholder files, confirmed unchanged this review, and `interface/cli/main.py`'s composition root still
wires them to a `_Pending` stub.

| ID | Task | Status | Notes |
|---|---|---|---|
| E5.1 | Input Parser (own agent, ADR-0023): text → `Question`, no tools, retry-then-fail, `ambiguities[]` → `awaiting_user`; tuned on dev (§4.1 + arm structure ≥90%). **Measured in V2:** held-out, second use (N4) | ⏳ | 2026-09-23, commit `ed8be9b`, tuned further in `32a5cd5` (2026-09-24): `PARSER_VERSION` reached **v6** (`docs/parser-tuning-log.md`) after settling, with the user, the gold `intent` convention through two rounds of blind annotation (`eval/request_bank/annotation/`) — `intent` is now "what the user wants to know", never the verb or what it takes to answer. `v6-dev` (232 requests) meets every threshold: validity/interventions/topology/metrics 100 %, intent 99.4 %, ambiguity 97.7 %, arm structure 95.3 %. **Held-out run (`v6-heldout`, 114×3, $0.376) executed 2026-09-24**: every per-run threshold met (validity 100 %, intent 95.7 %, interventions 99.5 %, topology/metrics 100 %, ambiguity 82.2 %, arm structure 94.4 %) but **`intent` agreement across the 3 runs is 93.9 % (107/114), below the ≥95 % bar — E5.1 is not Done.** Per the new N4 rule (`evaluating-resto.md` §7.1), the held-out split is now spent for tuning; a second, final measurement (prompt frozen) is reserved for Validation 2 and reported next to this first result |
| E5.2 | Coordinator Minimal (ADR-0023): one `ToolAgent.run` per `Question` with read-only tools → typed `StudyPlan` or clarification; the 4 canonical DB states | ⬜ | Wave 1b. `application/ports/agents/coordinator.py` exists; `adapters/llm/agents/coordinator.py` confirmed still the 4-line placeholder this review. Depends on E3.8, E3.7, E5.13 per the build DAG |
| E5.3 | Loop closure (ADR-0023): `needs_simulation` → Coordinator plans → Executor runs → re-ask; `max_rounds`/`forced_by_limit`; multi-network `ExpertTask` (risk); GP-3/4/5 passing | 🔄 | 2026-09-23 (`6ccb66b`): the Executor-side mechanics are implemented and tested against fake ports (`test_gp3_counterfactual_free_plans_the_treatment_only_when_the_expert_asks`, `test_the_last_round_is_forced_by_the_limit`, etc.). Still missing: a real Coordinator agent (E5.2) to plan `proposed_experiment` from a live model, the multi-network `ExpertTask` fix v0.3 §4.4 flags as a named risk (`TODO(E5.3)` in `run_study.py`), and GP-3/4/5 as golden-path tests (E7.1, still ⬜) rather than unit tests with doubles |
| E5.4 | Output Composer Minimal (agent): closed `Study` → `Report` (claims with `evidence_refs`) → Markdown with evidence table | ⬜ | Wave 1b. `application/ports/agents/composer.py` exists; `adapters/llm/agents/composer.py` confirmed still the 4-line placeholder |
| E5.5 | Coordinator Done: routing ≥90% vs gold plan bank; zero redundant simulations; failure injection → named failing step. **Measured in V2** | ⬜ | Wave 5. Depends on E5.2, E3.7. The failure-classification half is already implemented and unit-tested in `run_study.py` (`StepError.kind` incl. `budget`) — real progress, not yet enough to flip this row |
| E5.6 | Capability negotiation with DatabaseMCP; GP-10 | ⬜ | Wave 5 |
| E5.7 | Output Composer Done: automatic traceability checker; faithfulness rubric on 20 V2 reports | ⬜ | Wave 5 (checker) / F (rubric) |
| E5.8 | Stability: 3 repeated runs of Input Parser + Coordinator benchmarks, read from V2 | ⬜ | Wave F. Parser half reads N4 (E5.1's second held-out use); Coordinator half reads E5.5's 3-rep run |
| E5.9 | Domain change (ADR-0023/0025): `Phase`, `Study.phases`, typed `PlanStep` union, `StepError`, `ExpertRound.forced_by_limit`; schemas regenerated | ✅ | 2026-09-23, commit `a3a363a`: `domain/entities/study.py` gains `Phase`/`Study.phases`, `domain/value_objects/study_plan.py` gains the discriminated `PlanStep` union. Schemas and `docs/class_diagram.md` regenerated same commit. Verified now: `test_study.py`/`test_study_plan.py` exercise the invariants directly |
| E5.10 | Executor (`run_study`, deterministic code): resolves `FromStep`, calls specialists, guards in code, runs `ask_expert`/`compose_report` itself; agent ports + composition root; note writer | ✅ | 2026-09-23, commit `6ccb66b` (976 new lines): parse → `Study` → per-phase plan → semantic validation → step execution → forced-last-round Expert loop → note writer → report, `StepError` classified into `user_input`/`budget`/`agent`/`infrastructure`. Verified now: `test_run_study.py` (965 lines, 29 test functions) covers GP-1/GP-2/GP-3-shaped scenarios, forced mode, every `StepError.kind`, budget accounting |
| E5.11 | Deterministic rendering (ADR-0025) of `failed`/`awaiting_user` studies in `interface/render.py`; CLI error when no `Study` is created | ✅ | 2026-09-23, commit `9f13608`: `render_study` produces the three-block failure render and an `awaiting_user` render. Verified now: `test_render.py` parametrises every `StepErrorKind`; `test_main.py` covers both CLI paths |
| E5.12 | Domain change (ADR-0027): `Arm`, `Contrast`, `Question.arms`/`contrasts`, `required_arms`/`reference_arms`, `AddEdge.edge_id`, `arm` on plan/experiment types | ✅ | 2026-09-23, commit `cfb9711`: `domain/value_objects/arm.py`, `Question.arms`/`.contrasts` with `effective_arms`/`effective_contrasts`. This task's own scope is domain-only, met: `test_arm.py` + `test_experiment_design.py`. ADR-0027 itself is still **Proposed** — E5.13 (new in v0.3) is the task to resolve that, and it is ⬜ |
| E5.13 | *(new 2026-09-24)* Accept or change-then-accept ADR-0027 (arms and contrasts) — roots E3.7, E5.2, E5.4, E6.7 | ⬜ | Wave 1a, right after E3.8 per the build DAG. Checked now: `docs/adr/0027-experiment-arms-and-contrasts.md`'s own status line still reads "Proposed — domain types implemented (E5.12); planning and plan validation pending" |

## E6 — Network Author, Demand Generator, REAL-NET (106 pts, 7 tasks) · DoD §4.3, §4.4

| ID | Task | Status | Notes |
|---|---|---|---|
| E6.1 | Network Author Minimal (agent): OSM snapshot → `netconvert` → `Network` with recipe; v1 tool catalogue + `probe_run` | ⬜ | Wave 3. Domain side done (`NetworkRecipe`, `TopologyModification`, `ProbeReport`); ports defined. Checked now: `adapters/llm/agents/network_author.py` and `application/tools/network_author.py` are both still 4-line placeholders |
| E6.2 | Demand Generator Minimal (agent): `randomTrips` + `duarouter` → trips + routes; `reroute_demand` | ⬜ | Wave 3. Checked now: `adapters/llm/agents/demand_generator.py` and `application/tools/demand_generator.py` both still 4-line placeholders |
| E6.3 | REAL-NET: choose district, hand-clean on plain XML, freeze, log every fix | ⬜ | Wave 1b (no prerequisite, "can start any week"; falls back to wave 3 if missed). No `real-net.*` files found in the repo this review |
| E6.4 | Network Author Done (sanity + probe, 10/10 GEN-LOCATIONS, replay determinism, agent stability, derivation bank) | ⬜ | Wave 3 (build) / measured in V2 |
| E6.5 | Demand Generator Done (calibration loop to fidelity ±15%/±25% with evidence, history-driven, reroute test) | ⬜ | Wave 3 (build) / measured in V2 |
| E6.6 | Demand profiles low/peak/incident on REAL-NET (clock-time, ADR-0028) | ⬜ | Wave 3 |
| E6.7 | GP-8 (new place name) and GP-11 (add an edge) passing | ⬜ | Wave 3. Depends on E6.1, E6.2, E5.13 (ADR-0027) |

## E7 — Integration (54 pts, 7 tasks, 1 Stretch) · DoD §5

| ID | Task | Status | Notes |
|---|---|---|---|
| E7.1 | Golden-path test framework; GP-1…GP-5 and GP-9 (moved here in v0.3) | ⬜ | Wave 1b. No `golden/` directory or golden-path test framework found in the repo this review |
| E7.2 | GP-6 (dynamic path) and GP-7 (compare) | ⬜ | Wave 2 |
| E7.3 | Failure-injection suite across golden paths (incl. script lint/dry-run, agent budget) | ⬜ | Wave 5 |
| E7.4 | Cost/latency per golden path recorded | ⬜ | Wave F |
| E7.5 | Full run: 11/11 golden paths × 3 → **M6** measurement | ⬜ | Wave F |
| E7.6 | Code freeze: tag, README, reproducibility package (packaging only after feature freeze, v0.3 scope change) | ⬜ | Wave F, deadline Wed 10 Feb |
| E7.7 | *(Stretch)* usability session with 2–3 DLR engineers | ⬜ | Not counted — only attempted if M6 lands on time |

## E8 — Thesis document (120 pts, 8 tasks) · rolling, concentrated 1 → 18 Feb

| ID | Task | Status | Notes |
|---|---|---|---|
| E8.1 | Outline + state-of-the-art chapter | ⬜ | Wave W (Oct) |
| E8.2 | Architecture & contracts chapter | ⬜ | Wave W (Nov), once ADR-0027 is settled and the Coordinator spine closed |
| E8.3 | Evaluation methodology chapter | ⬜ | Wave W, before V1 |
| E8.4 | Module sections written at each Done | ⬜ | Wave W, rolling |
| E8.5 | Results chapter | ⬜ | Wave F |
| E8.6 | Discussion, limitations, conclusions | ⬜ | Wave F |
| E8.7 | Full draft to supervisors; revision round | ⬜ | **M7**, 18 Feb (v1) / M8 window (v2, not planned) |
| E8.8 | Final delivery | ⬜ | **M8**, May 2027 (TBC), recorded not planned |

---

## Milestone status

M2–M6 are **build milestones**: met when every task they list is ✅ or ⏳ (v0.3 §0.2, §2). Their
measurement happens in Validation 2.

| ID | Target | Deadline | Milestone | Status | Notes |
|---|---|---|---|---|---|
| M0 | Fri 18 Sep | Fri 18 Sep | Foundations frozen | ✅ | 2026-09-14, 4 days early: all 8 E0 tasks ✅, CI green on `master`, DEV-NET runs its three demand profiles, architecture v1.0 frozen |
| M1 | Fri 16 Oct | Fri 16 Oct | Tooling complete | ✅ | 2026-09-15, a month early: E1 fully ✅, E2.1/E2.2 (Runner/Builder Minimal) ✅, E3.1 (20×3 scenario matrix stored via real DatabaseMCP) ✅ |
| M2 | Fri 9 Oct | Fri 13 Nov | Expert built on DEV-NET | ⬜ | Acceptance needs E3.8 ✅ and E4.2–E4.4 ⏳ (dev sweep on the E3.8 bank) and E4.5 ⏳ with EXP-01 ready to run — all three still ⬜/not-yet-⏳ as of this review; E3.8 itself (the wave-1a opener and this milestone's own critical path, "E3.8 → E4.4" = 34 pts) has not started. Target is 2 weeks out (today: 25 Sep); one working day into wave 1a since the v0.3 re-baseline, no cause yet to call the target at risk, but E3.8 needs to start now to hold it |
| M3 | Fri 6 Nov | Fri 11 Dec | End-to-end loop built | ⬜ | Needs E3.7, E5.2, E5.3, E5.4 ✅, GP-1…7+9 passing, Builder/Runner built. Of these, only domain/Executor groundwork (E5.9–E5.12) is ✅; the Coordinator and Composer agents are unbuilt placeholders, E7.1's golden-path framework doesn't exist, and E2.5–E2.7 (Runner online, Builder scripts/bank) haven't started. Critical chain per work plan §4.3 is 59 pts (E3.8→E3.7→E5.2→E5.3→E7.1→E7.2); target six weeks out |
| M4 | Fri 27 Nov | Fri 15 Jan | Real network ready (built) | ⬜ | Needs E6.1–E6.7 and E3.5; none started (all E6 agent files confirmed still 4-line placeholders this review). No prerequisite blocks E6.3 (REAL-NET freeze) from starting immediately per work plan §4.4 |
| M5 | Fri 4 Dec | Fri 29 Jan | Thesis result built | ⬜ | Needs E3.6 ✅, E4.8 ⏳, E4.9 ⏳ (setup). Depends on the E6.3→E6.6→E3.5→E3.6→E4.8 chain (60 pts), none of it started |
| M6 | Fri 11 Dec | ~~Fri 5 Feb~~ Fri 29 Jan | All modules built | ⬜ | Needs E5.5/E5.6/E7.3 ✅ or ⏳, E5.7's checker built, 11 golden paths passing as tests. Longest single chain in the whole plan (71 pts: E3.8→E3.7→E5.2→E5.3→E7.1→E6.7→E7.3) — the work plan's own "what to watch" calls the Coordinator spine "the critical path of the whole plan" and says to start it first |
| V1 | Mon 14 → Fri 18 Dec | Fri 18 Dec | Validation 1 | ⬜ | Reduced checkpoints of every built module on dev splits, interim only |
| FF | Fri 22 Jan | Fri 29 Jan | Feature freeze | ⬜ | No behaviour change after it |
| V2 | Mon 25 → Fri 29 Jan | Fri 5 Feb | Validation 2 | ⬜ | Every measurement suite run once at definitive size, held-out included, under the $30 cap |
| M7 | Thu 18 Feb | Thu 18 Feb | End of full-time work | ⬜ | Code frozen/tagged, V2 done, results chapter written, full draft v1 to supervisors |
| M8 | May 2027 (TBC) | — | Delivery | — | Recorded only, not planned in v0.3 (revision round, final delivery, defense prep) |

---

## Update ritual

Update this file whenever a task's status changes (not just on the Friday ritual from `tfm-work-plan.md`
§6) — flip its ⬜/🔄/⏳/🚧 and refresh the summary line at the top. A task only becomes ✅ once it meets
its DoD in the pass that measures it (never just because related code exists), and a ⏳ task turns ✅
only on its measurement suite's result in Validation 1 or 2.
