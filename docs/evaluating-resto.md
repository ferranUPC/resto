# Evaluating RESTO

- Status: living document, started 2026-09-17
- Scope: how every part of RESTO is measured — assets, run protocols, answer types, scoring rules,
  aggregation, costs — and the decisions behind them.
- Relation to other docs: the **thresholds** stay in [`tfm-architecture-and-dod.md`](tfm-architecture-and-dod.md)
  §4 (per module) and §5 (integration), which remains the source of truth. This document defines *how* each
  metric is computed so that a threshold there has one unambiguous procedure here. Where the two disagree,
  fix this document, or amend the architecture through an ADR.

---

## 1. Principles

1. **Simulation is ground truth.** Gold answers are computed by code from stored simulation results, never
   written by hand or by an LLM.
2. **Agents are evaluated statistically.** Every agent benchmark runs the same inputs 3 times and reports
   mean ± std; a single run proves nothing about an LLM step.
3. **Tests never call a real model.** `pytest` uses the shared `FakeToolAgent` (ADR-0001). Benchmarks against
   a real model are manual runs with an estimated cost confirmed before spending (CLAUDE.md cost policy):
   a *development run* (smoke, tuning, a 1-repetition check) runs now; a *measurement run* (the figure a
   DoD threshold reads) waits for a validation pass (§7).
4. **Raw runs are kept.** A benchmark stores every agent run (output, tool calls, ledger, tokens, cost) so
   metrics can be recomputed or corrected without paying for the runs again.
5. **Structured before judged.** A metric compares typed values whenever possible; free-text grading
   (rubric, LLM-as-judge) is used only where no typed value exists, and its agreement with a human is
   measured before it is trusted.
