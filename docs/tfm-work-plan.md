# Agentic Traffic Simulation Framework — Work Plan (v0.2)

Scope: reach **Done** on every module of the Architecture & DoD document (**v0.3**), plus the thesis document, between **Wed 9 Sep 2026** and **Thu 18 Feb 2027**. Stretch items are explicitly out of plan.

v0.2 of this plan (2026-09-11) aligns task wording, outputs and a few estimates with architecture v0.3: all authoring modules are agents, `traci_api` scripts replace the `TraciPlan` interpreter, the Network Generator becomes the Network Author (create + derive), `Demand` becomes an aggregate calibrated in the loop, and the Input Parser is part of the Coordinator. Task ids, due dates and milestones are unchanged.

---

## 0. Capacity check

| | |
|---|---|
| Calendar span | 23 weeks (9 Sep → 18 Feb) |
| Minus Christmas break (21 Dec → 3 Jan, low-intensity work only) | ≈ 21 working weeks |
| Capacity at 40 h/week | ≈ 840 h |
| Planned effort (sum of all tasks below) | 894 h |
| Contingency | **none** (−54 h) |

**Pending scope, not counted above (added 2026-09-22):** the Coordinator is split per
[ADR-0023](adr/0023-coordinator-split-deterministic-executor.md) — Input Parser agent (text → `Question`,
E5.1), a one-shot Coordinator agent (`Question` + read-only DB tools → `StudyPlan`, E5.2), and a
deterministic Executor (`run_study`, E5.10) that walks the plans and runs the free-mode loop as new
phases; `StudyOutcome` is dropped. The domain change (`Study` in phases, typed `PlanStep` with
`FromStep`) is E5.9. No hours are committed for E5.9/E5.10 and E5.2 is not yet re-estimated; this is
considered now rather than after M6 because the project has run ahead of its own calendar since 13 Sep
(every `docs/feasability-analisis/` entry since then).

**Pending scope, not counted above (added 2026-09-23):** [ADR-0025](adr/0025-executor-plan-shape-intent-rules-and-failures.md)
fixes the Executor contract (plan names the network and the reused experiments and may have zero steps;
planning rules by `intent`; typed `StepError`; forced last round; role/purpose from the Coordinator;
one port per agent) and [ADR-0026](adr/0026-expert-notes-per-study-and-prediction-verification.md) when
and how notes are written and verified; flows in [`study-flows.md`](study-flows.md). Almost all of it is
absorbed by tasks not yet done (E3.4, E5.1–E5.5, E5.9, E5.10, E6.7, E7.1, E7.3 — wording updated below).
Two tasks are new, hours not yet committed: **E4.11** (note writing per ADR-0026 — E4.6 is done and is
not reopened) and **E5.11** (deterministic rendering of failed and `awaiting_user` studies).

The plan is overcommitted by ~6 % and has no buffer (v0.1 was ~4 %; the extra 24 h are the agentic Network Author and Demand Generator, `traci_api`, and the Coordinator as a tool-using agent). That is deliberate: it tells you where you are at every milestone. Section 5 lists, in order, which *Done* criteria to downgrade to *Minimal* if a milestone slips. Do not add Stretch work before M6.

---

## 1. Epics and tasks

Estimates are in hours. "Due" is the end-of-day deadline. "DoD" points to the section of the Architecture & DoD document that the task satisfies.

