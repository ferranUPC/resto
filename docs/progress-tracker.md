# Progress tracker

Tracks completion of every task in [`tfm-work-plan.md`](tfm-work-plan.md). Task descriptions here are shortened for scanning — the source of truth for scope, outputs and DoD thresholds is `tfm-work-plan.md` (epics/hours/due dates) and `tfm-architecture-and-dod.md` (per-module DoD, §4.x).

Status: ⬜ not started · 🔄 in progress · ✅ done (meets its Done/threshold from the DoD, not just "code exists")

Last updated: 2026-09-11

**Summary: 0 / 65 tasks done (0%) · 1 in progress** (E7.7 is Stretch, never scheduled — excluded from the count, per work plan §5)

---

## E0 — Foundations (8 tasks) · due 18 Sep

| ID | Task | Status | Notes |
|---|---|---|---|
| E0.1 | Repo skeleton: hexagonal layout, packaging, ruff, pytest, CI | 🔄 | No commits since last review (2026-09-10) — same state. `pyproject.toml` + ruff + pytest still green locally (11 passed, `ruff check .` clean). `.github/workflows/ci.yml` still triggers on `push: branches: [main]` against a `master` repo — still 0 workflow runs recorded on GitHub. Was due 10 Sep; now overdue by one day with no fix applied to the one-line branch bug flagged last review |
| E0.2 | Pin SUMO version; reproducible environment; record in README | ⬜ | No change since last review. README still conda-instructions-only; no SUMO version pinned; no Docker/Postgres+pgvector service defined anywhere in the repo. Was due 10 Sep; now overdue by one day |
| E0.3 | Contracts v1 as Pydantic models: all §2.2 schemas, JSON-schema export, round-trip tests | ⬜ | Domain entities (plain dataclasses, not Pydantic) for `Network`, `Scenario`, `Intervention`, `TraciPlan` exist ahead of schedule in `domain/`; the Pydantic boundary contracts for the rest of §2.2 are not started |
| E0.4 | DatabaseMCP contract spec (tool names, I/O schemas, capability groups, error codes) | ⬜ | |
| E0.5 | DEV-NET: grid + hand edits (bottleneck, signalised corridor) | ⬜ | |
| E0.6 | Demand profiles low/peak/incident on DEV-NET, seeded | ⬜ | |
| E0.7 | Trace logging: run id, step, tool call, artifacts, tokens → JSONL | ⬜ | |
| E0.8 | Architecture doc frozen as v1.0 + ADRs for §7 decisions | ⬜ | §7 already has the Postgres/pgvector decision recorded; doc not yet frozen/tagged v1.0 |

## E1 — MCP servers (6 tasks) · due 2 Oct · DoD §4.9

| ID | Task | Status | Notes |
|---|---|---|---|
| E1.1 | NetworkMCP (7 read tools + tests incl. error case) | ⬜ | |
| E1.2 | TraciMCP (8 primitives + tests with SUMO in the loop) | ⬜ | |
| E1.3 | DatabaseMCP reference impl (Postgres + `pgvector` via SQLAlchemy Core, file store) | ⬜ | |
| E1.4 | `find_similar_scenario` + `search_notes` (10 + 5 test cases) | ⬜ | |
| E1.5 | DatabaseMCP conformance suite | ⬜ | |
| E1.6 | Capability-listing helper for Coordinator; latency benchmark | ⬜ | |

## E2 — Scenario Builder & Simulation Runner (7 tasks) · DoD §4.5, §4.6

| ID | Task | Status | Notes |
|---|---|---|---|
| E2.1 | Runner batch mode + reproducibility test (20 runs) | ⬜ | |
| E2.2 | Builder Minimal: static `lane_closure`/`speed_limit` → `.add.xml` + `sumocfg` | ⬜ | Discussed design (mechanism-per-writer, dispatch via `supports()`), not implemented |
| E2.3 | Builder static: `edge_closure`, `signal_program` (WAUT), `demand_scale` | ⬜ | |
| E2.4 | Effect-verification harness | ⬜ | |
| E2.5 | `TraciPlan` interpreter (online mode) + unit tests per trigger/action | ⬜ | |
| E2.6 | Builder dynamic strategy: condition → `TraciPlan` authoring | ⬜ | |
| E2.7 | Builder bank (25–30 specs) run to ≥27/30 | ⬜ | |

## E3 — Evaluation assets & harness (6 tasks)

| ID | Task | Status | Notes |
|---|---|---|---|
| E3.1 | Scenario matrix DEV-NET/peak (15–25 rows × 3 seeds) | ⬜ | |
| E3.2 | Question templates + generator + gold answers (≥60 on DEV-NET) | ⬜ | |
| E3.3 | Metrics harness (exact match, Jaccard, direction, band, Brier, abstention P/R) | ⬜ | |
| E3.4 | Request bank (50+ NL requests, 10+ ambiguous) | ⬜ | |
| E3.5 | Scenario matrix REAL-NET/peak | ⬜ | |
| E3.6 | Question bank REAL-NET (40+) | ⬜ | |

