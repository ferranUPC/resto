# Agentic Traffic Simulation Framework — Architecture & Definition of Done (v0.2)

Status: second iteration. Changes vs v0.1: Scenario Builder added; Simulation Runner is now a pure executor driven by a declarative TraCI plan; Network Generator restricted to topology; DatabaseMCP defined as a standard contract with pluggable backends and capability discovery; knowledge model of the Expert made explicit; evaluation assets illustrated with examples; §7 questions resolved. All *(threshold)* values remain placeholders until first measurements.

---

## 1. Design principles

1. **Evaluation first.** Every module has a *Minimal* version (the framework runs end-to-end), a *Done* criterion (metric + threshold + test asset) and a *Stretch* level. The thesis can stop at any point where every module is at least *Minimal* and the research focus (Network Expert) is *Done*.
2. **Typed contracts between modules.** Modules communicate through validated schemas (Pydantic), never free text. This makes routing testable and results reproducible.
3. **Authoring is agentic, execution is not.** LLM agents write plans, configurations and opinions. Anything that touches SUMO at runtime is deterministic code interpreting what the agents wrote.
4. **Simulation is the ground truth.** SUMO decides what is true. Agents are evaluated against simulation, never against other agents.
5. **Determinism where possible.** Every non-LLM step is seeded and reproducible. LLM steps are evaluated statistically (repeated runs).
6. **Every answer carries evidence.** No module produces a claim that cannot be traced to an artifact.
7. **Ports and adapters.** Agents depend on tool interfaces (MCP contracts), not on implementations. SUMO, the database and the file system sit behind adapters.

---

## 2. Final architecture

### 2.1 Layers and modules

```
┌─────────────────────────────── Interface ───────────────────────────────┐
│   Input Parser  ──►  ExperimentRequest                Output Composer   │
└──────────────────────────┬──────────────────────────────────▲───────────┘
                           ▼                                  │
┌─────────────────────── Orchestration ───────────────────────┴───────────┐
│                      Experiment Coordinator                             │
│   (plans, routes, tracks state, closes the Expert ↔ Simulation loop)    │
└──────┬─────────────────────────────────────────────────┬────────────────┘
       │                                                 │
       ▼                                                 ▼
┌── Authoring (agentic) ──────────────────┐   ┌── Reasoning (agentic) ────────┐
│ Network Generator   (topology)          │   │ Network Expert                │
│ Demand Generator    (routes / trips)    │◄──│  descriptive / diagnostic /   │
│ Scenario Builder    (SUMO config,       │   │  counterfactual;              │
│                      additionals,       │   │  free / forced mode           │
│                      TraCI plan)        │   └───────────────┬───────────────┘
└──────────────────────┬──────────────────┘                   │
                       ▼                                      │
┌── Execution (deterministic code) ───────┐                   │
│ Simulation Runner                       │                   │
│   batch: sumo + sumocfg                 │───────────────────┤
│   online: TraCI plan interpreter        │                   │
└──────────────────────┬──────────────────┘                   │
                       ▼                                      ▼
┌─────────────────────────── Tools (MCP) ─────────────────────────────────┐
│  NetworkMCP     DatabaseMCP (contract; pluggable backend)     TraciMCP  │
└─────────────────────────────────────────────────────────────────────────┘
```

Key structural decisions:

- **Authoring vs execution.** SUMO expertise lives in the authoring agents. The Runner never decides anything; it executes what the Builder wrote.
- **Static by default, dynamic by exception.** Interventions are implemented with SUMO's static mechanisms (rerouters, additional files, TAZ, vTypes) whenever the intervention is fixed in advance. TraCI is used only when the intervention depends on runtime state.
- **TraCI plan.** Dynamic interventions are expressed as data (a declarative `TraciPlan`), not as generated code. The Runner contains a small interpreter written once. LLM-generated Python scripts are Stretch.
- **Loop.** Expert → Coordinator → Builder → Runner → Expert is the central mechanism of the framework.

### 2.2 Data contracts