### E0 — Foundations (70 h) · 9 Sep → 18 Sep

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E0.1 | Repo skeleton: hexagonal layout (domain / application / adapters), packaging, ruff, pytest, CI | repo + green CI | 8 | 10 Sep |
| E0.2 | Pin SUMO 1.27.1 from PyPI as a `pyproject.toml` dependency (`eclipse-sumo`, `sumolib`, `traci`); reproducible environment (no extra service: the DatabaseMCP reference backend is SQLite, ADR-0012); record in README | env + README | 4 | 10 Sep |
| E0.3 | Domain dataclasses for every aggregate, value object, typed task and agent draft of §2.3 (incl. `NetworkDraft`, `DemandDraft`, `ScenarioDraft`); `application/schemas.py` (TypeAdapters), JSON-schema export to files, round-trip tests | `domain/` + `schemas.py` | 16 | 14 Sep |
| E0.4 | DatabaseMCP contract spec: tool names, I/O schemas, six capability groups (incl. `demands`, `results.query_edgedata`), error codes | `DATABASE_MCP_CONTRACT.md` | 8 | 15 Sep |
| E0.5 | DEV-NET: `netgenerate` grid + hand edits (2→1 merge bottleneck, signalised corridor), documented | `dev-net.net.xml` + doc | 10 | 16 Sep |
| E0.6 | Demand profiles `low` / `peak` / `incident` on DEV-NET, seeded, stored as trips + routes; synthetic counts at 3–5 control edges for calibration tests; verify congestion levels (≈10–20 % edges congested at peak) | 3 demand sets + counts + verification notebook | 10 | 17 Sep |
| E0.7 | Trace logging: run id, step, tool call, artifacts, tokens → JSONL | `tracing/` | 8 | 18 Sep |
| E0.8 | Architecture doc frozen as v1.0 + ADRs for the decisions in §7 | `docs/` | 6 | 18 Sep |

### E1 — MCP servers and `traci_api` (94 h) · 21 Sep → 2 Oct · DoD §4.9

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E1.1 | NetworkMCP: `get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`, `edges_in_bbox`, `capacity_estimate`, `get_tls`; ≥3 tests each incl. error case | server + tests | 20 | 24 Sep |
| E1.2 | `resto.traci_api`: primitives `close_lane`, `open_lane`, `set_speed`, `set_tls_program`, `get_edge_occupancy`, `get_edge_speed`, `get_vehicle_count`, `step`; declarative `at_time(...)` / `when(...)` / `run()`; `applied_actions` log with `origin`; TraciMCP server over the same primitives; tests with SUMO in the loop | module + server + tests | 20 | 28 Sep |
| E1.3 | DatabaseMCP reference implementation (SQLite + in-process cosine, ADR-0012; filesystem artifact store): `networks`, `demands`, `scenarios`, `results` (incl. `query_edgedata`), `notes` (in-process vector search), `historical_demand` capability groups; in-process repository adapters + `mcp_client` adapter | server + adapters | 24 | 30 Sep |
| E1.4 | `find_similar_scenario` (exact `scenario_id` match, else intervention + `context_tags` overlap), `search_notes` with `status`/`basis` filters, `query_edgedata` on windows/edge sets; 10 + 5 + 5 test cases | tests | 12 | 1 Oct |
| E1.5 | DatabaseMCP conformance suite runnable against any implementation through the `mcp_client` adapter | `conformance/` | 10 | 2 Oct |
| E1.6 | Capability-listing helper for the Coordinator; latency benchmark of every tool on DEV-NET | benchmark report | 8 | 2 Oct |

### E2 — Scenario Builder & Simulation Runner (110 h) · DoD §4.5, §4.6
Phase A (Minimal, 58 h): 5 Oct → 16 Oct. Phase B (Done, 52 h): 30 Nov → 11 Dec.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E2.1 | Runner batch mode: run `sumocfg` with a seed, collect edgedata/tripinfo/summary, build `SimulationResult` (`result_id` = hash of scenario + seed), store; ephemeral mode for `probe_run` / `calibration_run` (not stored); byte-identical reproducibility test (20 runs) | runner + tests | 12 | 8 Oct |
| E2.2 | Builder Minimal (agent with writer tools): static `lane_closure` and `speed_limit` → rerouter / VSS `.add.xml` + `sumocfg`; `ScenarioDraft` → promotion (id validation against NetworkMCP, SUMO load check, `scenario_id` = request hash) | builder agent + writers | 20 | 13 Oct |
| E2.3 | Builder static: time-bounded `edge_closure`, `signal_program` (WAUT), `demand_scale` (derived `Demand` with `scale`, mechanism `RegenerateDemand`) | builder | 14 | 16 Oct |
| E2.4 | Effect-verification harness: per intervention type, read edgedata / `applied_actions` and assert the observable effect (§4.5) | `verify/` | 12 | 16 Oct |
| E2.5 | Runner online mode: `ScriptSandbox` (AST lint — only `resto.traci_api` imports; `dry_run`; subprocess execution with the run seed), `applied_actions` with `origin`; 10 script test cases verified by reading state back through TraCI; scripts failing lint rejected before SUMO starts; crashing scripts → failed run with traceback | sandbox + online runner + tests | 24 | 4 Dec |
| E2.6 | Builder scripts: `condition` → `when(...)` script; `custom` interventions (static mechanism if one fits, else free Python against `traci_api`); `rejected[]` with reason; mechanism-selection tests | builder | 14 | 8 Dec |
| E2.7 | Builder bank (25–30 specs covering every §2.5 cell incl. `custom`); run to ≥27/30; structural-determinism check over 3 runs (static files + `declared_rules`); rejection of unsupported specs with reason | bank + report | 14 | 11 Dec |