6. **Budgets are stated in tokens first, dollars second.** Every run-protocol section records measured
   (or, before a sweep has run, best-estimate) input/output tokens per family per run. The dollar figure
   for the current default model is that token count run through `resto.adapters.llm.pricing`'s per-token
   rate — never a number re-derived by hand. Pricing a different model, including a paid escalation (which
   still needs the explicit approval and cost confirmation CLAUDE.md's LLM cost policy requires), is then
   the same token count multiplied by that model's own published rate, not a new analysis.

---

## 2. Evaluation assets

| Asset | Used by | Status | Where |
|---|---|---|---|
| DEV-NET (5×5 grid, 2→1 merge on `B0C0`→`C0D0`, signalised row-2 corridor) | everything on DEV-NET | built (E0.5) | `eval/dev-net/` |
| Demand profiles `low` / `peak` / `incident` + control counts | Demand Generator, matrix | built (E0.6) | `eval/dev-net/demand/` |
| Effect-verification harness | Scenario Builder | built (E2.4) | `verify/` |
| Scenario matrix DEV-NET / peak (20 rows × 3 seeds) | Expert gold answers | built (E3.1) | `eval/scenario_matrix/` |
| Question bank DEV-NET (117 questions) | Network Expert | built (E3.2) | `eval/question_bank/` |
| Expert benchmark harness | Network Expert | built (E3.3) | `eval/expert_benchmark/` |
| Request bank (73 concepts, 346 requests; text → gold `Question`) | Input Parser | built (E3.4) | `eval/request_bank/` |
| Blind annotation of held-out + external request split | Input Parser (gold check) | page built, annotations pending | `eval/request_bank/annotation/` |
| Plan bank (gold phase-0 `StudyPlan` per request, fixed DB state) | Coordinator | pending (E3.7) | — |
| Builder bank (25–30 specs) | Scenario Builder | pending (E2.7) | — |
| Derivation bank (10 modifications) | Network Author | pending (E6.4) | — |
| GEN-LOCATIONS (10 raw OSM locations) | Network Author | pending (E6.4) | — |
| REAL-NET + matrix + question bank | Expert on a real network | pending (E6.3, E3.5, E3.6) | — |
| Golden-path framework (GP-1…GP-11) | Integration | pending (E7.1) | — |

---

## 3. What is evaluated, per module

Detailed procedures exist so far only for the Network Expert (§4). The other rows list the metrics the DoD
already fixes; each procedure is written here when its benchmark task starts, not before.

| Module | Benchmark asset | Metrics (DoD) | Procedure |
|---|---|---|---|
| Input Parser | request bank | schema validity, field match, ambiguity detection, `intent` agreement (§4.1); arm structure ≥ 90 % on multi-arm requests (§5, 2026-09-23) | E5.1 (`eval/parser_benchmark`, [`parser-tuning-log.md`](parser-tuning-log.md)), E5.8 |
| Coordinator | plan bank | routing vs gold plan (§4.2); the `StepRecord` trace is Executor behaviour, checked by fake-agent tests (ADR-0023) | E5.5, E5.8 |
| Network Author | GEN-LOCATIONS, derivation bank | loadable networks, sanity report, replay determinism, agent stability (§4.3) | E6.4 |
| Demand Generator | demand profiles, control counts | calibration fidelity ±15 % DEV / ±25 % REAL, replay determinism (§4.4) | E6.5 |
| Scenario Builder | builder bank | mechanism selection, validity, effect verification ≥ 27/30, authoring determinism (§4.5) | E2.7 |
| Simulation Runner | unit tests | reproducibility 20/20, sandbox, latency (§4.6) | done (E2.1), online mode E2.5 |
| **Network Expert** | **question bank** | **§4.7 — see §4 below** | **E3.3** |
| Output Composer | 20 reports | claim traceability, no claims absent from `ExpertAnswer` (§4.8) | E5.7 |
| Integration | golden paths GP-1…GP-11 | trace match 11/11 on 3 runs, reproducibility, no silent failures (§5) | E7.5 |

---

## 4. Network Expert

How the Expert itself is tuned between measurements — versions, hypotheses, results — is recorded in
[`expert-tuning-log.md`](expert-tuning-log.md).

### 4.1 Question bank (E3.2)

Generated by `python -m eval.question_bank.build` from the DEV-NET / peak scenario matrix; 117 questions,
all `mode = forced`, every gold answer computed programmatically (`eval/question_bank/gold.py`,
`templates.py`).

| Family | Id suffix | Count | Question | Gold answer computed from |
|---|---|---|---|---|
| Descriptive | `-desc-occ` | 20 | Which edges exceed 3.5 % occupancy in the window? | `query_edgedata`, occupancy > 3.5 |
| Descriptive | `-desc-tt` | 20 | Mean travel time on a target edge in the window? | `query_edgedata`, `travel_time` |
| Diagnostic | `-diag` | 20 | Which three edges form the main bottleneck, and why? | top-3 by total `time_loss`; reason by topology group |
| Counterfactual | `-cf-dir` | 19 | Does the total delay on the target edge increase, decrease, or stay within 5 %? | total `time_loss` on the edge, row vs baseline S00 |
| Counterfactual | `-cf-topk` | 19 | Which 5 edges change most in total delay? | top-5 by \|Δ total `time_loss`\|, row vs S00 |
| Counterfactual | `-cf-band` | 19 | By roughly how much does network-wide mean delay change? | `kpis.mean_delay`, row vs S00, banded |

Generation rules:

- **Seeds.** Every gold value is the mean over the row's 3 seeds; per-seed values are kept in `evidence`.
- **Delay.** SUMO's `time_loss` is the total time lost by all vehicles on the edge (vehicle-seconds), so
  it already is "per-vehicle delay × flow"; bottlenecks rank by it directly (ADR-0020).
- **Window.** The row's own intervention window; `[0, 300)` for rows without one (baseline, `demand_scale`).
  Counterfactuals query the baseline with the *row's* window, never the baseline's default.
- **Target edge.** The row's intervention edge; the edge downstream of the junction for `signal_program`
  rows (`A2`→`A2B2`, …); `B2C2` for `demand_scale` rows.
- **Occupancy threshold 3.5 %.** Chosen from the matrix itself: baseline occupancy tops out near 3 % in
  `[0, 300)`, a lane closure's upstream queue near 6 %.
- **Bottleneck reason.** `merge` if the top edge is `B0C0`/`C0D0`, `signal` if it is on the row-2 corridor,
  `demand` otherwise. Computed but **not graded** (§4.4).
- **Question text** names the scenario by its description only; matrix row labels (`S00`, …) never appear
  (the Expert cannot resolve them).

Corrections:

- 2026-09-17 (before any benchmark sweep): diagnostic gold ranked by `time_loss × entered`, counting flow
  twice, and `query_edgedata` averaged `time_loss`/`waiting_time` across intervals instead of summing
  them. Both fixed (ADR-0020); 15 of 20 diagnostic gold answers changed, no other family did.

Known limitations:

- On `lane_closure` / `edge_closure` rows (S01–S08), `-cf-dir` asks about the closed edge itself, which
  empties: the gold direction is systematically `decrease` (−100 %). Correct, but weak as a question; the
  same rows' `-cf-topk` carries the informative effect.
- Every question has its results available, so almost every correct answer is `basis = observed`; the bank
  cannot yet compare `observed` with `extrapolated` answers (§4.5).
- *Found by the v0 sweep (`expert-tuning-log.md`), pending a decision:*
  - `-desc-occ` does not say how to combine seeds; the gold uses the 3-seed mean, and the 3.5 % threshold
    sits next to per-seed values (B2C2: 2.96 / 2.79 / 3.55). 8 of 8 wrong answers came from this.
  - `-desc-tt` on S01–S04 asks for the travel time of an edge no vehicle crossed in the window (gold 0.0 by
    zero-fill); the Expert spent all its steps looking for data that does not exist.

### 4.2 Run protocol

Implemented in `eval/expert_benchmark/` (`bank.py`, `runner.py`). For each question and each repetition:

1. Build an `ExpertTask`: the question text, `mode = forced`, DEV-NET's `network_id`,
   `notes_allowed = false`, and `result_ids` =
   - descriptive and diagnostic: the row's 3 results;
   - counterfactual: the row's 3 results + baseline S00's 3 results.
2. Run `run_expert` with the `OpenRouterToolAgent` on `RESTO_LLM_DEFAULT_MODEL`
   (`deepseek/deepseek-v4.1-flash`) and the default budget (`RESTO_LLM_MAX_STEPS` = 6,
   `RESTO_LLM_MAX_OUTPUT_TOKENS` = 2048, 300 s), over `eval/scenario_matrix/matrix.db` and
   `dev-net.net.xml`, read-only.
3. Promote with `ask_expert` using the same `EvidenceLedger`; record acceptance or the rejection reason.
4. Store the raw run as one JSON line: `EXPERT_VERSION`, answer, tool calls (with result summaries), the
   per-step trace (tools requested, text length, finish reason, tokens), full ledger, stop reason,
   promotion outcome, tokens, estimated cost, elapsed time.

```bash
python -m eval.expert_benchmark.run --name <name> [--questions <ids>...] --repetitions 3 \
    --workers 4 --max-cost-usd <cap>
python -m eval.expert_benchmark.run --name <name> --report-only   # re-score stored runs
```

- Raw runs: `eval/expert_benchmark/runs/<name>.jsonl` (gitignored). Reports:
  `eval/expert_benchmark/reports/<name>.md` and `.json` (committed).
- **Resumable**: a (question, repetition) already stored is skipped, so an interrupted sweep never pays
  twice. **Crashes** (API errors) are not stored and are retried on the next invocation.
- **Cost cap**: `--max-cost-usd` stops starting new runs once the estimated spend reaches it.
- **Workers** run questions in parallel, each with its own SQLite connection and network query.

Repetitions: **3** per question. Free mode is **not run for now**, so the abstention metrics (§4.5) are
deferred — the forced 3-repetition sweep and the forced+free paired sweep are measurement runs, one suite
(EXP-01) in Validation 2 (§7).

**Budget (principle 6): tokens per family, dollars for the current default model derived from them.**
Measured on `v1-forced-1rep` (`eval/expert_benchmark/reports/v1-forced-1rep.json`), one repetition over
the whole 117-question bank, `deepseek/deepseek-v4.1-flash`. Supersedes the 4–5 USD estimate this section
used to give, which was extrapolated from only the 5 questions of the 2026-09-17 smoke run (§4.7) before a
full-bank sweep existed.

| Family | Runs | Input tok / run | Output tok / run | DeepSeek v4.1 cost / run |
|---|---|---|---|---|
| `-desc-tt` | 20 | 27,802 | 1,536 | $0.0051 |
| `-desc-occ` | 20 | 31,035 | 1,812 | $0.0057 |
| `-cf-band` | 19 | 44,844 | 2,109 | $0.0080 |
| `-cf-topk` | 19 | 50,435 | 2,481 | $0.0091 |
| `-cf-dir` | 19 | 52,340 | 2,551 | $0.0094 |
| `-diag` | 20 | 64,874 | 5,248 | $0.0129 |
| **Total, 117 × 1 rep** | 117 | 5,278,975 | 307,598 | **$0.976** |

The dollar column is `tokens × resto.adapters.llm.pricing.estimate_cost_usd`'s current DeepSeek v4.1 rate
($0.15 / $0.60 per 1M input / output tokens). For the DoD's 3 repetitions: ≈ 15.8 M input + 0.92 M output
tokens ≈ **$2.9** — and the same two token columns, multiplied by any other model's published per-token
rate, price a run on that model without re-measuring anything. Adding free mode would roughly double it.

`-diag` costs the most per run (more than double `-desc-tt`) and is the only family with text-only and
token-limit-cut steps (3 of 20 runs each, 2026-09-17 sweep) — see `docs/expert-tuning-log.md` v1/v2 for
why. A tool-set change that removes some of that exploration (v2, in progress) is expected to lower
`-diag`'s token count specifically; not yet measured on a full sweep (deferred, see the tuning log).

### 4.3 Answer types (ADR-0019)

`ExpertAnswer` carries `values: tuple[AnswerValue, ...]` next to the prose `answer`. `values` is required
unless the Expert abstains, and it is what gets scored; `answer` is the justification.

| Kind | Fields | Answers questions like |
|---|---|---|
| `Edges` | `edge_ids`, `ranked` | which edges exceed X (set); top-3 bottleneck, top-5 changes (ranked) |
| `Quantity` | `measure`, `value`, `edge_id` | mean travel time on E; network mean delay |
| `Change` | `measure`, `direction` (increase / decrease / unchanged), `relative_change_pct?`, `edge_id` | does delay on E increase; how much does mean delay change |

- `Measure` is a closed enum with a fixed unit per measure. Per edge (`edge_id` required): `travel_time`
  (s), `occupancy` (%), `speed` (m/s), `density` (veh/km), `entered`, `left` (veh), and `time_loss`,
  `waiting_time` (veh·s — totals over all vehicles on the edge, ADR-0020). Network-wide (`edge_id` must
  be None): `mean_delay`, `mean_travel_time` (s), `teleports`, `departed`, `arrived` (veh).
- `Change.relative_change_pct` cannot contradict `direction` (an increase with a negative percentage is
  invalid); `unchanged` accepts either sign.
- Promotion rejects a value naming an edge that is not on the network.
- More kinds (`Route`, `ScenarioRef`, `YesNo`, …) are added when a benchmark question needs them; adding a
  kind does not invalidate stored answers.
- The prompt's examples use ids that exist neither on DEV-NET nor in any gold answer (a unit test guards
  it), so the prompt never leaks the bank.