| Contract | Produced by | Consumed by | Essential fields |
|---|---|---|---|
| `ExperimentRequest` | Input Parser | Coordinator | `intent` (describe / diagnose / counterfactual / run_experiment / compare), `network_ref`, `demand_ref`, `interventions[]`, `metrics_of_interest[]`, `time_window`, `mode` (free / forced; user flag), `context_tags[]`, `ambiguities[]` |
| `Intervention` | Input Parser, Expert | Builder | `type` ∈ {`lane_closure`, `edge_closure`, `speed_limit`, `demand_scale`, `signal_program`}, `target` (edge/lane/TLS/TAZ id), `params`, `window` (fixed `[t_start, t_end]`) **or** `condition` (runtime predicate) |
| `ExperimentPlan` | Coordinator | Coordinator (executor) | ordered `steps[]` (`module`, `inputs`, `expected_artifacts`, `depends_on`), `rationale`, `reuse_decisions[]` |
| `Network` | Network Generator | Builder, Expert, DatabaseMCP | `network_id`, `net_xml`, `source` (osm bbox / place / file), `sanity_report`, content hash |
| `Demand` | Demand Generator | Builder, DatabaseMCP | `demand_id`, `network_id`, route/trip files, `profile` (low / peak / incident / custom), `seed`, `fidelity` (target vs achieved per measurement edge), content hash |
| `Scenario` | Scenario Builder | Runner, DatabaseMCP, Expert | `scenario_id`, `network_id`, `demand_id`, `sumocfg`, `additional_files[]`, `traci_plan` (optional), `interventions[]`, `strategy_per_intervention` (static / dynamic), `context_tags[]` (e.g. `rain`, `football_match`, `school_day`), `seed`, content hash |
| `TraciPlan` | Scenario Builder | Runner | `entries[]`, each `{trigger, action}`. Trigger: `at_time(t)` or `when(metric, target, op, value)`. Action: one TraciMCP primitive with typed params. Plus `poll_interval` |
| `SimulationResult` | Runner | DatabaseMCP, Expert | `result_id`, `scenario_id`, paths to edgedata / tripinfo / summary, aggregate KPIs, `applied_actions[]` (what the interpreter actually executed and when), `sumo_version`, `seed`, `status` (ok / failed + message) |
| `ExpertAnswer` | Network Expert | Coordinator, Output Composer | `answer`, `evidence[]`, `confidence` (0–1), `basis` (observed / inferred / extrapolated), `needs_simulation`, `proposed_experiment` (optional `ExperimentRequest`) |
| `ExpertNote` | Network Expert | DatabaseMCP (RAG) | `network_id`, `scenario_id`, prose summary written after an experiment, `provenance` (simulation / opinion), `basis`, `status` (unverified / confirmed / refuted), `context_tags[]` |
| `Report` | Output Composer | User | rendered answer, evidence table, experiments run, mode, limitations |

### 2.3 Module responsibilities

**Input Parser.** Natural language → `ExperimentRequest`. Records missing/ambiguous information in `ambiguities[]` instead of guessing. May be merged into the Coordinator if it stays trivial.

**Experiment Coordinator.** Given a request and the database state, produces and executes an `ExperimentPlan`. Decisions: (1) network exists or generate; (2) demand exists or generate; (3) matching scenario/result exists (`find_similar_scenario`) or build + run; (4) Expert can answer from existing results, or a simulation is needed; (5) in *free* mode, if the Expert returns `needs_simulation`, schedule the proposed experiment and re-ask; in *forced* mode, accept the answer. Owns state tracking, error recovery and capability negotiation with the DatabaseMCP.

**Network Generator.** Topology only. Creates a network from place / bbox / file (OSM → `netconvert`), applies topology modifications (`edge_closure` when permanent, geometry, lane count), runs sanity checks, stores the `Network`. Does *not* implement time-bounded closures; those are the Builder's job.

**Demand Generator.** Produces routes/trips for a network from explicit parameters, historical data (DatabaseMCP) or a default generator (`randomTrips`). Reports `fidelity`. Seeded.

**Scenario Builder.** The SUMO expert of the framework. Takes `Network` + `Demand` + `interventions[]` and produces a runnable `Scenario`:

- Chooses a **strategy** per intervention: *static* if the intervention has a fixed `window`, *dynamic* if it has a `condition`.
- Static: writes additional files — rerouters (`closingReroute`, `closingLaneReroute`), `variableSpeedSign`, TLS programs, TAZ edits, vType distributions — and the `sumocfg`.
- Dynamic: writes a `TraciPlan`.
- Validates the scenario (SUMO accepts it, ids exist in the network) before handing it to the Runner.

**Simulation Runner.** Deterministic code, no LLM. Batch mode: runs `sumo` on the `sumocfg`. Online mode: runs SUMO under TraCI and executes the `TraciPlan` with a small interpreter (step, evaluate triggers, call primitive, log `applied_actions`). Produces `SimulationResult`. Same scenario + seed → identical output.

**Network Expert.** Answers descriptive, diagnostic and counterfactual questions about a specific network. Two modes: *free* (may abstain and propose an experiment) and *forced* (must answer with `basis` and `confidence`). Knowledge model, deliberately mixed:

- *Facts via tools* — edgedata, KPIs, scenario metadata and the network graph are reached through NetworkMCP/DatabaseMCP queries, never embedded in a vector store.
- *Opinions via RAG* — `ExpertNote`s written by the Expert after each experiment, plus human engineer notes. Each note carries `provenance`, `basis` and `status`, so an old extrapolated opinion is never retrieved as if it were an observed fact. When a later simulation confirms or refutes a note, its `status` is updated.

Never runs SUMO itself.

**Output Composer.** `ExpertAnswer` + experiment list → `Report`. Every claim links to evidence. No reasoning of its own.

**NetworkMCP.** Read-only queries on a `.net.xml`: `get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`, `edges_in_bbox`, `capacity_estimate`, `get_tls`. Pure functions.

**DatabaseMCP.** A **standard contract** with a pluggable backend. The framework ships one reference implementation; a user may implement their own as long as it exposes the same tool names and schemas. Tools grouped by capability:

| Capability | Tools | Required? |
|---|---|---|
| `networks` | `store_network`, `get_network`, `list_networks` | yes |
| `scenarios` | `store_scenario`, `get_scenario`, `find_similar_scenario(network_id, interventions, context_tags)` | yes |
| `results` | `store_result`, `get_result`, `list_results(scenario_id)` | yes |
| `notes` | `store_note`, `search_notes(query, network_id, filters)`, `update_note_status` | yes |
| `historical_demand` | `get_historical_demand(network_id, day_type, hour)` | optional |

**Capability discovery**: at start-up the Coordinator lists the tools of the connected DatabaseMCP and derives which capabilities are present. Missing required capabilities → hard failure with a clear message. Missing `historical_demand` → the Demand Generator falls back to parameter-driven generation and the plan records the fallback. Discovery is about *capabilities*, not about data formats: data formats are fixed by the contract.

**TraciMCP.** Thin typed wrappers over TraCI primitives, no LLM: `close_lane`, `open_lane`, `set_speed`, `set_tls_program`, `get_edge_occupancy`, `get_edge_speed`, `get_vehicle_count`, `step`. Two consumers: the Runner's interpreter (v1) and, as Stretch, a live agent choosing calls from the catalogue.

### 2.4 Intervention → mechanism table (Builder's decision rules)

| Intervention | Fixed window (static) | Runtime condition (dynamic) |
|---|---|---|
| `lane_closure` | rerouter with `closingLaneReroute` in an `.add.xml` | `TraciPlan`: `when(...) → close_lane` |
| `edge_closure` | rerouter with `closingReroute`; permanent → Network Generator removes the edge | `TraciPlan`: `when(...) → close_lane` on all lanes |
| `speed_limit` | `variableSpeedSign` with a time profile | `TraciPlan`: `when(...) → set_speed` |
| `demand_scale` | Demand Generator regenerates with scale factor (no runtime mechanism needed) | not supported in v1 |
| `signal_program` | TLS program in `.add.xml` with `WAUT` switching | `TraciPlan`: `when(...) → set_tls_program` |

---

## 3. Evaluation assets

Build these before finishing any module.

