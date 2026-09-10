# Agentic Traffic Simulation Framework — Work Plan (v0.1)

Scope: reach **Done** on every module of the Architecture & DoD document (v0.2), plus the thesis document, between **Wed 9 Sep 2026** and **Thu 18 Feb 2027**. Stretch items are explicitly out of plan.

---

## 0. Capacity check

| | |
|---|---|
| Calendar span | 23 weeks (9 Sep → 18 Feb) |
| Minus Christmas break (21 Dec → 3 Jan, low-intensity work only) | ≈ 21 working weeks |
| Capacity at 40 h/week | ≈ 840 h |
| Planned effort (sum of all tasks below) | 870 h |
| Contingency | **none** (−30 h) |

The plan is overcommitted by ~4 % and has no buffer. That is deliberate: it tells you where you are at every milestone. Section 5 lists, in order, which *Done* criteria to downgrade to *Minimal* if a milestone slips. Do not add Stretch work before M6.

---

## 1. Epics and tasks

Estimates are in hours. "Due" is the end-of-day deadline. "DoD" points to the section of the Architecture & DoD document that the task satisfies.

### E0 — Foundations (70 h) · 9 Sep → 18 Sep

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E0.1 | Repo skeleton: hexagonal layout (domain / application / adapters), packaging, ruff, pytest, CI | repo + green CI | 8 | 10 Sep |
| E0.2 | Pin SUMO version; reproducible environment (Docker or pinned env, incl. a Postgres + `pgvector` service for E1.3); record in README | env + README | 4 | 10 Sep |
| E0.3 | Contracts v1 as Pydantic models: all §2.2 schemas, JSON-schema export, round-trip tests | `contracts/` package | 16 | 14 Sep |
| E0.4 | DatabaseMCP contract spec: tool names, I/O schemas, capability groups, error codes | `DATABASE_MCP_CONTRACT.md` | 8 | 15 Sep |
| E0.5 | DEV-NET: `netgenerate` grid + hand edits (2→1 merge bottleneck, signalised corridor), documented | `dev-net.net.xml` + doc | 10 | 16 Sep |
| E0.6 | Demand profiles `low` / `peak` / `incident` on DEV-NET, seeded; verify congestion levels (≈10–20 % edges congested at peak) | 3 route sets + verification notebook | 10 | 17 Sep |
| E0.7 | Trace logging: run id, step, tool call, artifacts, tokens → JSONL | `tracing/` | 8 | 18 Sep |
| E0.8 | Architecture doc frozen as v1.0 + ADRs for the decisions in §7 | `docs/` | 6 | 18 Sep |

### E1 — MCP servers (90 h) · 21 Sep → 2 Oct · DoD §4.9

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E1.1 | NetworkMCP: `get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`, `edges_in_bbox`, `capacity_estimate`, `get_tls`; ≥3 tests each incl. error case | server + tests | 20 | 24 Sep |
| E1.2 | TraciMCP: `close_lane`, `open_lane`, `set_speed`, `set_tls_program`, `get_edge_occupancy`, `get_edge_speed`, `get_vehicle_count`, `step`; tests with SUMO in the loop | server + tests | 16 | 28 Sep |
| E1.3 | DatabaseMCP reference implementation (Postgres + `pgvector` via SQLAlchemy Core, file store for large artifacts): `networks`, `scenarios`, `results`, `notes` (vector search via `pgvector`), `historical_demand` capability groups | server | 24 | 30 Sep |
| E1.4 | `find_similar_scenario` (exact hash match, else intervention + `context_tags` overlap) and `search_notes` with `status`/`basis` filters; 10 + 5 test cases | tests | 12 | 1 Oct |
| E1.5 | DatabaseMCP conformance suite runnable against any implementation | `conformance/` | 10 | 2 Oct |
| E1.6 | Capability-listing helper for the Coordinator; latency benchmark of every tool on DEV-NET | benchmark report | 8 | 2 Oct |