### E3 — Evaluation assets & harness (70 h)

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E3.1 | Scenario matrix DEV-NET / peak: 15–25 rows × 3 seeds, simulated and stored via DatabaseMCP | matrix in DB | 12 | 16 Oct |
| E3.2 | Question templates (descriptive / diagnostic / counterfactual) + generator + programmatic gold answers from the matrix; ≥60 questions on DEV-NET | question bank | 16 | 23 Oct |
| E3.3 | Metrics: exact match, Jaccard top-k, direction, magnitude band, Brier, abstention P/R; harness with repeated runs, mean ± std, report generation | `eval/` | 16 | 27 Oct |
| E3.4 | Request bank: 50+ NL requests (10+ ambiguous) with gold `Question`, gold `StudyPlan` and expected `StepRecord` trace for a fixed DB state; gold plans follow ADR-0025 (planning rules by `intent`, `network_id` + `reused` with role/purpose, zero-step plans valid, no `ask_expert`/`compose_report` steps) | request bank | 12 | 18 Nov |
| E3.5 | Scenario matrix REAL-NET / peak | matrix in DB | 8 | 15 Jan |
| E3.6 | Question bank REAL-NET (40+) | question bank | 6 | 18 Jan |

### E4 — Network Expert (160 h) · DoD §4.7 · **research focus**
Phase A (DEV-NET, 110 h): 19 Oct → 13 Nov. Phase B (REAL-NET, 50 h): 18 Jan → 29 Jan.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E4.1 | Refactor the existing v1 Expert onto the `ToolAgent` port (`ExpertTask` in, `ExpertAnswer` out); facts only through tools (`query_edgedata`, `get_result`, NetworkMCP), never from parsed files; `evidence[]` on every answer | expert v2 | 16 | 22 Oct |
| E4.2 | Descriptive questions to Done on DEV-NET (≥90 %) | benchmark run | 14 | 27 Oct |
| E4.3 | Diagnostic questions to Done (Jaccard ≥0.6; "why" rubric ≥70 %) | benchmark run | 18 | 2 Nov |
| E4.4 | Counterfactual, forced mode: reasoning strategy over graph + facts, `confidence` and `basis` output; direction ≥75 %, band ≥50 % | benchmark run | 24 | 6 Nov |
| E4.5 | Free mode: abstention policy, `proposed_experiment` (a `Question`) generation; abstention recall ≥70 %, false requests ≤30 % | benchmark run | 14 | 10 Nov |
| E4.6 | `ExpertNote` writing after each experiment, RAG over notes, `status` update on confirm/refute; knowledge-hygiene probes (20) | notes pipeline + tests | 16 | 12 Nov |
| E4.7 | DEV-NET benchmark report: all §4.7 metrics, 3 runs, mean ± std → **M2** | report | 8 | 13 Nov |
| E4.8 | Port to REAL-NET, tune, full benchmark (descriptive ≥85 %, Jaccard ≥0.5, direction ≥65 %) | report | 24 | 26 Jan |
| E4.9 | Learning-effect experiment: store size 0 / 5 / 15 / 25, held-out interventions, confidence intervals, plot | figure + data | 18 | 29 Jan |
| E4.10 | Calibration analysis (Brier, accuracy by `basis`) and ablation facts-only vs facts + notes | figures | 8 | 29 Jan |
| E4.11 | *(new, hours TBD)* Notes per ADR-0026: note writer returns 0–3 `ExpertNoteDraft`s, each with a `scenario_ref` from an allow-list (study scenarios + predicted `scenario_id`); `write_note` validates the ref and sets `provenance = simulation` only if that scenario has results in the study; tests with the fake agent | notes v2 + tests | **TBD** | 12 Nov |