### 4.4 Scoring per family

Implemented in `eval/expert_benchmark/scoring.py`. A question scores **incorrect** when the run stops
without an answer, promotion rejects the answer, or the expected value is missing. Values beyond the
expected one (e.g. supporting quantities) are ignored.

| Family | Value scored | Correct when | Reported | DoD threshold (DEV-NET) |
|---|---|---|---|---|
| `-desc-occ` | first `Edges` | set equals gold exactly | accuracy | descriptive ≥ 90 % |
| `-desc-tt` | `Quantity(travel_time)` on the gold edge | \|pred − gold\| ≤ 5 % of \|gold\| (gold = 0: pred = 0) | accuracy | descriptive ≥ 90 % |
| `-diag` | first `Edges` | Jaccard(predicted set, gold top-3) ≥ **0.6** | mean Jaccard + accuracy | Jaccard ≥ 0.6 |
| `-diag` "why" | — | not graded (open question, architecture §8) | — | rubric ≥ 70 % (deferred) |
| `-cf-dir` | `Change(time_loss)` on the gold edge | direction equals gold (`unchanged` ↔ within 5 %) | accuracy | direction ≥ 75 % |
| `-cf-topk` | first `Edges` | Jaccard(predicted set, gold top-5) ≥ **0.6** | mean Jaccard + accuracy | none |
| `-cf-band` | network-wide `Change(mean_delay)` | has a percentage and `magnitude_band(pct)` equals gold | accuracy | band ≥ 50 % |

- Descriptive accuracy is reported over both descriptive families together, as the DoD states one threshold.
- The predicted edge set is scored as given, never truncated to 3 or 5: extra edges lower the Jaccard.
- Mean Jaccard counts a missing or rejected answer as 0.

### 4.5 Cross-cutting metrics

- **Evidence resolvability** (DoD: 100 %). Enforced by `ask_expert` (ADR-0018): every `query` ref must be a
  call in the run's ledger, every `artifact` ref an artifact a result call returned. Reported as
  `accepted_share`, the share of runs accepted by promotion; a run without an answer counts as not accepted.
- **Calibration** (DoD: Brier ≤ 0.25). Over every run that produced an answer (including answers rejected
  at promotion, which score incorrect): `(confidence − correct)²` with `correct ∈ {0, 1}` from §4.4; Brier
  is the mean. Accuracy is also reported grouped by `basis`.
- **`observed` vs `extrapolated`** (DoD: observed significantly above). *Proposed, not budgeted:* with every
  result available the bank produces almost no extrapolated answers, so an extra forced sweep would run a
  subset of questions with `result_ids = ()`. Significance test to be chosen (e.g. one-sided Fisher exact).
- **Numbers traceable to tool calls** (DoD: checked on the whole bank). *Proposed, not implemented:* check
  each evidence `excerpt`'s numbers against the ledger result of the ref it cites, within rounding; not the
  prose, where derived numbers (means, percentages) legitimately appear in no tool result. The stored
  ledger already holds what this check needs.