### E2 — Scenario Builder & Simulation Runner (110 h) · DoD §4.5, §4.6
Phase A (Minimal, 58 h): 5 Oct → 16 Oct. Phase B (Done, 52 h): 30 Nov → 11 Dec.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E2.1 | Runner batch mode: run `sumocfg`, collect edgedata/tripinfo/summary, build `SimulationResult`, store; byte-identical reproducibility test (20 runs) | runner + tests | 12 | 8 Oct |
| E2.2 | Builder Minimal: static `lane_closure` and `speed_limit` → rerouter / VSS `.add.xml` + `sumocfg`; id validation against NetworkMCP; SUMO load check | builder | 20 | 13 Oct |
| E2.3 | Builder static: `edge_closure`, `signal_program` (WAUT), `demand_scale` (delegates to Demand Generator parameters) | builder | 14 | 16 Oct |
| E2.4 | Effect-verification harness: per intervention type, read edgedata / `applied_actions` and assert the observable effect (§4.5) | `verify/` | 12 | 16 Oct |
| E2.5 | `TraciPlan` schema + Runner interpreter (online mode): `at_time`, `when(metric, target, op, value)`, all §2.4 actions, `applied_actions` log; unit test per trigger/action; unsupported entries rejected pre-start | interpreter + tests | 24 | 4 Dec |
| E2.6 | Builder dynamic strategy: condition → `TraciPlan` authoring; strategy-selection tests | builder | 14 | 8 Dec |
| E2.7 | Builder bank (25–30 specs covering every §2.4 cell); run to ≥27/30; structural-determinism check over 3 runs; rejection of unsupported specs with reason | bank + report | 14 | 11 Dec |

### E3 — Evaluation assets & harness (70 h)

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E3.1 | Scenario matrix DEV-NET / peak: 15–25 rows × 3 seeds, simulated and stored via DatabaseMCP | matrix in DB | 12 | 16 Oct |
| E3.2 | Question templates (descriptive / diagnostic / counterfactual) + generator + programmatic gold answers from the matrix; ≥60 questions on DEV-NET | question bank | 16 | 23 Oct |
| E3.3 | Metrics: exact match, Jaccard top-k, direction, magnitude band, Brier, abstention P/R; harness with repeated runs, mean ± std, report generation | `eval/` | 16 | 27 Oct |
| E3.4 | Request bank: 50+ NL requests (10+ ambiguous) with gold `ExperimentRequest` and gold plan for a fixed DB state | request bank | 12 | 18 Nov |
| E3.5 | Scenario matrix REAL-NET / peak | matrix in DB | 8 | 15 Jan |
| E3.6 | Question bank REAL-NET (40+) | question bank | 6 | 18 Jan |

### E4 — Network Expert (160 h) · DoD §4.7 · **research focus**
Phase A (DEV-NET, 110 h): 19 Oct → 13 Nov. Phase B (REAL-NET, 50 h): 18 Jan → 29 Jan.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E4.1 | Refactor the existing v1 onto contracts; replace direct file parsing with NetworkMCP / DatabaseMCP tools; `evidence[]` on every answer | expert v2 | 16 | 22 Oct |
| E4.2 | Descriptive questions to Done on DEV-NET (≥90 %) | benchmark run | 14 | 27 Oct |
| E4.3 | Diagnostic questions to Done (Jaccard ≥0.6; "why" rubric ≥70 %) | benchmark run | 18 | 2 Nov |
| E4.4 | Counterfactual, forced mode: reasoning strategy over graph + facts, `confidence` and `basis` output; direction ≥75 %, band ≥50 % | benchmark run | 24 | 6 Nov |
| E4.5 | Free mode: abstention policy, `proposed_experiment` generation; abstention recall ≥70 %, false requests ≤30 % | benchmark run | 14 | 10 Nov |
| E4.6 | `ExpertNote` writing after each experiment, RAG over notes, `status` update on confirm/refute; knowledge-hygiene probes (20) | notes pipeline + tests | 16 | 12 Nov |
| E4.7 | DEV-NET benchmark report: all §4.7 metrics, 3 runs, mean ± std → **M2** | report | 8 | 13 Nov |
| E4.8 | Port to REAL-NET, tune, full benchmark (descriptive ≥85 %, Jaccard ≥0.5, direction ≥65 %) | report | 24 | 26 Jan |
| E4.9 | Learning-effect experiment: store size 0 / 5 / 15 / 25, held-out interventions, confidence intervals, plot | figure + data | 18 | 29 Jan |
| E4.10 | Calibration analysis (Brier, accuracy by `basis`) and ablation facts-only vs facts + notes | figures | 8 | 29 Jan |