### E5 — Input Parser, Coordinator, Executor, Output Composer (104 h) · DoD §4.1, §4.2, §4.8
Phase A (Minimal + loop, 58 h): 16 Nov → 27 Nov. Phase B (Done, 46 h): 1 Feb → 5 Feb.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E5.1 | Input Parser (own agent again, ADR-0023): text → `Question`, no tools, retry-then-fail, `ambiguities[]` → `awaiting_user` before the Coordinator runs; `InputParserAgent` port implementation (ADR-0025); evaluate on request bank to Done (§4.1) | parser agent + report | 14 | 18 Nov |
| E5.2 | Coordinator Minimal (ADR-0023): one `ToolAgent.run` per `Question` with read-only tools (`find_network`, `find_demand`, `find_scenario`, `list_results`) → typed `StudyPlan` or a clarification request; planning rules by `intent` (ADR-0025: counterfactual plans the baseline only, phases ≥ 1 planned as `run`), `network_id` + `reused` + role/purpose in the plan; `CoordinatorAgent` port; the 4 canonical DB states — **hours to be re-estimated: the tool-using orchestration part moved to E5.10** | coordinator agent | 24 | 23 Nov |
| E5.3 | Loop closure (ADR-0023): `needs_simulation` → Coordinator plans the `proposed_experiment` as a new phase → Executor runs it → re-ask with the original question and all phases' results, `max_rounds` respected with the last round forced (`forced_by_limit`, ADR-0025); `ExpertTask` over base + derived networks (open point in ADR-0023, decided here); GP-3 / GP-4 / GP-5 passing | tests | 14 | 26 Nov |
| E5.4 | Output Composer Minimal (agent): completed `Study` → `Report` (claims with `evidence_refs`) → Markdown with evidence table; experiments table marks reused experiments; fixed limitation line added by code when the last round was `forced_by_limit` (ADR-0025) | composer | 6 | 27 Nov |
| E5.5 | Coordinator Done: routing ≥90 % on `StudyPlan` vs gold plan (gold plans without `ask_expert`/`compose_report` steps, ADR-0023); `StepRecord` trace vs expected is now Executor behaviour, checked by tests with the fake agent; zero redundant simulations (counter); failure injection (incl. agent budget exhausted) yields named failing step with the right `StepError.kind` (ADR-0025) | report | 18 | 3 Feb |
| E5.9 | *(new, hours TBD)* Domain change for ADR-0023: `Phase`, `Study.phases` and its invariants, typed `PlanStep` union with `FromStep` late binding, `ExpertRound` without `triggered_experiments`; plus ADR-0025: `StudyPlan.network_id` + `reused` (`ReusedExperiment`), zero-step plans, role/purpose on the `build_scenario` step, `Experiment.reused`, `StepError`, `ExpertRound.forced_by_limit`; schemas and class diagram regenerated | domain + tests | **TBD** | 13 Nov |
| E5.10 | *(new, hours TBD)* Executor (`run_study`, deterministic code, not an agent): resolves `FromStep`, calls specialists, promotes drafts, records `StepRecord`s per phase, guards in code (no re-run of an existing `result_id`, per-`Study` budget, `max_rounds`), runs `ask_expert` and `compose_report` itself, mechanical closing status; a rejected draft is a failed step by name, no re-ask; `Study` persisted after every step; plus ADR-0025/0026: agent ports (`application/ports/agents.py`) + composition root, failures classified into `StepError`, forced last round, `DEFAULT_SEEDS`, note writer after the final round with the scenario allow-list and predicted `scenario_id`, `update_note_status` on new results only | run_study | **TBD** | 25 Nov |
| E5.11 | *(new, hours TBD)* Deterministic rendering (ADR-0025) of `failed` and `awaiting_user` studies in `interface/render.py`: what happened / what was done / what the user can do, per `StepError.kind`; ambiguities or candidate list; CLI error when no `Study` is created | render + tests | **TBD** | 27 Nov |
| E5.6 | Capability negotiation with DatabaseMCP; GP-10 | tests | 8 | 3 Feb |
| E5.7 | Output Composer Done: automatic traceability checker (numbers ↔ artifacts); faithfulness rubric on 20 reports | checker + report | 12 | 5 Feb |
| E5.8 | Stability: 3 repeated runs of Input Parser and Coordinator benchmarks | report | 8 | 5 Feb |

