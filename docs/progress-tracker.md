# Progress tracker

Tracks completion of every task in [`tfm-work-plan.md`](tfm-work-plan.md). Task descriptions here are shortened for scanning — the source of truth for scope, outputs and DoD thresholds is `tfm-work-plan.md` (epics/hours/due dates) and `tfm-architecture-and-dod.md` (per-module DoD, §4.x).

Status: ⬜ not started · 🔄 in progress · ✅ done (meets its Done/threshold from the DoD, not just "code exists")

Last updated: 2026-09-15

**Summary: 16 / 65 tasks done (24.6%)** (E7.7 is Stretch, never scheduled — excluded from the count, per work plan §5)

---

## E0 — Foundations (8 tasks) · due 18 Sep

| ID | Task | Status | Notes |
|---|---|---|---|
| E0.1 | Repo skeleton: hexagonal layout, packaging, ruff, pytest, CI | ✅ | 2026-09-11: layout restructured to architecture v0.3 (`domain/`, `application/{ports,use_cases,tools,schemas.py}`, `adapters/{llm,sumo,sandbox,web,persistence,tracing}`, `interface/{mcp,cli}`, `eval/`); placeholders for every module; 28 tests green, `ruff check .` clean. `ci.yml` already targets `master`; not yet pushed, so still no workflow run to confirm CI green. 2026-09-13: pushed; `gh run list` shows 3 CI runs on `master` (`1d1578b`, `a0e1fa2`, `554086c`), all `success` → output "repo + green CI" met (closed 11 Sep, 1 day after its 10 Sep due date) |
| E0.2 | Pin SUMO 1.27.1 from PyPI; reproducible environment incl. Postgres + `pgvector`; record in README | ✅ | 2026-09-11: SUMO 1.27.1 pinned as `pyproject.toml` dependencies, installed and verified in the `resto` env; README rewritten. 2026-09-14: the Postgres + `pgvector` service is no longer part of the design — ADR-0012 (architecture v1.0, A1) moves the DatabaseMCP reference backend to SQLite + in-process cosine. The residual paper-cut noted in the last review is now fixed: commit `749b393` rewrote the stale "Postgres + `pgvector`" wording in `tfm-work-plan.md` E0.2/E1.3 to describe the SQLite backend |
| E0.3 | Domain dataclasses (aggregates, value objects, tasks, drafts) + `schemas.py` TypeAdapters, JSON-schema export, round-trip tests | ✅ | 2026-09-14: committed in `32672d5`. Six aggregates + value objects incl. `drafts.py` (`NetworkDraft`/`DemandDraft`/`ScenarioDraft`/`ExpertNoteDraft`), `schemas.py` TypeAdapters, 18 files in `schemas/` with a drift test, `test_serialisation.py` round-tripping every domain dataclass, `test_drafts.py`. Verified now: `pytest` 186 passed, `ruff check .` clean, CI green on `master` (run `34816761408`) |
| E0.4 | DatabaseMCP contract spec (six capability groups incl. `demands`, `query_edgedata`; error codes) | ✅ | 2026-09-14: `docs/DATABASE_MCP_CONTRACT.md` committed (`0ea81ac`, CI green). Six capability groups (§5.1–5.6), error codes (§7), conformance checklist (§8, for E1.5 to implement against), SQLite reference impl (§9). §10 open points 1–2 resolved by architecture amendment A2 (`Network.label`, note-ranking as a pure domain algorithm — ADR-0013/0014); open point 3 (`historical_demand` shape) is *deliberately* left open until E6.5 per the doc's own text, not a gap in this task. Cosmetic-only issue: the file's own title/header still literally read "v1.0-draft" despite the architecture freeze — worth a one-line fix, doesn't affect content completeness |
| E0.5 | DEV-NET: grid + hand edits (bottleneck, signalised corridor) | ✅ | 2026-09-14, commit `5e48e03` (CI green): `netgenerate` 5×5 grid, scripted (`generate.sh`, reproducible, no manual GUI edits), 2→1 lane merge bottleneck on `B0C0`→`C0D0` isolated from the row-2 signalised corridor (5 TLS junctions), 0 U-turn connections, fully strongly connected — all verified and documented in `eval/dev-net/README.md` with concrete counts (80 edges, 25 nodes, one expected `netconvert` warning) |
| E0.6 | Demand profiles low/peak/incident on DEV-NET (trips + routes) + synthetic counts at control edges | ✅ | 2026-09-14, commit `e5f1ef5` (CI green): `low`/`peak`/`incident` trips+routes (seed 1), `control_counts.json` at 5 control edges, `verification.ipynb` sweeping simulation seeds 1–9 per profile. `peak` measured at 16.5% mean congestion (inside the 10–20% target), `incident` isolates the `B0C0` bottleneck (26× peak occupancy); write-up documents a real finding (sim-seed 8 gridlock at the original incident rate) and the fix (rate lowered to 950 veh/h, 20/20 seeds clean) — reads as genuine empirical tuning, not a placeholder |
| E0.7 | Trace logging: run id, step, tool call, artifacts, tokens → JSONL | ✅ | 2026-09-14, commit `bcca11c` (CI green): `Tracer` port + `JsonlTracer` adapter (`{root}/{study_id}.jsonl`, one JSON object per line, tolerates dataclasses/`Enum`/`Path` payloads). `test_jsonl.py` covers ordering, per-study isolation, unknown-study read, and payload serialisation of `StepStatus`/`Usage`/`Path` — 5 tests, all passing |
| E0.8 | Architecture doc frozen as v1.0 + ADRs for §7 decisions | ✅ | 2026-09-14, commit `7745324` (CI green): `tfm-architecture-and-dod.md` header now reads "v1.0 — Status: frozen (2026-09-14, E0.8/M0)"; 14 ADRs under `docs/adr/` (0001–0014) with an index (`README.md`); §9 amendments A1/A2 reconciled into the body and superseded as prose by their ADRs |