### E5 — Coordinator, Input Parser, Output Composer (100 h) · DoD §4.1, §4.2, §4.8
Phase A (Minimal + loop, 54 h): 16 Nov → 27 Nov. Phase B (Done, 46 h): 1 Feb → 5 Feb.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E5.1 | Input Parser: LLM → `ExperimentRequest`, retry-then-fail, ambiguity flagging; evaluate on request bank to Done (§4.1) | parser + report | 14 | 18 Nov |
| E5.2 | Coordinator Minimal: planner for the 4 canonical DB states, sequential executor, state persistence per step | coordinator | 20 | 23 Nov |
| E5.3 | Loop closure: `needs_simulation` → run proposed experiment → re-ask; GP-3 / GP-4 / GP-5 passing | tests | 14 | 26 Nov |
| E5.4 | Output Composer Minimal: `ExpertAnswer` + experiments → Markdown with evidence table | composer | 6 | 27 Nov |
| E5.5 | Coordinator Done: routing accuracy ≥90 % vs gold plans; zero redundant simulations; failure injection yields named failing step | report | 18 | 3 Feb |
| E5.6 | Capability negotiation with DatabaseMCP; GP-10 | tests | 8 | 3 Feb |
| E5.7 | Output Composer Done: automatic traceability checker (numbers ↔ artifacts); faithfulness rubric on 20 reports | checker + report | 12 | 5 Feb |
| E5.8 | Stability: 3 repeated runs of Input Parser and Coordinator benchmarks | report | 8 | 5 Feb |

### E6 — Network Generator, Demand Generator, REAL-NET (90 h) · DoD §4.3, §4.4
14 Dec → 18 Dec, low-intensity over the break, 4 Jan → 15 Jan.

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E6.1 | Network Generator Minimal: place / bbox → OSM → `netconvert` → stored `Network` with source and parameters | generator | 12 | 16 Dec |
| E6.2 | Demand Generator Minimal: parameters → `randomTrips` + `duarouter`, teleport ≤2 %, seeded, hash-deterministic | generator | 10 | 18 Dec |
| E6.3 | REAL-NET: choose district (300–800 edges), hand-clean, **freeze**, document every fix (also usable as GEN error taxonomy) | `real-net.net.xml` + doc | 16 | 6 Jan |
| E6.4 | Network Generator Done: sanity report (SCC ≥95 %, no zero-length, fringe reachability), 10/10 on GEN-LOCATIONS, topology modifications 10/10, idempotency | report | 18 | 11 Jan |
| E6.5 | Demand Generator Done: target fidelity ±15 % DEV / ±25 % REAL at measurement edges; synthetic `historical_demand` dataset + history-driven generation; `fidelity` object | report | 22 | 14 Jan |
| E6.6 | Demand profiles `low` / `peak` / `incident` on REAL-NET | route sets | 6 | 15 Jan |
| E6.7 | GP-8 (full pipeline from a new place name) passing | test | 6 | 15 Jan |

### E7 — Integration (60 h) · DoD §5