### E6 — Network Author, Demand Generator, REAL-NET (106 h) · DoD §4.3, §4.4
14 Dec → 18 Dec, low-intensity over the break, 4 Jan → 15 Jan.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E6.1 | Network Author Minimal (agent): place / bbox → OSM snapshot → `netconvert` → `Network` with recipe; v1 tool catalogue (`netconvert` options, `remove_edge` / `add_edge` / `set_lanes` / `set_speed` on plain XML, `inspect_network`, `sanity_check`, `probe_run`); `NetworkDraft` promotion with replay check | agent + tools | 16 | 16 Dec |
| E6.2 | Demand Generator Minimal (agent): parameters → `randomTrips` + `duarouter` → trips + routes stored via `demands`; teleport ≤2 %; seeded; replay-deterministic; `reroute_demand` (deterministic) | agent + tools | 10 | 18 Dec |
| E6.3 | REAL-NET: choose district (300–800 edges), hand-clean on plain XML, **freeze**, log every fix as (type, plain file, attribute) → error taxonomy **and** Network Author tool backlog | `real-net.net.xml` + fix log | 16 | 6 Jan |
| E6.4 | Network Author Done: sanity report (SCC ≥95 %, no zero-length, fringe reachability) + `probe_run` threshold, 10/10 on GEN-LOCATIONS; replay determinism (`replay(recipe)` == `content_hash`, 100 %); agent stability over 3 runs; derivation bank 10/10 (incl. `AddEdge`); catalogue extended from the E6.3 fix log where cheap | report | 24 | 11 Jan |
| E6.5 | Demand Generator Done: calibration loop (`routeSampler` + `calibration_run`) reaching fidelity ±15 % DEV / ±25 % REAL at the control edges within 5 rounds, `Fidelity.evidence` resolvable; external datasets frozen as artifacts; synthetic `historical_demand` + history-driven generation; `reroute_demand` test on a derived network | report | 26 | 14 Jan |
| E6.6 | Demand profiles `low` / `peak` / `incident` on REAL-NET | route sets | 6 | 15 Jan |
| E6.7 | GP-8 (full pipeline from a new place name) and GP-11 (add an edge, a `run` request per ADR-0025: derive → reroute → baseline vs treatment) passing; `NetworkAuthorAgent` / `DemandGeneratorAgent` port implementations come with E6.1 / E6.2 | tests | 8 | 15 Jan |

### E7 — Integration (60 h) · DoD §5

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E7.1 | Golden-path test framework: expected-trace assertions over the trace log, per phase, starting at the Input Parser (`study-flows.md` §4); GP-1 … GP-5 | `golden/` | 10 | 27 Nov |
| E7.2 | GP-6 (dynamic path) and GP-7 (compare) | tests | 6 | 11 Dec |
| E7.3 | Failure-injection suite across all golden paths (netconvert, SUMO crash, invalid scenario, script lint/dry-run failure, tool timeout, agent budget exhausted); asserts `StepError.kind` and the rendered failure blocks (ADR-0025) | tests | 10 | 4 Feb |
| E7.4 | Cost / latency per golden path recorded; thresholds set from first measurement | table | 6 | 4 Feb |
| E7.5 | Full run: 11/11 golden paths × 3; GP-2 reproducibility (identical `result_id`s, hashes and conclusions) → **M6** | report | 10 | 5 Feb |
| E7.6 | Code freeze: tag, README, reproducibility package (one command per experiment in the thesis) | release | 12 | 10 Feb |
| E7.7 | *(Stretch, only if M6 is on time)* usability session with 2–3 DLR engineers | — | — | — |