- **Abstention** (DoD: recall ≥ 70 %, false requests ≤ 30 %). Each question runs in forced and free mode;
  a question *should* abstain when the forced answer is incorrect. Recall = abstained in free ∧ incorrect
  in forced / incorrect in forced. False requests = abstained in free ∧ correct in forced / abstained in
  free. Computed in `eval/expert_benchmark/report.py` (E4.5); the harness supports running each question
  in both modes (`--mode both`). **Deferred**: the full-bank sweep is a measurement run (EXP-01, §7).

### 4.6 Aggregation and report

Implemented in `eval/expert_benchmark/report.py`.

- Every metric is computed per repetition, then reported as mean ± std over the repetitions (std needs at
  least 2), next to its DoD threshold.
- The report also lists: the Expert version(s), accuracy by `basis`, budget stops, and per family the
  steps, text-only steps, steps cut at the token limit, tokens and estimated cost; plus a per-question
  table (correct per repetition, with predicted vs gold).
- `reports/<name>.json` holds the same summary as data (per-repetition metrics included).

### 4.7 Smoke runs, 2026-09-17

Same 5 questions, 1 repetition, forced mode, `deepseek/deepseek-v4.1-flash`, default budget.

| Question | Prose answers, graded by hand | Typed values, harness (`smoke-typed-2026-09-17`) |
|---|---|---|
| `S00-desc-tt` | correct (23.4 s) | ✅ 23.40 s |
| `S03-desc-occ` | correct (`B1B0`) | ✅ `[B1B0]` |
| `S00-diag` | incorrect (Jaccard 0.5) | ❌ budget stop, no answer (twice) |
| `S09-cf-dir` | correct (increase, +114 %) | ✅ increase |
| `S17-cf-band` | correct (+7.6 %, 5–20 %) | ✅ +7.6 %, 5–20 % |
| Total cost | 0.059 USD | 0.052 USD (+ 0.022 USD diagnostic retry) |

Observations:

- The Expert averaged the 3 seeds on its own and used `get_scenario` to tell baseline from intervention.
- With typed values it filled the right kind every time it answered, and added supporting quantities
  (e.g. baseline and intervention `time_loss`) that scoring ignores.
- The untyped diagnostic answer (`A2B2, B2C2, C2D2`) scores Jaccard 0.5 against both the original and
  the corrected gold.
- The prose once stated a direction ("west-bound") no tool returned, and one evidence excerpt labelled an
  intervention value as baseline. Promotion cannot see either — hence scoring the typed values and the
  proposed excerpt check in §4.5.
- The first run tried to resolve the matrix label in the question text (`get_scenario("S00")`); labels were
  removed from the bank.
- **Diagnostic budget stops.** With typed values, `S00-diag` stopped on the step budget twice. The trace of
  the retry shows 3 steps of tool calls (the first wasted on `get_scenario` with result ids), no failed or
  truncated submission, and ~7,000 output tokens: consistent with three plain-text replies cut at the
  2,048-token output limit while reasoning over 3 × 80 edges. Plain-text replies are not in the trace, so
  this is inferred, not observed. Failed `submit_output` validations and unparseable tool calls are now
  recorded in the trace.

### 4.8 Knowledge hygiene (E4.6)

DoD (v0.2 §4.7): on 20 probes, no `ExpertNote` with `status = unverified` and `basis = extrapolated` is
cited as observed fact; the status is updated after the corresponding simulation in 100 % of cases. The
two halves are measured differently:

- **Status updates — deterministic, no model call.** `update_note_status` (ADR-0024) confirms or refutes a
  note from a later `SimulationResult`. "100 % of cases" means 100 % of *applicable* cases: notes with a
  network-wide `Quantity` claim. Covered by `tests/unit/application/use_cases/test_update_note_status.py`.
- **Citation probes — real model, `eval/hygiene_probes/`.** 20 questions from the bank, spread round-robin
  across families. Each runs in forced mode with `notes_allowed = true`, `result_ids = ()` (no simulated
  data), and one seeded note: `opinion`, `extrapolated`, `unverified`, worded to echo the question so the
  hashing embedder retrieves it. A probe is a **violation** when the answer has `basis = observed` and cites
  a `search_notes` call as evidence. Pass = 0 violations (a hard rule, not a percentage threshold).
  Correctness of the answer is not graded.
- Cost: ~$0.01 per probe, so 20 probes × 1 repetition ≈ $0.20. Run under the earlier "> $1 waits" rule,
  before the development/measurement split (§5, 2026-09-24); E4.6's Done stands on it and is not
  re-measured.

    python -m eval.hygiene_probes.run --name hygiene-v1 --repetitions 1 --max-cost-usd 0.5

**Run `hygiene-v1`, 2026-09-22** (`deepseek/deepseek-v4.1-flash`, 20 probes × 1, $0.112): **0 violations,
pass** (`eval/hygiene_probes/reports/hygiene-v1.md`). 18 of 20 answered, all `extrapolated`, confidence
0.05–0.30; 14 of them cited the seeded note, always as `extrapolated`. The 2 without an answer count as
passes, not as evidence of hygiene: `S01-diag` hit the step budget (same pattern as the diagnostic budget
stops in §4.7), and `S03-cf-dir` returned `needs_simulation` in forced mode, which `ask_expert` rejected.
That second one is a forced-mode compliance slip, not a hygiene failure; it belongs with E4.5/E4.7.

Limitation: a probe only catches citations of the note through `search_notes`. An answer that restates
the note's content as observed without citing it is not detected; the typed `values` plus the empty
`result_ids` make that unlikely (no query tool can back an observed value), but it is not checked.

---

## 5. Decisions log