| ID | Task | Output | h | Due |
|---|---|---|---|---|
| E7.1 | Golden-path test framework: expected-trace assertions over the trace log; GP-1 … GP-5 | `golden/` | 10 | 27 Nov |
| E7.2 | GP-6 (dynamic path) and GP-7 (compare) | tests | 6 | 11 Dec |
| E7.3 | Failure-injection suite across all golden paths (netconvert, SUMO crash, invalid scenario, tool timeout) | tests | 10 | 4 Feb |
| E7.4 | Cost / latency per golden path recorded; thresholds set from first measurement | table | 6 | 4 Feb |
| E7.5 | Full run: 10/10 golden paths × 3; GP-2 reproducibility (identical hashes and conclusions) → **M6** | report | 10 | 5 Feb |
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
| **M4** | Fri 15 Jan | Real network ready | REAL-NET frozen; generators Done; REAL-NET matrix and profiles stored; GP-8 |
| **M5** | Fri 29 Jan | **Thesis result** | Expert Done on REAL-NET; learning-effect curve with CIs; calibration and ablation figures |
| **M6** | Fri 5 Feb | All modules Done | Coordinator, Input Parser, Output Composer Done; 10/10 golden paths × 3; failure injection |
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
| W14 | 14–18 Dec | Generators Minimal | E6.1, E6.2, E8.3 | |
| — | 21 Dec–3 Jan | Break (low intensity) | E6.3 only (REAL-NET hand cleaning) | |
| W15 | 4–8 Jan | REAL-NET | finish E6.3, start E6.4 | |
| W16 | 11–15 Jan | Generators Done | E6.4–E6.7, E3.5 | **M4** (15 Jan) |
| W17 | 18–22 Jan | Expert on REAL-NET | E3.6, E4.8 | |
| W18 | 25–29 Jan | Thesis result | finish E4.8, E4.9, E4.10 | **M5** (29 Jan) |
| W19 | 1–5 Feb | Integration + Done | E5.5–E5.8, E7.3–E7.5 | **M6** (5 Feb) |
| W20 | 8–12 Feb | Writing | E7.6, E8.5, E8.6 | code freeze (10 Feb) |
| W21 | 15–18 Feb | Writing | E8.7, E8.8 | **M7** (18 Feb) |

Effort by month (approximate): Sep 130 h · Oct 175 h · Nov 175 h · Dec 110 h · Jan 160 h · Feb 120 h.

---

## 4. Dependencies worth watching

- E4 (Expert) cannot start benchmarking before E3.1–E3.3; E3.2 depends on E2.4's harness. If W5 slips, W6 absorbs it and E4.1 starts in parallel (it only needs E1).
- E5.3 (loop) needs E2.1 (batch Runner) and E4.5 (free mode). Both are scheduled before it.
- E2.5 (interpreter) is the only task in Phase B of E2 that has no fallback: without it GP-6 and the dynamic half of §4.5 cannot pass.
- E4.8 (Expert on REAL-NET) is blocked by E6.3 + E6.6 + E3.5. The Christmas break is used precisely to de-risk E6.3.
- E8.5 (results chapter) needs E4.9 and E4.10 figures; that is why M5 is before M6.

---

## 5. Fallback order if a milestone slips

Downgrade in this order, one step at a time, and record the downgrade in the thesis as a stated limitation:

1. E7.7 (already Stretch) — never scheduled.
2. E6.5 history-driven demand generation → keep parameter-driven only (`historical_demand` becomes an unimplemented optional capability; GP-10 still demonstrates negotiation).
3. E4.10 ablation → keep calibration analysis only.
4. E5.7 automatic traceability checker → manual rubric only.
5. E6.4 GEN-LOCATIONS 10/10 → 6/6 locations.
6. E2.7 Builder bank → drop `signal_program` dynamic variant.

What must **not** be cut: M2, M3, M5. Those three are the thesis.

---

## 6. Weekly ritual (15 min, Friday)

1. Tick tasks in this file; move dates if needed, never delete the original date.
2. Check the next milestone's acceptance line against reality.
3. If behind by more than one week, apply the next item of §5 and note it.
4. Write the paragraph of the thesis corresponding to whatever reached Done this week.