### E8 — Thesis document (120 h) · rolling, concentrated 8 Feb → 18 Feb
Rule: a module's chapter section is drafted the week it reaches Done, while the details are fresh. Reserve Friday afternoons from November onward.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E8.1 | Outline mapped to epics; state-of-the-art chapter from the existing SoA matrix work | outline + SoA chapter | 16 | 30 Oct |
| E8.2 | Architecture & contracts chapter (from doc v1.0, ADRs) | chapter | 12 | 27 Nov |
| E8.3 | Evaluation methodology chapter (assets, banks, metrics, DoD approach) | chapter | 12 | 18 Dec |
| E8.4 | Module sections written at each Done (Builder/Runner, Expert, generators, Coordinator) | sections | 20 | rolling |
| E8.5 | Results chapter: DEV-NET, REAL-NET, learning-effect curve, calibration, ablation | chapter | 20 | 8 Feb |
| E8.6 | Discussion, limitations, threats to validity, conclusions | chapter | 12 | 12 Feb |
| E8.7 | Full draft to supervisors (FIB + DLR); revision round | draft v1 → v2 | 20 | 16 Feb |
| E8.8 | Final delivery | — | 8 | **18 Feb** |

---

## 2. Milestones

| ID | Date | Milestone | Acceptance check |
|---|---|---|---|
| **M0** | Fri 18 Sep | Foundations frozen | Contracts v1 merged; DEV-NET runs the three demand profiles; CI green; architecture v1.0 |
| **M1** | Fri 16 Oct | Tooling complete | All MCPs Done (§4.9); Builder & Runner Minimal; DEV-NET scenario matrix stored |
| **M2** | Fri 13 Nov | **Expert Done on DEV-NET** | Benchmark report meets every §4.7 threshold except REAL-NET and learning effect |
| **M3** | Fri 11 Dec | End-to-end loop | GP-1 … GP-7 pass; Builder & Runner Done. Natural point for a mid-stay review at DLR |
| **M4** | Fri 15 Jan | Real network ready | REAL-NET frozen with fix log; Network Author and Demand Generator Done; REAL-NET matrix and profiles stored; GP-8, GP-11 |
| **M5** | Fri 29 Jan | **Thesis result** | Expert Done on REAL-NET; learning-effect curve with CIs; calibration and ablation figures |
| **M6** | Fri 5 Feb | All modules Done | Coordinator (incl. request understanding), Output Composer Done; 11/11 golden paths × 3; failure injection |
| **M7** | Thu 18 Feb | Delivery | Code frozen and tagged (10 Feb); thesis delivered |

---

## 3. Calendar

Weeks start on Monday. "Fri PM writing" applies from 6 Nov.

| Week | Dates | Focus | Tasks | Milestone |
|---|---|---|---|---|
| W0 | 9–11 Sep | Foundations | E0.1, E0.2, start E0.3 | |
| W1 | 14–18 Sep | Foundations | E0.3–E0.8 | **M0** (18 Sep) |
| W2 | 21–25 Sep | MCPs | E1.1, start E1.2 | |
| W3 | 28 Sep–2 Oct | MCPs | E1.2–E1.6 | |
| W4 | 5–9 Oct | Runner + Builder | E2.1, start E2.2 | |
| W5 | 12–16 Oct | Builder + matrix | E2.2–E2.4, E3.1 | **M1** (16 Oct) |
| W6 | 19–23 Oct | Expert | E4.1, E3.2 | |
| W7 | 26–30 Oct | Expert | E4.2, E3.3, E8.1 | |
| W8 | 2–6 Nov | Expert | E4.3, E4.4 | |
| W9 | 9–13 Nov | Expert | E4.5, E4.6, E4.7 | **M2** (13 Nov) |
| W10 | 16–20 Nov | Coordinator | E3.4, E5.1, start E5.2 | |
| W11 | 23–27 Nov | Coordinator + loop | E5.2, E5.3, E5.4, E7.1, E8.2 | |
| W12 | 30 Nov–4 Dec | Runner online | E2.5 | |
| W13 | 7–11 Dec | Builder Done | E2.6, E2.7, E7.2 | **M3** (11 Dec) |
| W14 | 14–18 Dec | Network Author & Demand Generator Minimal | E6.1, E6.2, E8.3 | |
| — | 21 Dec–3 Jan | Break (low intensity) | E6.3 only (REAL-NET hand cleaning) | |
| W15 | 4–8 Jan | REAL-NET | finish E6.3, start E6.4 | |
| W16 | 11–15 Jan | Network Author & Demand Generator Done | E6.4–E6.7, E3.5 | **M4** (15 Jan) |
| W17 | 18–22 Jan | Expert on REAL-NET | E3.6, E4.8 | |
| W18 | 25–29 Jan | Thesis result | finish E4.8, E4.9, E4.10 | **M5** (29 Jan) |
| W19 | 1–5 Feb | Integration + Done | E5.5–E5.8, E7.3–E7.5 | **M6** (5 Feb) |
| W20 | 8–12 Feb | Writing | E7.6, E8.5, E8.6 | code freeze (10 Feb) |
| W21 | 15–18 Feb | Writing | E8.7, E8.8 | **M7** (18 Feb) |