| Asset | Purpose | Description |
|---|---|---|
| **DEV-NET** | Development, unit tests | Synthetic grid (e.g. 5×5, 200 m blocks), one designed bottleneck (2→1 lane merge), one signalised corridor. Answers are known by construction. |
| **REAL-NET** | Final Expert evaluation | Small real OSM district (~300–800 edges), cleaned by hand **once and frozen**. Answers are only known via simulation. Not used to evaluate the Network Generator (see §4.3). |
| **GEN-LOCATIONS** | Network Generator evaluation | 10 raw OSM locations (grid-like and irregular), never hand-cleaned. |
| **Demand profiles** | Both networks | `low`, `peak`, `incident`, seeded. |
| **Scenario matrix** | Ground truth for counterfactuals; experiment store for the learning-effect experiment | See example below. |
| **Question bank** | Expert benchmark | Template-generated, labelled, gold answers computed from the matrix. |
| **Request bank** | Input Parser and Coordinator benchmark | NL requests + gold `ExperimentRequest` + gold plan for a fixed DB state. |
| **Builder bank** | Scenario Builder benchmark | 25–30 `interventions[]` specs covering every row of §2.4, each with the expected observable effect. |

**Scenario matrix, example (DEV-NET / peak):**

| scenario_id | interventions | strategy | seeds |
|---|---|---|---|
| S00 | baseline | — | 1, 2, 3 |
| S01 | lane_closure E12 lane 1, 08:00–09:00 | static | 1, 2, 3 |
| S02 | edge_closure E07, 08:00–09:00 | static | 1, 2, 3 |
| S03 | speed_limit corridor C, 30 km/h, 07:00–10:00 | static | 1, 2, 3 |
| S04 | demand_scale ×1.2 | static (regenerate) | 1, 2, 3 |
| S05 | lane_closure E12 lane 1 when occupancy(E12) > 0.8 | dynamic | 1, 2, 3 |
| … | 15–25 rows per network | | |

**Question bank, example templates** (parameters drawn from the matrix and the network):