## E1 — MCP servers and `traci_api` (6 tasks) · due 2 Oct · DoD §4.9

| ID | Task | Status | Notes |
|---|---|---|---|
| E1.1 | NetworkMCP (7 read tools + tests incl. error case) | ✅ | 2026-09-14, commit `daf304d` (CI green): all 7 tools (`get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`, `edges_in_bbox`, `capacity_estimate`, `get_tls`) live as `application/tools/network.py` functions, wrapped by `interface/mcp/network_server.py` (ADR-0009: MCP layer is protocol plumbing only). Coverage is layered rather than duplicated per file: `tests/unit/adapters/sumo/test_netxml.py` carries the real ≥3-tests-incl.-error-case bar per method (25 tests, every one of the 7 query methods plus `has_edge`/`has_lane`/`has_tls` has an explicit unknown-id `KeyError` case), `tests/unit/application/tools/test_network.py` (10 tests) checks delegation + `Tool` wrapping, `tests/unit/interface/mcp/test_network_server.py` (4 tests) checks the server wires those tools and surfaces an unknown-id error as `UnexpectedToolError`. Verified now: full suite green |
| E1.2 | `traci_api` (8 primitives + `at_time`/`when` + `applied_actions`) and TraciMCP over it | ✅ | 2026-09-14, commit `4301d1c` (CI green): `adapters/sumo/traci_api.py` has all 8 primitives (`close_lane`, `open_lane`, `set_speed`, `set_tls_program`, `get_edge_occupancy`, `get_edge_speed`, `get_vehicle_count`, `step`) plus `at_time`/`when`/`run`/`applied_actions`/`registered_rules`, each `AppliedAction` tagging `origin=CODE` vs `origin=RULE`. `interface/mcp/traci_server.py` exposes the 8 primitives over MCP (deliberately not `at_time`/`when`, documented reasoning: callables can't cross the JSON wire — a design call, not a gap). `tests/unit/adapters/sumo/test_traci_api.py` (20 tests) runs with a **real SUMO/traci session** against DEV-NET, not mocks — covers every primitive, an unknown-id `TraciException` case for the mutating ones, `at_time` firing once, `when`'s rising-edge semantics, `origin` tagging, and `run(until=...)`. `test_traci_server.py` (3 tests) + `test_traci_api_facade.py` (35 tests) round it out |
| E1.3 | DatabaseMCP reference impl (SQLite + in-process cosine, ADR-0012; six capability groups incl. `demands`) + `mcp_client` adapter | ✅ | 2026-09-14, commits `1a3c930` + `8ee4380` (CI green): `adapters/persistence/sqlite/repositories.py` implements the 5 required capability groups (`networks`, `demands`, `scenarios` incl. `find_similar_scenario`, `results` incl. `query_edgedata`, `notes` incl. `search_notes`) over `interface/mcp/database_server.py` (17 tools, contract error codes as `"CODE: message"`-prefixed `ToolError`s per §7). `adapters/persistence/mcp_client.py` speaks *real* MCP (`ClientSession` over any `mcp.client` transport, sync/async bridging documented in-file) rather than calling the server in-process — this is what the conformance suite (E1.5) actually exercises. `historical_demand` (6th, optional group) is deliberately unimplemented, per contract §10 point 3, deferred to E6.5 — not a gap in this task. Tests: 25 in `test_repositories.py`, 18 in `test_mcp_client.py`, 8 in `test_database_server.py`. Note: `tfm-work-plan.md` E1.3's own wording still lists `historical_demand` as in-scope output — same class of paper-cut as the since-fixed pgvector wording, worth a follow-up doc edit, not a blocker |
| E1.4 | `find_similar_scenario` + `search_notes` + `query_edgedata` (10 + 5 + 5 test cases) | ✅ | 2026-09-14, commit `8ee4380` (CI green): the 10+5+5 bar is met in `conformance/` (run through the real `mcp_client` adapter, per §4.9's own framing of this bar as a conformance requirement): `test_find_similar_scenario.py` 10 tests (exact-hash short-circuit, baseline scoring, intervention-only/context-tags-only/combined weighting, zero-score exclusion, network scoping, limit, empty case), `test_search_notes.py` 5 tests (scoping, ranking, `status` filter, `context_tags` filter, unknown-filter-key error), `test_query_edgedata.py` 5 tests (window/edge-set cases). Additional unit-level coverage in `test_repositories.py` (5 find_similar + 5 search_notes) and `test_edgedata.py` (8 tests) |
| E1.5 | DatabaseMCP conformance suite | ✅ | 2026-09-14, commit `8ee4380` (CI green): `conformance/` (56 tests) is parametrized over every DatabaseMCP backend the project ships (`_BACKENDS` dict, currently `sqlite-reference`; adding Postgres+pgvector later — Stretch — is a one-entry addition) and reaches every backend only through `interface/mcp/database_server.py` + `adapters/persistence/mcp_client.py` over a real (in-memory) MCP `ClientSession`, never a backend's repository classes directly — genuinely tests "any implementation" per DoD §4.9, not just the SQLite path. Covers capabilities listing, determinism, error codes, idempotency, round-trip, plus the E1.4 suites above |
| E1.6 | Capability-listing helper for Coordinator; latency benchmark | ✅ | 2026-09-14, commit `c77692b` (CI green, verified now): `application/capability_negotiation.py` derives capability groups from a backend's advertised tool names (`capabilities_of`) and hard-fails start-up on a missing required one (`negotiate_capabilities`, `MissingRequiredCapabilityError`), with `historical_demand` treated as optional per contract; covered by `tests/unit/application/test_capability_negotiation.py` and reused as the single source of truth by `conformance/test_capabilities.py`. `eval/benchmarks/latency.py` + `eval/benchmarks/latency-report.md`: all 32 MCP tools (Network/Database/Traci) benchmarked at 50 reps each on DEV-NET, every one well under the §4.9 <1s threshold (slowest 4.84 ms max) |

## E2 — Scenario Builder & Simulation Runner (7 tasks) · DoD §4.5, §4.6

| ID | Task | Status | Notes |
|---|---|---|---|
| E2.1 | Runner batch mode (+ ephemeral mode for probe/calibration) + reproducibility test (20 runs) | ✅ | 2026-09-15, commit `1e23009` (CI green, verified now): `adapters/sumo/runner.py`'s `SubprocessSumoRunner.run_batch` derives a run cfg (seed/outputs/edgedata period all in files, per ADR-0017), runs `sumo -c`, collects edgedata/tripinfo/statistics/summary as `ArtifactRef`s, surfaces SUMO's own error message on a non-zero exit or missing outputs. `application/use_cases/run_simulation.py`: `run_simulation` computes `result_id = hash(scenario_id, seed, mode, sumo_version)` before running, returns an existing *ok* result unrun ("zero redundant simulations"), stores a `SimulationResult` with a separate `content_hash` over only the deterministic artifact kinds; `run_ephemeral` is the unstored probe/calibration path (no repository argument at all, so it cannot reach the store). `tests/unit/adapters/sumo/test_runner.py::test_twenty_runs_with_the_same_seed_are_byte_identical` runs 20 real SUMO batch runs and asserts a single distinct content-hash tuple across all of them — the literal reproducibility bar met, not simulated. Online mode (`run_online`) still raises `NotImplementedError`, correctly deferred to E2.5 |
| E2.2 | Builder Minimal (agent + writer tools): static `lane_closure`/`speed_limit` → `.add.xml` + `sumocfg` | ✅ | 2026-09-15, commit `ee85dad` (CI green, verified now): `adapters/llm/agents/scenario_builder.py` assembles the `AgentTask`/tool list/budget and calls the shared `ToolAgent` port (real impl now exists, see note below); its system prompt restricts the agent to `lane_closure`/`speed_limit` on a single lane with a fixed window, explicit "no silent coercion" — anything else must go to `rejected[]`, matching ADR-0007. `application/tools/scenario_builder.py` binds `edge_exists`/`lane_exists`/`write_rerouter`/`write_vss`/`write_sumocfg` as real `Tool`s against `NetworkQuery` + the deterministic writers. `application/use_cases/build_scenario.py::build_scenario` promotes an `AgentRun[ScenarioDraft]` in the DoD §2.4 order (syntactic via the dataclass, semantic — demand/network match, every accepted intervention's target re-checked directly against the network rather than trusting the agent's own tool calls, SUMO load check on the written cfg — then `scenario_id` from the *accepted* interventions, then persist with existing-id dedup). 581 lines across the three test files (`test_scenario_builder.py` agent/tools/use-case) cover both layers. Same commit range also lands the real `OpenRouterToolAgent` (`adapters/llm/anthropic_client.py`, `Toolagent on openrouter` commit `cea5570`) that this agent runs on: `adapters/llm/config.py` wires `RESTO_LLM_DEFAULT_MODEL=deepseek/deepseek-v4.1-flash` as the hard default with `RESTO_LLM_ESCALATION_MODEL` blank, matching CLAUDE.md's cost policy exactly; `test_anthropic_client.py` explicitly does not construct a real client or need `OPENROUTER_API_KEY` (fake-agent tests only, per ADR-0001) |
| E2.3 | Builder static: `edge_closure`, `signal_program` (WAUT), `demand_scale` | ⬜ | |
| E2.4 | Effect-verification harness | ⬜ | |
| E2.5 | Runner online mode: `ScriptSandbox` (lint, dry-run, subprocess) + 10 script test cases | ⬜ | Replaces the v0.2 `TraciPlan` interpreter |
| E2.6 | Builder scripts: `condition` → `when(...)`, `custom` interventions, `rejected[]` | ⬜ | |
| E2.7 | Builder bank (25–30 specs incl. `custom`) run to ≥27/30 | ⬜ | |

## E3 — Evaluation assets & harness (6 tasks)

| ID | Task | Status | Notes |
|---|---|---|---|
| E3.1 | Scenario matrix DEV-NET/peak (15–25 rows × 3 seeds) | ⬜ | |
| E3.2 | Question templates + generator + gold answers (≥60 on DEV-NET) | ⬜ | |
| E3.3 | Metrics harness (exact match, Jaccard, direction, band, Brier, abstention P/R) | ⬜ | |
| E3.4 | Request bank (50+ NL requests, 10+ ambiguous; gold `Question` + `StudyPlan` + trace) | ⬜ | |
| E3.5 | Scenario matrix REAL-NET/peak | ⬜ | |
| E3.6 | Question bank REAL-NET (40+) | ⬜ | |

## E4 — Network Expert, research focus (10 tasks) · DoD §4.7

| ID | Task | Status | Notes |
|---|---|---|---|
| E4.1 | Refactor v1 Expert onto `ToolAgent` (`ExpertTask` → `ExpertAnswer`); facts via tools; `evidence[]` | ⬜ | |
| E4.2 | Descriptive questions to Done on DEV-NET (≥90%) | ⬜ | |
| E4.3 | Diagnostic questions to Done (Jaccard ≥0.6; "why" rubric ≥70%) | ⬜ | |
| E4.4 | Counterfactual, forced mode (direction ≥75%, band ≥50%) | ⬜ | |
| E4.5 | Free mode: abstention policy, `proposed_experiment` | ⬜ | |
| E4.6 | `ExpertNote` writing + RAG + status update; hygiene probes (20) | ⬜ | |
| E4.7 | DEV-NET benchmark report (3 runs, mean±std) → **M2** | ⬜ | |
| E4.8 | Port to REAL-NET, full benchmark | ⬜ | |
| E4.9 | Learning-effect experiment (0/5/15/25, CIs, plot) | ⬜ | |
| E4.10 | Calibration analysis + ablation | ⬜ | |

## E5 — Coordinator (incl. Input Parser), Output Composer (8 tasks) · DoD §4.1, §4.2, §4.8

| ID | Task | Status | Notes |
|---|---|---|---|
| E5.1 | Coordinator request understanding: text → `Question`, retry-then-fail, `ambiguities[]` → `awaiting_user` | ⬜ | |
| E5.2 | Coordinator Minimal: `ToolAgent` with specialists as tools, `StudyPlan` first, `Study` persisted per step, guards in code | ⬜ | |
| E5.3 | Loop closure: `needs_simulation` → run → re-ask, `max_rounds`; GP-3/4/5 | ⬜ | `run_study` placeholder in `application/use_cases/`; `Study` invariants (`max_rounds`, forced mode, ambiguity) already enforced in the domain and tested |
| E5.4 | Output Composer Minimal (agent): closed `Study` → `Report` → Markdown | ⬜ | |
| E5.5 | Coordinator Done: routing ≥90% (plan + trace), zero redundant sims, failure injection | ⬜ | |
| E5.6 | Capability negotiation with DatabaseMCP; GP-10 | ⬜ | |
| E5.7 | Output Composer Done: automatic traceability checker | ⬜ | |
| E5.8 | Stability: 3 repeated runs of Input Parser + Coordinator benchmarks | ⬜ | |

## E6 — Network Author, Demand Generator, REAL-NET (7 tasks) · DoD §4.3, §4.4

| ID | Task | Status | Notes |
|---|---|---|---|
| E6.1 | Network Author Minimal (agent): OSM snapshot → `netconvert` → `Network` with recipe; v1 tool catalogue + `probe_run` | ⬜ | Domain side done (`NetworkRecipe`, `TopologyModification`, `ProbeReport`); ports `OsmSource`, `NetconvertRunner`, `PlainNetEditor` defined |
| E6.2 | Demand Generator Minimal (agent): `randomTrips` + `duarouter` → trips + routes; `reroute_demand` | ⬜ | |
| E6.3 | REAL-NET: choose district, hand-clean on plain XML, freeze, log every fix (type, file, attribute) | ⬜ | |
| E6.4 | Network Author Done (sanity + probe, 10/10 GEN-LOCATIONS, replay determinism, agent stability, derivation bank) | ⬜ | |
| E6.5 | Demand Generator Done (calibration loop to fidelity ±15%/±25% with evidence, history-driven, reroute test) | ⬜ | |
| E6.6 | Demand profiles low/peak/incident on REAL-NET | ⬜ | |
| E6.7 | GP-8 (new place name) and GP-11 (add an edge) passing | ⬜ | |

## E7 — Integration (7 tasks, 1 Stretch) · DoD §5

| ID | Task | Status | Notes |
|---|---|---|---|
| E7.1 | Golden-path test framework; GP-1…GP-5 | ⬜ | |
| E7.2 | GP-6 (dynamic path) and GP-7 (compare) | ⬜ | |
| E7.3 | Failure-injection suite across golden paths (incl. script lint/dry-run, agent budget) | ⬜ | |
| E7.4 | Cost/latency per golden path recorded | ⬜ | |
| E7.5 | Full run: 11/11 golden paths × 3 → **M6** | ⬜ | |
| E7.6 | Code freeze: tag, README, reproducibility package | ⬜ | |
| E7.7 | *(Stretch)* usability session with 2–3 DLR engineers | ⬜ | Not counted — only attempted if M6 lands on time |

## E8 — Thesis document (8 tasks) · rolling, concentrated 8–18 Feb

| ID | Task | Status | Notes |
|---|---|---|---|
| E8.1 | Outline + state-of-the-art chapter | ⬜ | |
| E8.2 | Architecture & contracts chapter | ⬜ | |
| E8.3 | Evaluation methodology chapter | ⬜ | |
| E8.4 | Module sections written at each Done | ⬜ | |
| E8.5 | Results chapter | ⬜ | |
| E8.6 | Discussion, limitations, conclusions | ⬜ | |
| E8.7 | Full draft to supervisors; revision round | ⬜ | |
| E8.8 | Final delivery | ⬜ | **M7**, 18 Feb |

---

## Milestone status

| ID | Date | Milestone | Status | Notes |
|---|---|---|---|---|
| M0 | 18 Sep | Foundations frozen | ✅ | 2026-09-14, 4 days early: all 8 E0 tasks ✅, CI green on `master`, DEV-NET runs its three demand profiles, architecture v1.0 frozen. `tfm-work-plan.md` E0.2/E1.3 still carry stale Postgres/`pgvector` wording (superseded by ADR-0012) — a doc-only cleanup, not a milestone blocker |
| M1 | 16 Oct | Tooling complete | ⬜ | 2026-09-15: all of E1 (MCPs, §4.9) now ✅. Runner batch (E2.1) and Builder Minimal (E2.2) ✅. Still missing for the acceptance line: E2.3 (`edge_closure`/`signal_program`/`demand_scale`), E2.4 (effect-verification harness) and E3.1 (DEV-NET scenario matrix stored) — none started yet |
| M2 | 13 Nov | **Expert Done on DEV-NET** | ⬜ | |
| M3 | 11 Dec | End-to-end loop | ⬜ | |
| M4 | 15 Jan | Real network ready | ⬜ | |
| M5 | 29 Jan | **Thesis result** | ⬜ | |
| M6 | 5 Feb | All modules Done | ⬜ | |
| M7 | 18 Feb | Delivery | ⬜ | |

---

## Update ritual

Update this file whenever a task's status changes (not just on the Friday ritual from `tfm-work-plan.md` §6) — flip its ⬜/🔄/✅ and refresh the summary line at the top. A task only becomes ✅ once it meets its DoD, not when the code merely exists.