## E4 — Network Expert, research focus (10 tasks) · DoD §4.7

| ID | Task | Status | Notes |
|---|---|---|---|
| E4.1 | Refactor v1 onto contracts; NetworkMCP/DatabaseMCP tools; `evidence[]` | ⬜ | |
| E4.2 | Descriptive questions to Done on DEV-NET (≥90%) | ⬜ | |
| E4.3 | Diagnostic questions to Done (Jaccard ≥0.6; "why" rubric ≥70%) | ⬜ | |
| E4.4 | Counterfactual, forced mode (direction ≥75%, band ≥50%) | ⬜ | |
| E4.5 | Free mode: abstention policy, `proposed_experiment` | ⬜ | |
| E4.6 | `ExpertNote` writing + RAG + status update; hygiene probes (20) | ⬜ | |
| E4.7 | DEV-NET benchmark report (3 runs, mean±std) → **M2** | ⬜ | |
| E4.8 | Port to REAL-NET, full benchmark | ⬜ | |
| E4.9 | Learning-effect experiment (0/5/15/25, CIs, plot) | ⬜ | |
| E4.10 | Calibration analysis + ablation | ⬜ | |

## E5 — Coordinator, Input Parser, Output Composer (8 tasks) · DoD §4.1, §4.2, §4.8

| ID | Task | Status | Notes |
|---|---|---|---|
| E5.1 | Input Parser: LLM → `ExperimentRequest`, retry-then-fail, ambiguity flagging | ⬜ | |
| E5.2 | Coordinator Minimal: planner for 4 canonical DB states | ⬜ | |
| E5.3 | Loop closure: `needs_simulation` → run → re-ask; GP-3/4/5 | ⬜ | `BuildAndRunExperimentUseCase` stub created in `application/use_cases/` (empty, `NotImplementedError`) |
| E5.4 | Output Composer Minimal: `ExpertAnswer` + experiments → Markdown | ⬜ | |
| E5.5 | Coordinator Done: routing ≥90%, zero redundant sims, failure injection | ⬜ | |
| E5.6 | Capability negotiation with DatabaseMCP; GP-10 | ⬜ | |
| E5.7 | Output Composer Done: automatic traceability checker | ⬜ | |
| E5.8 | Stability: 3 repeated runs of Input Parser + Coordinator benchmarks | ⬜ | |

## E6 — Network Generator, Demand Generator, REAL-NET (7 tasks) · DoD §4.3, §4.4

| ID | Task | Status | Notes |
|---|---|---|---|
| E6.1 | Network Generator Minimal: place/bbox → OSM → `netconvert` | ⬜ | |
| E6.2 | Demand Generator Minimal: `randomTrips` + `duarouter`, teleport ≤2% | ⬜ | |
| E6.3 | REAL-NET: choose district, hand-clean, freeze, document fixes | ⬜ | |
| E6.4 | Network Generator Done (sanity report, 10/10 GEN-LOCATIONS, idempotency) | ⬜ | |
| E6.5 | Demand Generator Done (fidelity ±15%/±25%, history-driven) | ⬜ | |
| E6.6 | Demand profiles low/peak/incident on REAL-NET | ⬜ | |
| E6.7 | GP-8 (full pipeline from a new place name) passing | ⬜ | |

## E7 — Integration (7 tasks, 1 Stretch) · DoD §5

| ID | Task | Status | Notes |
|---|---|---|---|
| E7.1 | Golden-path test framework; GP-1…GP-5 | ⬜ | |
| E7.2 | GP-6 (dynamic path) and GP-7 (compare) | ⬜ | |
| E7.3 | Failure-injection suite across golden paths | ⬜ | |
| E7.4 | Cost/latency per golden path recorded | ⬜ | |
| E7.5 | Full run: 10/10 golden paths × 3 → **M6** | ⬜ | |
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

| ID | Date | Milestone | Status |
|---|---|---|---|
| M0 | 18 Sep | Foundations frozen | ⬜ |
| M1 | 16 Oct | Tooling complete | ⬜ |
| M2 | 13 Nov | **Expert Done on DEV-NET** | ⬜ |
| M3 | 11 Dec | End-to-end loop | ⬜ |
| M4 | 15 Jan | Real network ready | ⬜ |
| M5 | 29 Jan | **Thesis result** | ⬜ |
| M6 | 5 Feb | All modules Done | ⬜ |
| M7 | 18 Feb | Delivery | ⬜ |

---

## Update ritual

Update this file whenever a task's status changes (not just on the Friday ritual from `tfm-work-plan.md` §6) — flip its ⬜/🔄/✅ and refresh the summary line at the top. A task only becomes ✅ once it meets its DoD, not when the code merely exists.