| Type | Template | Gold answer computed from |
|---|---|---|
| Descriptive | Which edges exceed {X} % occupancy between {t1} and {t2} in {scenario}? | edgedata of that scenario |
| Descriptive | What is the mean travel time on {E} in {scenario}? | edgedata |
| Diagnostic | Which three edges form the main bottleneck in {scenario} and why? | top-3 by delay × flow; "why" graded by rubric (merge / signal / demand) |
| Counterfactual | If {intervention}, does mean delay on {E'} increase, decrease or stay within ±5 %? | S_intervention vs S00 |
| Counterfactual | If {intervention}, which five edges change most in delay? | delta between rows, top-5 |
| Counterfactual | By roughly how much does network-wide mean delay change if {intervention}? | delta, graded in magnitude bands |

**Request bank, example entry:**

- NL: "Close the right lane on Main St during the morning peak and tell me what happens to delay."
- Gold `ExperimentRequest`: `intent=counterfactual`, `interventions=[lane_closure(target=E12 lane 1, window=07:00–10:00)]`, `metrics_of_interest=[delay]`, `mode=free`.
- DB state: network + peak demand exist, no matching scenario.
- Gold plan: Builder → Runner → Expert → Output (no Network Generator, no Demand Generator).

**Counterfactual metrics** (used in §4.7): direction accuracy; magnitude band (<5 %, 5–20 %, 20–50 %, >50 %); affected-set overlap (Jaccard, top-k); calibration (Brier score of `confidence`; accuracy conditioned on `basis`); abstention quality (precision/recall of `needs_simulation` against the questions forced mode gets wrong).

---

## 4. Definition of Done per module

### 4.1 Input Parser

- **Minimal**: LLM → JSON → Pydantic `ExperimentRequest`; one retry, then explicit failure.
- **Done**: schema validity ≥ 98 % on the request bank; field-level match vs gold ≥ 85 % on `intent`, `interventions`, `metrics_of_interest`; ≥ 80 % of ambiguous requests produce a non-empty `ambiguities[]`; `intent` agreement across 3 repeated runs ≥ 95 % *(thresholds)*.
- **Stretch**: clarification turn before dispatch.

### 4.2 Experiment Coordinator

- **Minimal**: sequential plans for the four canonical states (nothing / network / network + demand / results exist); persists state per step.
- **Done**:
  - Routing accuracy vs gold plans ≥ 90 % on the request bank *(threshold)*.
  - Zero redundant simulations (scenario hash already in store → reused).
  - Loop closure verified on 10 cases: `needs_simulation` → exactly the proposed experiment → re-ask.
  - Capability negotiation: with a DatabaseMCP lacking `historical_demand`, plans fall back correctly and record it; with a DatabaseMCP lacking a required capability, start-up fails with a clear message.
  - Injected failures (netconvert, SUMO crash, invalid scenario) yield a failed plan naming the step; never partial success reported as success.
- **Stretch**: parallel independent experiments; replanning on failure.

### 4.3 Network Generator (topology only)

- **Minimal**: place / bbox → OSM → `netconvert` → `.net.xml` that loads in SUMO; stored with source and parameters.
- **Done** (on GEN-LOCATIONS, never on REAL-NET):
  - 10/10 locations produce a loadable network *(threshold)*.
  - Sanity report: largest strongly connected component ≥ 95 % of edges; no zero-length edges; every edge reachable from a fringe edge *(threshold)*.
  - Topology modifications (permanent edge removal, lane count change, speed attribute change) applied from spec and verified by re-reading: 10/10 test modifications.
  - Idempotent: same inputs → identical hash.
- **Stretch**: LLM-assisted cleanup of OSM artefacts, evaluated by teleport reduction on fixed demand.

### 4.4 Demand Generator

- **Minimal**: `vehicles_per_hour` + window → `randomTrips` + `duarouter` → runs with teleports ≤ 2 % *(threshold)*; seeded.
- **Done**:
  - Target fidelity at 3–5 measurement edges: within ±15 % on DEV-NET, ±25 % on REAL-NET *(threshold)*.
  - History-driven generation from `historical_demand` reproduces recorded counts within the same tolerances.
  - `fidelity` reported with every demand; same inputs + seed → identical hash.
- **Stretch**: OD estimation from partial counts, evaluated against a hidden true OD on DEV-NET.

### 4.5 Scenario Builder (new)

- **Minimal**: for `lane_closure` and `speed_limit` with fixed windows, produces `.add.xml` + `sumocfg` that SUMO accepts.
- **Done** (on the Builder bank, 3 repeated runs):
  - **Strategy selection**: static vs dynamic chosen correctly for 100 % of specs (window → static, condition → dynamic).
  - **Validity**: 100 % of generated scenarios pass `sumo --check-route` / load without errors; all referenced ids exist in the network.
  - **Effect verification** per intervention type, read from edgedata / `applied_actions` after a Runner execution:
    - `lane_closure`: flow on the closed lane = 0 inside the window, > 0 outside; ≥ 90 % of vehicles that would have used it appear on alternative edges.
    - `edge_closure`: same, at edge level.
    - `speed_limit`: mean speed on target ≤ limit + 10 % inside the window.
    - `signal_program`: TLS phases observed match the program inside the window.
    - `demand_scale`: total departed vehicles within ±5 % of scaled target.
    - Dynamic variants: `applied_actions` shows the action fired at the first step where the condition held (±`poll_interval`).
    - Target: ≥ 27/30 specs pass *(threshold)*.
  - **Determinism of authoring**: for the same spec, the generated files are structurally equivalent across 3 runs (same rerouter/edge/time entries; formatting may differ).
  - **No silent coercion**: a spec the Builder cannot implement (e.g. dynamic `demand_scale`) is rejected with a reason, not approximated.
- **Stretch**: LLM-generated Python TraCI scripts for interventions outside the `TraciPlan` language, sandboxed, with the same effect-verification tests; combined interventions (e.g. closure + adaptive signals) with interaction checks.

### 4.6 Simulation Runner (deterministic executor)

- **Minimal**: batch run of a `Scenario`, produces edgedata + tripinfo + summary, stores `SimulationResult`.
- **Done**:
  - Reproducibility: same scenario + seed → byte-identical edgedata, 20/20 runs (batch and online).
  - `TraciPlan` interpreter: every trigger type and every action in §2.4 covered by a unit test; 10/10 plan test cases apply actions at the correct step, verified by reading state back through TraCI; `applied_actions` logged.
  - Unsupported plan entries rejected before starting SUMO.
  - SUMO errors captured with the SUMO message; run marked failed, never silently empty.
  - DEV-NET peak (1 h simulated) < 2 min wall clock in batch, < 5 min online *(threshold)*.
- **Stretch**: live agent selecting TraciMCP calls from the catalogue toward a stated goal, evaluated vs a scripted baseline.

### 4.7 Network Expert (research focus)

- **Minimal**: descriptive questions on DEV-NET from edgedata + NetworkMCP, with evidence.
- **Done** (question bank, 3 repeated runs, mean ± std):
  - Descriptive: exact-answer accuracy ≥ 90 % DEV-NET / ≥ 85 % REAL-NET *(threshold)*.
  - Diagnostic: top-3 bottleneck Jaccard ≥ 0.6 DEV-NET / ≥ 0.5 REAL-NET; "why" rubric ≥ 70 % *(threshold)*.
  - Counterfactual, forced: direction ≥ 75 % / ≥ 65 %; magnitude band ≥ 50 % *(threshold)*.
  - Calibration: Brier ≤ 0.25; accuracy with `basis=observed` significantly above `basis=extrapolated`.
  - Abstention, free mode: recall of `needs_simulation` on forced-mode errors ≥ 70 %, false requests ≤ 30 % *(threshold)*.
  - Evidence: 100 % of answers reference a resolvable artifact or query.
  - Knowledge hygiene: on 20 probes, no `ExpertNote` with `status=unverified` and `basis=extrapolated` is cited as observed fact; confirmed/refuted status is updated after the corresponding simulation in 100 % of cases.
  - **Learning effect** (thesis claim): counterfactual accuracy on held-out interventions increases as the store grows 0 → 5 → 15 → 25 experiments on the same network; plotted with confidence intervals.
- **Stretch**: the Expert proposes the experiment that most reduces its uncertainty; accuracy gain per experiment vs random selection.

### 4.8 Output Composer

- **Minimal**: `ExpertAnswer` + experiments → Markdown.
- **Done**: 100 % of quantitative claims link to evidence (numbers must appear in referenced artifacts, checked automatically); 0 claims not present in the `ExpertAnswer` (rubric, 20 reports); mode, `basis` and limitations stated.
- **Stretch**: interactive report with charts; detail level selectable.

### 4.9 MCP servers

- **Minimal**: every tool has a docstring, typed I/O, one example.
- **Done**:
  - Contract tests: ≥ 3 unit tests per tool including one error case; 100 % pass.
  - DatabaseMCP contract published as a schema; the reference implementation passes a **conformance suite** that any user implementation can run.
  - `find_similar_scenario`: exact match when it exists, otherwise closest by intervention + `context_tags` overlap; 10 test cases.
  - `search_notes` respects `status` / `basis` filters; 5 test cases.
  - Latency: single call < 1 s DEV-NET, < 5 s REAL-NET *(threshold)*.
- **Stretch**: a second backend implementation (e.g. SQLite or file-based, vs. the Postgres/`pgvector` reference) passing the conformance suite, demonstrating pluggability.

---

## 5. Integration Definition of Done

Golden paths (expected traces):

| ID | Request | Expected trace |
|---|---|---|
| GP-1 | Describe congestion at peak (results exist) | Input → Coord → Expert → Output |
| GP-2 | Same, no results | Input → Coord → Builder → Runner → Expert → Output |
| GP-3 | "What if I close lane 1 of E12?" free, no match | … → Expert (`needs_simulation`) → Coord → Builder (static) → Runner → Expert → Output |
| GP-4 | Same, forced | … → Expert (`basis=extrapolated`) → Output; no simulation |
| GP-5 | Same, experiment exists | … → Expert (stored result) → Output; no simulation |
| GP-6 | "Close E12 lane 1 when occupancy > 0.8" | … → Builder (dynamic, `TraciPlan`) → Runner (online) → Expert → Output |
| GP-7 | Compare scenarios A and B on delay | Input → Coord → Expert → Output |
| GP-8 | New place name, nothing exists | Full pipeline incl. Network Generator and Demand Generator |
| GP-9 | Ambiguous request | Input flags ambiguity → Coord stops and asks |
| GP-10 | DatabaseMCP without `historical_demand` | Coord records fallback → Demand Generator parameter-driven → … |

- **Done**:
  - Correct invocation: trace matches expected for 10/10 golden paths on 3 repeated runs *(threshold)*.
  - Reproducibility: GP-2 twice with the same seed → identical `SimulationResult` hashes and identical numbers/conclusions (prose may differ).
  - No silent failures: injected failure at any step surfaces in the final report.
  - Cost/latency budget per golden path recorded; thresholds set after first measurement.
  - Machine-readable trace per run (steps, tool calls, artifacts, tokens) usable for thesis figures.
- **Stretch**: usability study with 2–3 DLR traffic engineers rating reports on usefulness and trust.

---

## 6. Suggested order of work

1. Contracts (§2.2), DatabaseMCP contract + conformance suite, DEV-NET, demand profiles.
2. NetworkMCP, TraciMCP, DatabaseMCP reference implementation to *Done*.
3. Scenario Builder to *Minimal* and Runner to *Minimal* (batch) → scenario matrix for DEV-NET.
4. Network Expert to *Done* on DEV-NET; question bank.
5. Coordinator to *Minimal*; loop GP-3/4/5.
6. Builder to *Done* (incl. dynamic) and Runner online mode; GP-6.
7. Network Generator and Demand Generator to *Minimal*; REAL-NET frozen; scenario matrix on REAL-NET.
8. Network Expert to *Done* on REAL-NET; learning-effect curve.
9. Integration DoD; remaining modules to *Done*; Stretch only afterwards.

---

## 7. Decisions taken in this iteration

- Interventions for v1: `lane_closure`, `edge_closure`, `speed_limit`, `demand_scale`, `signal_program`.
- `forced` is a user flag (user does not want to spend simulation resources).
- Expert knowledge model: facts via tools (edgedata, KPIs, metadata, graph), opinions via RAG (`ExpertNote`s with provenance, basis and verification status), `context_tags` structured in `Scenario`.
- REAL-NET is hand-cleaned once and frozen for the Expert evaluation; the Network Generator is evaluated separately on GEN-LOCATIONS.
- Dynamic interventions are declarative `TraciPlan`s interpreted by the Runner; LLM-generated TraCI scripts are Stretch.
- DatabaseMCP reference implementation: **Postgres + `pgvector`** (via SQLAlchemy Core), not SQLite, to support a network larger than DEV-NET/REAL-NET's initial scale robustly — proper concurrent access, `JSONB` for semi-structured fields (`params`, `context_tags[]`, `applied_actions[]`), and mature indexed vector search (HNSW/IVFFlat) for `search_notes` over `ExpertNote`s as the note store grows (up to 25 experiments per network in the learning-effect run). Large artifacts (`.net.xml`, edgedata, tripinfo) still live on the filesystem, referenced by path/hash — never stored in the DB.
- Scenario Builder authoring: one deterministic **writer per mechanism** (`RerouterWriter`, `VssWriter`, `TlsProgramWriter`, `TazWriter`), not a single monolithic Builder agent and not LLM-driven — §2.4's intervention→mechanism table is a deterministic lookup, not a judgment call. Each writer implements a structural `AdditionalFileWriter` port (`supports(intervention) -> bool`, `write(intervention, network, output_dir) -> Path`) defined in `application/ports/`; concrete writers live in `adapters/scenario_builder/writers/`; a thin `ScenarioBuilderUseCase` in `application/use_cases/` dispatches to the first writer whose `supports()` matches and raises `UnsupportedInterventionError` if none does. This is what makes the DoD §4.5 criterion "a spec the Builder cannot implement is rejected with a reason, not approximated" enforceable by construction rather than by convention.
- SUMO version pinned for the whole thesis: **1.27.1**, recorded in `README.md`; every `SimulationResult.sumo_version` must match it.

## 8. Open questions for the next iteration

- `TraciPlan` expressiveness: is `when(metric, target, op, value)` enough for v1, or do we need compound conditions (`and`/`or`) and reversal actions (`open_lane` when the condition stops holding)?
- How is the "why" of diagnostic questions graded: rubric by you, LLM-as-judge with a rubric, or both with agreement reported?
