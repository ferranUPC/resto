# eval/

Evaluation assets and harness (architecture doc §3): DEV-NET, demand profiles, scenario matrix,
question / request / builder / derivation banks, metrics and repeated-run harness. Outside the
hexagon; imports `resto.application`.

- Status: living document, started 2026-09-17 (as `docs/evaluating-resto.md`, split into `eval/` on 2026-10-06)
- Scope: how every part of RESTO is measured: assets, run protocols, answer types, scoring rules,
  aggregation, costs, and the decisions behind them.
- Relation to other docs: the **thresholds** stay in [`tfm-architecture-and-dod.md`](../docs/tfm-architecture-and-dod.md)
  §4 (per module) and §5 (integration), which remains the source of truth. This document defines *how* each
  metric is computed so that a threshold there has one unambiguous procedure here. Where the two disagree,
  fix this document, or amend the architecture through an ADR.
- Sibling files: [`decisions-log.md`](decisions-log.md) (the decisions behind the rules below, and open
  questions) and [`measurement-plans.md`](measurement-plans.md) (validation passes, evaluation needs and
  the priced measurement suites). The cost rules live in [`docs/llm-cost-policy.md`](../docs/llm-cost-policy.md).

---

## 1. Principles

1. **Simulation is ground truth.** Gold answers are computed by code from stored simulation results, never
   written by hand or by an LLM.
2. **Agents are evaluated statistically.** Every agent benchmark runs the same inputs 3 times and reports
   mean ± std; a single run proves nothing about an LLM step.
3. **Tests never call a real model.** `pytest` uses the shared `FakeToolAgent` (ADR-0001). Benchmarks against
   a real model are manual runs with an estimated cost confirmed before spending (`docs/llm-cost-policy.md`):
   a *development run* (smoke, tuning, a 1-repetition check) runs now; a *measurement run* (the figure a
   DoD threshold reads) waits for a validation pass ([`measurement-plans.md`](measurement-plans.md)).
4. **Raw runs are kept.** A benchmark stores every agent run (output, tool calls, ledger, tokens, cost) so
   metrics can be recomputed or corrected without paying for the runs again.
5. **Structured before judged.** A metric compares typed values whenever possible; free-text grading
   (rubric, LLM-as-judge) is used only where no typed value exists, and its agreement with a human is
   measured before it is trusted.
6. **Budgets are stated in tokens first, dollars second.** Every run-protocol section records measured
   (or, before a sweep has run, best-estimate) input/output tokens per family per run. The dollar figure
   for the current default model is that token count run through `resto.adapters.llm.pricing`'s per-token
   rate — never a number re-derived by hand. Pricing a different model, including a paid escalation (which
   still needs the explicit approval and cost confirmation `docs/llm-cost-policy.md` requires), is then
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
| Derivation bank (10 modifications) | Network Author | pending (E6.2) | — |
| GEN-LOCATIONS (10 raw OSM locations) | Network Author | pending (E6.2) | — |
| REAL-NET + matrix + question bank | Expert on a real network | pending (E8.1, E8.3, E8.4) | — |
| Golden-path framework (GP-1…GP-11) | Integration | pending (E9.1) | — |

---

## 3. What is evaluated, per module

Detailed procedures exist so far only for the Network Expert (§4). The other rows list the metrics the DoD
already fixes; each procedure is written here when its benchmark task starts, not before.

| Module | Benchmark asset | Metrics (DoD) | Procedure |
|---|---|---|---|
| Input Parser | request bank | schema validity, field match, ambiguity detection, `intent` agreement (§4.1); arm structure ≥ 90 % on multi-arm requests ([`decisions-log.md`](decisions-log.md), 2026-09-23) | E5.1 (`eval/parser_benchmark`, [`docs/tuning/parser-tuning-log.md`](../docs/tuning/parser-tuning-log.md)), E5.8 |
| Coordinator | plan bank | routing vs gold plan (§4.2); the `StepRecord` trace is Executor behaviour, checked by fake-agent tests (ADR-0023) | E5.5, E5.8 |
| Network Author | GEN-LOCATIONS, derivation bank | loadable networks, sanity report, replay determinism, agent stability (§4.3) | E6.2 |
| Demand Generator | demand profiles, control counts | calibration fidelity ±15 % DEV / ±25 % REAL, replay determinism (§4.4) | E7.4 |
| Scenario Builder | builder bank | mechanism selection, validity, effect verification ≥ 27/30, authoring determinism (§4.5) | E2.7 |
| Simulation Runner | unit tests | reproducibility 20/20, sandbox, latency (§4.6) | done (E2.1), online mode E2.5 |
| **Network Expert** | **question bank** | **§4.7 — see §4 below** | **E3.3** |
| Output Composer | 20 reports | claim traceability, no claims absent from `ExpertAnswer` (§4.8) | E5.7 |
| Integration | golden paths GP-1…GP-11 | trace match 11/11 on 3 runs, reproducibility, no silent failures (§5) | E9.5 |

---

## 4. Network Expert

How the Expert itself is tuned between measurements — versions, hypotheses, results — is recorded in
[`docs/tuning/expert-tuning-log.md`](../docs/tuning/expert-tuning-log.md).

### 4.1 Question bank (E3.2)