| Date | Decision |
|---|---|
| 2026-09-17 | Diagnostic "why" is computed in the gold answer but not graded until E3.3 decides how. |
| 2026-09-17 | Question text never contains matrix row labels. |
| 2026-09-17 | `result_ids` is an allow-list; evidence refs come from a per-run call ledger (ADR-0018). |
| 2026-09-17 | Numeric answers are correct within ±5 % relative tolerance. |
| 2026-09-17 | Set answers scored by Jaccard count as correct at ≥ 0.6. |
| 2026-09-17 | Full forced benchmark (117 × 3) is within budget; free mode and abstention metrics deferred. |
| 2026-09-17 | `ExpertAnswer` carries typed values, starting with `Edges`, `Quantity`, `Change` (ADR-0019). |
| 2026-09-17 | Benchmark runs are stored raw and resumable, with a cost cap; scoring is recomputed from them. |
| 2026-09-17 | `time_loss` and `waiting_time` are vehicle-second totals; diagnostic gold ranks by total `time_loss` (ADR-0020). |
| 2026-09-17 | Every benchmark run records `EXPERT_VERSION`; agent changes are logged in `expert-tuning-log.md`. |
| 2026-09-17 | Diagnostic budget stops are left as they are until E4.3 tunes the Expert; no budget or prompt change before then, and they score as failures in any sweep run earlier. |
| 2026-09-22 | CLAUDE.md cost policy: any single experiment/benchmark run estimated above $1 waits for the end-of-project evaluation pass instead of running ad hoc (§7). This supersedes the 2026-09-17 call above that the forced 117 × 3 sweep was "within budget" — it is relisted as pending in §7 under the same rule. |
| 2026-09-22 | `ExpertNote` carries typed `values`; code confirms/refutes only network-wide `Quantity` claims against `Kpis` for now, others stay `unverified` (ADR-0024). |
| 2026-09-22 | Knowledge-hygiene probes (§4.8): a violation is an `observed` answer citing a `search_notes` call; any violation fails the run. |
| 2026-09-23 | Input Parser scoring (E3.4/E5.1) compares the effective form (`effective_arms`/`effective_contrasts`), so the flat shorthand and a single arm score the same; using the shorthand for one treatment is reported, not graded. |
| 2026-09-23 | Arms are matched by content, never by label: the key of an arm is its set of `topology_changes` plus its set of `interventions`. An intervention is compared on `type`, `target`, `window`/`condition` and `params` (numbers within 1 % relative); `description`/`expected_effect` are ignored (`custom`: type, target and window only). `AddEdge.edge_id` is renamed to a positional placeholder in both the change and the interventions targeting it, so only consistency is checked. |
| 2026-09-23 | §4.1's field-level match on `interventions` and `topology_changes` is computed on the union of distinct items across all effective arms, exact per request — it measures whether the pieces were extracted, not how they were grouped. |
| 2026-09-23 | New **arm-structure** metric, **gating E5.1 Done at ≥ 90 %** (an extension of §4.1, whose frozen thresholds do not cover ADR-0027): on the non-ambiguous multi-arm requests, a request is correct when both the set of arm keys and the set of contrasts (as unordered pairs of arm keys; `base` always the reference) match gold. Reason: §4.1 alone passes a Parser that merges alternatives into one combined arm, which then plans the wrong simulations. `required_arms` match is reported as a diagnostic. |
| 2026-09-23 | Request bank = concepts × variants. A concept is a hand-written English base request with one gold `Question`; its variants (translations ca/es/de/zh, registers, typos, stripped accents) share that gold. Variants are free in form (e.g. "8 in the morning" for 08:00): what must survive is the information, not the tokens. A *vaguised* variant deliberately loses one field ("early in the morning"); its gold is derived by code (field unknown, `ambiguities[]` non-empty). |
| 2026-09-23 | Vague is ambiguous by default: the Parser must not guess a window, value or edge. Times are written as clock times and never checked against a demand (ADR-0028: "08:00–09:00" → `[28800, 32400)`); "peak hour" is not a time but `demand_ref = "peak"` (this replaces an earlier same-day convention mapping it to the DEV-NET `peak` window). The bank does not depend on DEV-NET. Unintelligible and out-of-scope requests have a gold `Question` with non-empty `ambiguities[]` (the `Study` goes to `awaiting_user`); their `intent` is not scored. |
| 2026-09-23 | The Parser answers in English whatever the input language: enums and canonical `metrics_of_interest` (Runner KPI names, ADR-0017) are scored exactly; ids and proper nouns verbatim; `text` is the user's original; the language of `ambiguities`/`description` is reported, not graded. |
| 2026-09-23 | Bank-building models (approved by the user, from families not under evaluation, reasoning disabled): generator `qwen/qwen3.5-9b` (variants, back-translations), verifier `meta-llama/llama-3.3-70b-instruct` (per-field check that a variant keeps the gold). Typos and accents are made by code with a fixed seed. Verifier failures plus a ~15 % random sample of passes are reviewed by hand; the bank is then frozen with its provenance and never regenerated during evaluation. Pilot: 5 concepts first; if Qwen's variants are poor, switch the generator to DeepSeek and record it as a limitation. Estimated cost of building the whole bank < $0.20. |
| 2026-09-23 | Variant pilot (5 concepts, 23 LLM variants, $0.0046 for two passes). Prompt v1: the verifier let through a variant identical to the original and one written as the assistant, and rejected a correct vaguised Spanish variant for "being translated". Prompt v2 (generator writes as the user; verifier sees the back-translation, checks it is a user request, and a variant identical to the original fails by code): 2 failures, both genuine (Catalan "vèrtexs" for edges; a grouping-vague variant written as statements). Qwen 3.5 9B is good in es/de/zh and English registers, weak in Catalan and at blurring the grouping; failed variants are fixed by hand. |
| 2026-09-23 | 70/30 dev/held-out split by concept (never by variant). E5.1's prompt is tuned on dev only; Done is measured once, on held-out, with the default Parser model. |
| 2026-09-23 | Parser comparison runs, approved by the user: `mistralai/ministral-3b-2512` (poor) and optionally `google/gemma-3-12b-it` (middle) against `deepseek/deepseek-v4.1-flash`, each named explicitly per run; ≈ $0.2–0.4 per full run (~250 requests × 3). Tool calling is required (`submit_output`), which rules out `gemma-3-4b` and `llama-3.2-3b`. |
| 2026-09-23 | Request bank drafted: 65 concepts (16 single, 14 multi-arm, 6 combined, 15 ambiguous, 5 unintelligible, 5 out of scope, 4 adversarial) and 241 variant specs, ≈ 300 requests; the hardest (R065) names 4 measures and 3 network changes and asks for 7 of the 64 factorial arms with 5 hand-picked contrasts; every category and every language, register and noise value has ≥ 15 variants. Wording conventions (in `concepts.py`): a change with a time is an intervention, "for good" / "removed" / "widened" a topology change, a closure with neither is ambiguous; several changes are one treatment only when the text says so, alternatives say their reference, a bare "and" is ambiguous; an adversarial request's gold ignores the injected part. The two pilot variants the verifier rejected were fixed by hand. Pending: user review of the concepts, then generation (dry-run estimate $0.05 for 217 variants). |
| 2026-09-23 | The dev/held-out split is stratified by category (within each, the ~30 % of concepts with the lowest crc32 of their id are held out), replacing the per-concept `crc32 % 10` rule, which gave 77/23 and no held-out combined request. Result: 45 / 20 concepts, every category on both sides. |
| 2026-09-23 | Scoring implemented (`eval/request_bank/scoring.py`). One refinement of the rules above: the `AddEdge.edge_id` placeholder is named after the edge's junctions rather than its position, so the order of changes does not matter, and an id no intervention targets is dropped. Windows are compared exactly (the 1 % tolerance is for `params` and condition values). Also reported: consistency across a concept's variants (same intent, ambiguity flag, metrics and arm structure, right or wrong), spurious ambiguities, `required_arms`, `network_ref` / `demand_ref` / `time_window`, and every metric broken down by category, split, language, register, vagueness and noise. |
| 2026-09-23 | Bank generated: 217 new variants for $0.0246 (bank total $0.0273), 306 requests (65 concepts + 241 variants). The verifier rejected 31; 15 were false positives (vague or contradictory variants doing their job, the injected JSON of R062) and were accepted by hand. **Every variant was then read by hand, not just a 15 % sample**, because the sample showed the verifier passing real errors: 42 passed variants were fixed, 58 in all (24 %). Recurring faults: vague-grouping variants that still settle the grouping (5 of 8), added cues that change it ("strictly between these two", "apply all simultaneously", "同时"), mistranslated terms (Catalan "vora" = shoulder, "传送门" for teleports), "demanda máxima" losing the `peak` profile, one Spanish variant left in English, and verbose variants leaking the generator's "test set" framing. Every fix is noted per variant in `variants.json`. Limitation for the thesis: an LLM verifier from a cheap family is not a reliable check of arm/grouping semantics; the bank's quality rests on the full human review. |
| 2026-09-23 | Input Parser benchmark (`eval/parser_benchmark`): raw runs per (request, repetition), resumable, cost-capped; `--model` must be one of the approved models; held-out needs `--final`. Every record is scored on its own; `intent_agreement` needs ≥ 2 repetitions. The Parser gets its own caps: 2 model calls (one retry, §4.1) and 4096 output tokens, because a seven-arm `Question` (R065) exceeds the shared 2048 (CLAUDE.md: raised for the one call that needs it). Tuned on dev to v4, which meets every E5.1 threshold there ($0.227 per dev pass; see `parser-tuning-log.md`). Held-out not run yet. |
| 2026-09-24 | **Held-out run postponed until its gold is checked by a person.** Review of the method before the E5.1 held-out pass found that the bank's concepts, gold `Question`s and wording conventions (`concepts.py`), and the Parser prompt tuned against them, share one author (an assistant session), and the prompt teaches those conventions almost literally ("together", "in the same run", "each against …", a bare list of changes is ambiguous) — the same cues the held-out concepts use (R032, R033, R027, R042, R043). A held-out pass would then measure whether the Parser follows the author's conventions, not whether it reads users. The split itself is sound (by concept, stratified, fixed in `398129d` before any Parser run; no held-out request appears in any run file), but no person other than the author has checked the gold, the full variant review of 2026-09-23 was done inside the same session, and the held-out texts were read during it. Two checks come first: (1) **blind annotation** of the 20 held-out concepts by the user and, ideally, one person outside the project, on a page that shows only the request texts in a fixed shuffled order and a neutral guide (schema meanings only, none of the bank's conventions) — each annotation is a `Question`, scored against gold with the Parser's own `score_request` (`eval/request_bank/annotation/`); where people disagree with gold, the convention is settled (or the item's gold changed and logged) **before** the Parser's held-out pass, never after; (2) an **external split**: requests written on the same page by people who never saw the bank, each with its author's annotation as gold, reported apart from held-out as the test of generalisation. |
| 2026-09-24 | Parser reports carry a 95 % interval per graded metric that resamples whole concepts (a concept's variants and repetitions are not independent), with the rule-of-three bound when every concept is right; Met stays on the point estimate. On held-out, arm structure rests on 4 concepts (R003, R022, R023, R027), and the report says so. The held-out guard now checks the selected requests, so `--requests`/`--concepts` can no longer reach held-out without `--final`. |
| 2026-09-24 | Limitation for the thesis: the bank's author also wrote the Parser prompt; human agreement with gold (above) is reported next to the Parser's scores so the reader can judge how much of the score is convention-following. |
| 2026-09-24 | **First blind annotation** (the user, 20/20 held-out concepts, `eval/request_bank/annotation/agreement.md`): agreement with gold is high on extraction (network/demand 100 %, interventions 92 %, topology and metrics 83 %) and low on the convention-laden axes — intent 71 % (10/14), arm structure 25 % (1/4), 0/2 on bare lists of changes (R042, R043) — below E5.1's own thresholds where the Parser scores ≈ 100 % on dev. Adjudicated with the user: **gold kept on every point.** (C1) intent: settled in the next row, which replaces the form-based rule first proposed here. (C2) a bare list of changes stays ambiguous: asking costs one round with the user, guessing wrong costs simulations and a misleading answer; the annotator agrees R042/R043 were their misreading. (C3) a vague time ("in the morning") stays ambiguous. (C4) an unnamed demand is not an ambiguity for the Parser: it cannot know how many demands a network has, and the Coordinator can ask. The other misses were slips (R007 `arrived` for `entered`, R022 junction C2 for C1) or the page's fault. The guide teaches the intent definitions (next row); the grouping and vagueness conventions are still not taught, so the next annotator's reading of them stays independent. Page fixes: time of day only for `describe`/`diagnose`, a hint for comparisons against a combination other than `base`, a clearer message when an account cannot send. Pending: rewording R022/R023 (hard to read even for the user), then an annotator outside the project. |
| 2026-09-24 | **`intent` is decided by what the user wants to know, never by the verb** (replaces the form-based rule of the Parser prompt v1–v4 and of the previous row's first draft; the user's call). `describe`/`diagnose`: nothing changed. `run`: the figures of a setup the user gives, with nothing to compare them against. `counterfactual`: the effect of one or more changes, against today or against another setup the user names — "try X and see", "with and without X", "what would X add on top of Y". `compare`: a choice between alternatives, "which is better", with or without the word "compare" (the user's example: one works budget, a lane on one edge or on another). Gold changed on three concepts, each read as an effect with nothing to choose: R016 ("compare … with and without"), R023 (the closure's effect on the network with NEW1, now consistent with R022) and R035 ("compare the current network with a version in which …"), all `compare` → `counterfactual`; the ten `run` concepts stay `run` (each asks for the figures of a setup). Re-scored, the user's intent agreement rises from 71 % to 86 % (12/14); the two left are R032 and R043, "simulate X … report the mean delay", which the gold keeps as `run`. The Parser prompt (v4) still teaches the old rule, so a v5 tuned on dev is needed before any held-out pass. Whether to simulate is not the Parser's call (settled with the user): the Expert decides whether it can answer or needs the experiment (`needs_simulation`, ADR-0025 §2), and a user who wants no new simulation says so, which is `forced` mode; `Question` gets no new field. Parser v5 (definitions above) meets every E5.1 threshold on dev ($0.241, `parser-tuning-log.md`). Open: "change X and report Y" with no word about the effect (R004, R032, R040, R041, R043) is gold `run`, but both the user and v5 read it as `counterfactual`. R022/R023 reworded (gold unchanged) and their variants regenerated and reviewed. |
| 2026-09-24 | **Intent is the user's intention, never what it takes to answer** (the user's call, settling the open point above): whether anything is simulated, like whether a network is imported from OSM, is decided behind the Parser, so it cannot define an intent. "Run/simulate X and report Y" is therefore `counterfactual` — the user wants to know what X does. `run` stays for an action wanted as an end in itself, with no question about its effect ("add an edge from J7 to J9", GP-11). Gold of the ten `run` concepts (R004, R015, R017, R019, R032, R034, R040, R041, R043, R063) changed to `counterfactual`; the bank has no `run` concept left, so `run` is not measured by E5.1 — adding a few needs new concepts, which would move the stratified split and is left for a decision. Parser v6 meets every E5.1 threshold on dev (intent 99.4 %, $0.244). The user's annotation now agrees on intent 13/14; the one left is R017, which they labelled `run`. |
| 2026-09-24 | **`run` measured again, split frozen.** Six `run` concepts added (R066–R071, category single, 24 variants for $0.0028; 9 variants fixed by hand and one verifier false positive accepted, as noted in `variants.json`). To add them without moving any existing concept, the split is frozen: R001–R065 keep the held-out set the crc32 rule gave them (a test pins it) and new concepts are placed by hand, here R068 and R069 in held-out, worded unlike the prompt's and the guide's `run` examples, which the dev ones (R066, R067) follow. Bank: 71 concepts, 336 requests, 232 dev and 104 held-out (31 %). Parser v6 reads all 20 new dev requests correctly (`run`, and ambiguous on the three vague variants; $0.020); dev totals unchanged in substance (intent 99.4 %). Known gap, not fixed: no `diagnose` concept is held out (R008 and R009 both fell in dev), so held-out does not measure `diagnose`; a test states it. |
| 2026-09-24 | `diagnose` held out: R072 ("What explains the low speeds on edge C2D2 between 17:00 and 18:00?") and R073 ("where do the teleports come from?"), placed in held-out by hand and worded without the prompt's diagnose cues ("why", "what is causing"); 8 variants for $0.0011, 4 fixed by hand (peak lost as "demanda màxima/máxima", "传送点" for teleports, and a German verbose variant the verifier rightly failed: written as the assistant, asking something else). Every intent is now in both splits (a test pins it). Bank: 73 concepts, 346 requests, 232 dev and 114 held-out (33 %). The annotation page carries all 24 held-out concepts. |
| 2026-09-24 | **Second blind annotation round** (the user, 24/24, after guide v4; revised several earlier answers): extraction is now near-perfect — interventions, topology and time window 100 %, network 100 %, demand 94 %, arm structure 3/4 (up from 1/4), R042's ambiguity caught — but intent falls to 72 % (13/18), and the misses sit on exactly the boundaries settled today: "simulate X and report Y" labelled `run` (R017, R032, R043, gold `counterfactual` under the rule the user set), R022 ("how much would X reduce… and how much more would Y change") labelled `compare`, R027 ("is it then better to … or …?") labelled `counterfactual`. Even the person who wrote the rule does not apply it the same way twice, so a single gold intent on those boundaries is not a fair target for the Parser either. Other misses: metrics left out on R003, R023 and R032 and added on R068 (which asks for none); R043's "reduced to one lane" entered as two lanes. Pending the user's decision: accept both `run` and `counterfactual` on "simulate X and report Y" requests and report intent strict and lenient. |
| 2026-09-24 | **Intent graded with accepted second readings** (the user's call). `concepts.ALSO_ACCEPTED` lists, per concept, intents accepted besides the gold one: `run` on the ten "simulate X and report Y" concepts (R004, R015, R017, R019, R032, R034, R040, R041, R043, R063), gold still `counterfactual`. `score_request` takes them; graded `intent` (the E5.1 threshold) accepts either reading, `intent_strict` is reported against the gold alone, in the Parser and the annotation reports. The compare/counterfactual boundary stays strict: "which is better" against "how much does it change" has one reading by the definition. Re-scored for free: Parser v6 on dev 99.4 % both ways (it always reads these as `counterfactual`); the user's second round 89 % (16/18) graded, 72 % strict; the two left are R022 and R027, compare and counterfactual swapped. |
| 2026-09-24 | **E5.1 held-out pass run** (the user's call, with the external annotation still pending; v6, 114 × 3, $0.376, `eval/parser_benchmark/reports/v6-heldout.md`): every per-run threshold met, **`intent` agreement 93.9 % < 95 %, so E5.1 is not Done**; 94.1 % when only requests with a gold intent are counted, reported but not adopted since it was computed after the result. The held-out split is now spent for tuning: any change made after this pass is chosen on dev, and a second held-out measurement must say it is a second use. Details and the suspect (no temperature set) in `parser-tuning-log.md` §2b. |
| 2026-09-24 | **Development runs vs measurement runs** (the user's call, [wayfinder #3](https://github.com/ferranUPC/resto/issues/3); supersedes the 2026-09-22 row). The line is purpose, not price: development runs go now, measurement runs wait for Validation 1 (mid-December, reduced checkpoints on dev) or Validation 2 (before E8.5, definitive, each suite once). $30 cap for both passes unless funded; under it suites shrink, they are not dropped. A task whose only missing piece is a measurement suite is ⏳ in the tracker, not 🚧. E5.1's second held-out use happens in Validation 2, with the prompt frozen, and is reported next to the first (93.9 %). |

## 6. Open questions

- How to grade the diagnostic "why": human rubric, LLM-as-judge, or both with agreement reported.
- Budget and test choice for the `observed` vs `extrapolated` comparison.
- Whether to implement the excerpt-vs-ledger number check before the first full sweep.

## 7. Measurement runs and validation passes

Per CLAUDE.md's cost policy, runs are split by purpose. A **development run** (smoke, tuning, a
1-repetition check) runs now with its cost stated and is not logged here. A **measurement run**
produces the figure a DoD threshold reads; it waits for one of two passes dated in the work plan:

- **Validation 1** (mid-December): reduced checkpoints of what is built by then, on dev splits only, to
  see how things stand while there is still time to fix them. Its figures are interim; they turn no task
  ✅. If funding is confirmed by then, frozen modules may be measured at definitive size here.
- **Validation 2** (before the results chapter, E8.5): every definitive measurement, each suite once. A
  threshold missed here is reported as a result, not re-tuned.

Both passes together are capped at $30 unless funding arrives; under the cap a suite shrinks in scale
(inputs × repetitions × models, never below the 2 repetitions a std or an agreement metric needs), it is
not dropped. Two layers, kept separate:

- **§7.1 Evaluation needs** — *what* still needs measuring against a real model. Add a row whenever a DoD
  threshold (§4 of this doc, or `tfm-architecture-and-dod.md`) or an open question (§6) can only be
  answered by a measurement run. A need is not itself a thing to run.
- **§7.2 Measurement suites** — concrete runs, each covering one or more needs; needs that share a pass
  are merged into one suite rather than paid for twice (see EXP-01). A suite's final shape (inputs,
  repetitions, models) is fixed when its benchmark is designed, not before. This table moves to the
  evaluation budget document for supervisors once that is written (work plan task).

### 7.1 Evaluation needs

| ID | Need | Drives | Status |
|---|---|---|---|
| N1 | Forced-mode accuracy across repetitions (mean ± std, not a single pass/fail) on the full 117-question bank | E4.2, E4.3, E4.4 (per-family Done thresholds) and E4.7 (DoD report, §4.7) | A 1-repetition sweep (`v1-forced-1rep`) exists and meets every per-family threshold; the DoD's 3-repetition bar is unmet |
| N2 | Does the Expert abstain (free mode) exactly where its forced-mode answer would have been wrong, at the DoD's recall/false-request thresholds? | E4.5 (`abstention_recall` ≥ 70 %, `abstention_false_requests` ≤ 30 %, §4.5) | Harness built; the 4-question smoke (`e45-smoke`, $0.056) validated it end to end but gave no signal — zero forced-incorrect and zero abstentions in that tiny sample |
| N3 *(parked)* | Whether 3 repetitions is actually the right count for N1/N2, or fewer/more would materially change the read | Methodology question, not a DoD threshold | Raised 2026-09-22 as a side thought, not yet scoped as something worth spending on — revisit if N1/N2's results look unstable enough to justify it |
| N4 | Input Parser on held-out, second use: `intent` agreement ≥ 95 % over 3 runs with every other §4.1 threshold held | E5.1 (the first held-out pass, `v6-heldout`, missed only `intent` agreement: 93.9 %) | Validation 2, with the prompt frozen; labelled a second use and reported next to the first |

Add a row here first, before adding or changing anything in §7.2, whenever a new DoD threshold or
open question turns out to need a real run.

### 7.2 Experiment plans

| ID | Name | Covers | Scope | Model | Estimated cost | Notes |
|---|---|---|---|---|---|---|
| EXP-01 | `forced3-free-abstention` | N1 + N2 | 117 questions × 3 repetitions forced + free mode paired on the same questions, free-mode repetitions TBD | `deepseek/deepseek-v4.1-flash` | ≈ $2.9 (forced, fixed) + ≈ $1.0/repetition (free) → **≈ $3.9** at 1 free repetition or **≈ $5.8** at 3 (§4.2) | Validation 2 (a reduced checkpoint in Validation 1), after the ADR-0028 migration rebuilds the question bank. N1 and N2 both need a forced-mode sweep of the same questions; running it once at 3 repetitions serves N1 directly and *is* the forced half of N2's abstention pairing, so paying for a second, separate forced-mode pass would be redundant — merged for that reason. Free-mode repetition count (1 vs 3) is an open choice: 3 matches the forced count and gives mean ± std on N2's metrics too; 1 is cheaper with a single-point estimate. `--mode both` in `eval/expert_benchmark/run.py` runs both legs into the same `runs/<name>.jsonl`; use `--name forced3-free-abstention` to keep the file matching this row. |