Effort by month (approximate): Sep 134 h · Oct 175 h · Nov 179 h · Dec 114 h · Jan 172 h · Feb 120 h.

---

## 4. Dependencies worth watching

- E4 (Expert) cannot start benchmarking before E3.1–E3.3; E3.2 depends on E2.4's harness. If W5 slips, W6 absorbs it and E4.1 starts in parallel (it only needs E1).
- E5.3 (loop) needs E2.1 (batch Runner) and E4.5 (free mode). Both are scheduled before it.
- ADR-0025/0026 chain (added 2026-09-23): E5.9 (domain) → E3.4, E5.2 and E5.10; E4.11 (notes) → E5.10;
  E5.10 (Executor) → E5.3 and E7.1; E5.11 (failure render) → E5.5 and E7.3. E5.9, E4.11, E5.10 and
  E5.11 need no real model calls (fake `ToolAgent` and fake agent ports), so they can be pulled forward
  into any gap left by E4 work; the dates in the table are the latest that keep their consumers on time.
- E2.5 (sandbox + online Runner) is the only task in Phase B of E2 that has no fallback: without it GP-6 and the script half of §4.5 cannot pass. It depends on E1.2 (`traci_api`), scheduled two months earlier.
- E6.5 (calibration) and E6.1 (`probe_run`) both use the Runner as a tool: they depend on E2.1 (batch, ephemeral mode), scheduled in October.
- E6.4's derivation bank and E6.7's GP-11 depend on E6.2's `reroute_demand`; keep E6.2 before E6.4 even if W14 slips.
- E4.8 (Expert on REAL-NET) is blocked by E6.3 + E6.6 + E3.5. The Christmas break is used precisely to de-risk E6.3.
- E8.5 (results chapter) needs E4.9 and E4.10 figures; that is why M5 is before M6.

---

## 5. Fallback order if a milestone slips

Downgrade in this order, one step at a time, and record the downgrade in the thesis as a stated limitation:

1. E7.7 (already Stretch) — never scheduled.
2. E6.4 / E6.5 agent tuning → keep the v1 tool catalogue with a single prompt; drop the *agent stability over 3 runs* criterion (replay determinism and the derivation bank stay).
3. E6.5 history-driven demand generation → keep parameter-driven and count-calibrated only (`historical_demand` becomes an unimplemented optional capability; GP-10 still demonstrates negotiation).
4. E4.10 ablation → keep calibration analysis only.
5. E5.7 automatic traceability checker → manual rubric only.
6. E6.4 GEN-LOCATIONS 10/10 → 6/6 locations.
7. E2.7 Builder bank → drop the `custom` and `signal_program` script variants.

What must **not** be cut: M2, M3, M5. Those three are the thesis.

---

## 6. Weekly ritual (15 min, Friday)

1. Tick tasks in this file; move dates if needed, never delete the original date.
2. Check the next milestone's acceptance line against reality.
3. If behind by more than one week, apply the next item of §5 and note it.
4. Write the paragraph of the thesis corresponding to whatever reached Done this week.