Generated by `python -m eval.question_bank.build` from the DEV-NET / peak scenario matrix; 117 questions,
all `mode = forced`, every gold answer computed programmatically (`eval/question_bank/gold.py`,
`templates.py`).

| Family | Id suffix | Count | Question | Gold answer computed from |
|---|---|---|---|---|
| Descriptive | `-desc-occ` | 20 | Which edges exceed 3.5 % occupancy in the window? | `query_edgedata`, occupancy > 3.5 |
| Descriptive | `-desc-tt` | 20 | Mean travel time on a target edge in the window? | `query_edgedata`, `travel_time` |
| Diagnostic | `-diag` | 20 | Which three edges form the main bottleneck, and why is each of them congested? | top-3 by total `time_loss`; a Bottleneck cause per edge (ADR-0029) |
| Counterfactual | `-cf-dir` | 19 | Does the total delay on the target edge increase, decrease, or stay within 5 %? | total `time_loss` on the edge, row vs baseline S00 |
| Counterfactual | `-cf-topk` | 19 | Which 5 edges change most in total delay? | top-5 by \|Δ total `time_loss`\|, row vs S00 |
| Counterfactual | `-cf-band` | 19 | By roughly how much does network-wide mean delay change? | `kpis.mean_delay`, row vs S00, banded |

Generation rules:

- **Seeds.** Every gold value is the mean over the row's 3 seeds; per-seed values are kept in `evidence`.
- **Delay.** SUMO's `time_loss` is the total time lost by all vehicles on the edge (vehicle-seconds), so
  it already is "per-vehicle delay × flow"; bottlenecks rank by it directly (ADR-0020).
- **Window.** Time of day (ADR-0028). The row's own intervention window; 08:00–08:05 (`[28800, 29100)`,
  the `peak` demand's first 300 s) for rows without one (baseline, `demand_scale`). Question text
  writes clock times ("between 08:00 and 08:05").
  Counterfactuals query the baseline with the *row's* window, never the baseline's default.
- **Target edge.** The row's intervention edge; the edge downstream of the junction for `signal_program`
  rows (`A2`→`A2B2`, …); `B2C2` for `demand_scale` rows.
- **Occupancy threshold 3.5 %.** Chosen from the matrix itself: baseline occupancy tops out near 3 % in
  08:00–08:05, a lane closure's upstream queue near 6 %.
- **Bottleneck cause** (ADR-0029). One cause per top-3 edge, first match wins: `intervention` (the edge is
  the target edge, feeds it directly, or is controlled by the target traffic light; never for
  `demand_scale`), `merge` (a known lane drop: `B0C0`, `C0D0` on DEV-NET), `spillback` (feeds a
  higher-ranked edge of the same top-3), `signal` (controlled by any traffic light), `demand`. DEV-NET's
  gold totals 21 `intervention`, 33 `signal`, 6 `spillback`. Graded (§4.4).
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
- *Found by the v0 sweep (`docs/tuning/expert-tuning-log.md`), pending a decision:*
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
(EXP-01) in Validation 2 (`measurement-plans.md`).

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
token-limit-cut steps (3 of 20 runs each, 2026-09-17 sweep) — see `docs/tuning/expert-tuning-log.md` v1/v2 for
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
| `-diag` "why" | `BottleneckCauses` | per shared edge: predicted cause equals the gold cause (ADR-0029) | cause accuracy (`diag_cause_accuracy`) | "why" ≥ 70 % |
| `-cf-dir` | `Change(time_loss)` on the gold edge | direction equals gold (`unchanged` ↔ within 5 %) | accuracy | direction ≥ 75 % |
| `-cf-topk` | first `Edges` | Jaccard(predicted set, gold top-5) ≥ **0.6** | mean Jaccard + accuracy | none |
| `-cf-band` | network-wide `Change(mean_delay)` | has a percentage and `magnitude_band(pct)` equals gold | accuracy | band ≥ 50 % |

- Descriptive accuracy is reported over both descriptive families together, as the DoD states one threshold.
- The predicted edge set is scored as given, never truncated to 3 or 5: extra edges lower the Jaccard.
- An edge is a (network id, edge id) pair (ADR-0032). Every gold answer that names an edge carries
  `network_id`, the question's `network_ref`; `-cf-band` names none. The right edge on the wrong network
  scores as wrong, and the Jaccard and the cause count run over pairs.
- **Re-scoring runs stored before ADR-0032** (`--report-only`). Those answers name edges without a
  network. They are read, not refused: each edge is taken to be on the question's `network_ref`, which is
  the only network the Expert saw in those runs. A value that already names its network is left as it is.
  Re-scored figures of old runs do not change.
- Mean Jaccard counts a missing or rejected answer as 0.
- Cause accuracy counts only the edges in both the predicted top-3 and the gold's, so a wrong edge costs
  once (in the Jaccard). An answer without a `BottleneckCauses` value scores every shared edge wrong; a
  missing or rejected answer shares no edges. Per repetition it is correct causes ÷ shared edges summed
  over the diagnostic questions (micro-average), then mean ± std across repetitions.

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
  in both modes (`--mode both`). **Deferred**: the full-bank sweep is a measurement run (EXP-01, `measurement-plans.md`).

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
  before the development/measurement split (`decisions-log.md`, 2026-09-24); E4.6's Done stands on it and is not
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
