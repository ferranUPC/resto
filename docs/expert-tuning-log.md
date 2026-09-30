# Network Expert tuning log

- Status: living document, started 2026-09-17
- Purpose: record every change to the Network Expert agent — prompt, tool set, budget, answer schema — with
  the hypothesis behind it and its measured effect, so the thesis can explain how the Expert was optimised
  and why.
- Related: how answers are scored and aggregated is in [`evaluating-resto.md`](evaluating-resto.md) §4;
  thresholds are in [`tfm-architecture-and-dod.md`](tfm-architecture-and-dod.md) §4.7.

---

## 1. Method

- **Versions.** `EXPERT_VERSION` in `src/resto/adapters/llm/agents/expert.py` names the agent
  configuration. It is bumped whenever the prompt, the tool set or the default budget changes in a way
  that can change answers. Every benchmark run stores it, and every report shows it.
- **One sweep per version.** A version is measured on the whole DEV-NET question bank with
  `python -m eval.expert_benchmark.run --name <version>-<scope>`. Exploratory versions use 1
  repetition; a version reported as a result gets the DoD's 3 repetitions. Reports live in
  `eval/expert_benchmark/reports/`.
- **One entry per version**, in the template of §4: hypothesis, change (with commits), sweep, results
  against the previous version, cost, conclusion.
- **Development vs held-out data.** The DEV-NET bank is used for tuning, so results on it are optimistic by
  construction. The REAL-NET bank (E3.6) stays unseen until E4.8 and is where the thesis reports the
  Expert's performance. Every number quoted from this log must say which bank it comes from.
- **Measurement fixes are not optimisations.** A change that corrects what is measured (gold answers,
  scoring, traces) is logged separately (§2), because comparing versions across it would be misleading.

## 2. Measurement fixes before the baseline

Driven by two smoke runs on 5 questions (2026-09-17; `evaluating-resto.md` §4.7). None of these is an
agent optimisation; they make the baseline measurable and correct.

| Fix | Why | Reference |
|---|---|---|
| Question text names scenarios by description, never by matrix label (`S00`) | The Expert spent its first call trying `get_scenario("S00")` | commit `d172669` |
| Typed answer values (`Edges`, `Quantity`, `Change`) next to the prose | Prose cannot be scored reliably: an answer about "edges above 3.5 %" named edges below it | ADR-0019, commit `3ff760a` |
| Failed `submit_output` validations and unparseable tool calls recorded in the trace | A budget stop could not be explained | commit `6c42b4d` |
| `time_loss` / `waiting_time` treated as vehicle-second totals; diagnostic gold ranks by total `time_loss` | The contract averaged totals across intervals and the gold counted flow twice; 15 of 20 diagnostic gold answers changed | ADR-0020, commit `7171dfe` |
| Per-step trace: tools requested, text length, finish reason, tokens | Text-only steps cut at the token limit were invisible (suspected cause of the diagnostic budget stops) | `AgentRun.steps` |

## 3. Versions

| Version | Date | Change | Sweep | Descriptive acc. | Diagnostic Jaccard | Diagnostic cause acc. | CF direction | CF band | Brier | Accepted | Cost (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| v0 | 2026-09-17 | Baseline | `v0-forced-1rep` (117 × 1) | 0.68 | 0.10 | — | 0.79 | 0.89 | 0.08 | 0.59 | 1.54 |
| v0 re-scored | 2026-09-17 | Same runs, bank with `NoValue` gold (ADR-0021) | `v0-forced-1rep-rescored` | 0.57 | 0.10 | — | 0.79 | 0.89 | 0.13 | 0.59 | 0 |
| v1 | 2026-09-17 | Aggregation tools + expert practice in the prompt | `v1-forced-1rep` (117 × 1) | 1.00 | 0.70 | — | 1.00 | 1.00 | 0.02 | 0.94 | 0.98 |
| v2 | 2026-09-25 | Batched topology tools; **E3.8 (clock-time) bank** | `v2-e38-forced-1rep` (117 × 1) | 1.00 | 0.80 | 0.00 ¹ | 1.00 | 1.00 | 0.03 | 0.97 | 0.99 |
| v3 | 2026-09-25 | Bottleneck cause per edge (ADR-0029) | `v3-diag-1rep` (20 `-diag` × 1) | — ² | 0.10 | 1.00 (6 edges) | — | — | — | 0.10 | 0.32 |
| v4 | 2026-09-25 | Cause lookups in two steps; two-value diagnosis | `v4-diag-1rep` (20 `-diag` × 1) | — ² | 0.60 | 0.89 (36 edges) | — | — | — | 0.60 | 0.28 |
| v5 | 2026-09-30 | Per-tool guidance moved into the tool descriptions (ADR-0033) | `v5-diag-1rep` (20 `-diag` × 1) | — ² | 0.55 | 0.94 | — | — | — | 0.55 | 0.24 |

DoD thresholds (DEV-NET): descriptive ≥ 0.90, diagnostic Jaccard ≥ 0.60, diagnostic cause (the "why",
ADR-0029) ≥ 0.70, CF direction ≥ 0.75, CF band ≥ 0.50, Brier ≤ 0.25, accepted = 1.00.

¹ Re-scored after ADR-0029: v2 has no cause value, so every shared edge counts as wrong.
² Diagnostic-only sweeps: the other families were not run, and Brier and accepted cover the 20
diagnostic questions only. v3 to v5 changed only the diagnostic part of the prompt.

### v0 — baseline

- **Configuration.**
  - Model `deepseek/deepseek-v4.1-flash`; budget 6 steps, 2,048 output tokens, 300 s.
  - Tools: `get_edge`, `get_lanes`, `get_neighbours`, `shortest_path`, `capacity_estimate`, `get_tls`,
    `get_result`, `list_results`, `query_edgedata`, `get_scenario` (ADR-0018).
  - Typed answer values (ADR-0019); prompt as of the commit that introduced `EXPERT_VERSION`.
- **Hypothesis.** None: this is the reference every later version is compared with.
- **Expected issue.** Questions that aggregate over the whole network (`-desc-occ`, `-diag`, `-cf-topk`,
  59 of 117) must read raw per-seed edgedata of every edge (~17,000 characters per result) and do the
  arithmetic in text. The smoke runs saw two diagnostic budget stops.
- **Sweep.** `v0-forced-1rep`: 117 questions × 1 repetition, forced mode, 6 workers, ~35 min,
  1.54 USD, no crashes. Report: `eval/expert_benchmark/reports/v0-forced-1rep.md`.
- **Results.**

  | Family | Correct | Answered wrong | Budget stop | Rejected |
  |---|---|---|---|---|
  | `-desc-occ` | 11 | 8 | 1 | 0 |
  | `-desc-tt` | 16 | 0 | 4 | 0 |
  | `-diag` | 2 | 0 | 18 | 0 |
  | `-cf-dir` | 15 | 0 | 4 | 0 |
  | `-cf-topk` | 0 | 0 | 19 | 0 |
  | `-cf-band` | 17 | 0 | 2 | 0 |
  | **Total** | **61** | **8** | **48** | **0** |

  Descriptive accuracy 0.68, diagnostic Jaccard 0.10, CF direction 0.79 ✅, CF band 0.89 ✅, Brier 0.08 ✅,
  accepted 0.59 (budget stops count as not accepted). No answer was rejected for its evidence or values.

- **Findings.**
  1. **Budget stops are the main failure: 48 of 117 (41 %).** The per-step trace shows two mechanisms:
     - *Text reasoning cut at the 2,048-token limit* in 34 stops, concentrated where the whole network
       must be aggregated: 15 of 18 diagnostic stops and 16 of 19 top-k stops. This confirms the v1
       hypothesis.
     - *Exploration exhausting the 6 steps* (every step a tool call) in 14 stops, mostly questions whose
       data does not exist or is awkward: travel time and delay direction on an edge closed for the whole
       window (S01–S04 `-desc-tt`, S03/S04 `-cf-dir`), and signal-program windows not aligned to the
       300 s edgedata intervals (S15/S16 `-cf-dir`).
  2. **When the Expert answers, it is accurate: 61 of 69.** All 8 errors are `-desc-occ` with the same
     cause. The Expert lists an edge above 3.5 % in *any* seed (e.g. B2C2 at 2.96 / 2.79 / 3.55); the gold
     uses the 3-seed mean (3.10). The question does not say how to combine seeds, so this is an ambiguity
     in the bank, not only an Expert error.
- **Conclusion.** The aggregation tools of v1 target the dominant failure. Two defects of the question bank
  also surfaced (seed aggregation not stated; questions about edges without traffic) — see
  `evaluating-resto.md` §4.1. They are measurement fixes and are decided before v1 is compared with v0.

### Measurement fix between v0 and v1

S01–S08 `-desc-tt` asked for the travel time of an edge no vehicle crossed, with gold 0.0 s. Their gold is
now `no_value` and the Expert can answer `NoValue` (ADR-0021); no question text changed. v0's stored runs
were re-scored against the corrected bank at no cost (`v0-forced-1rep-rescored`): descriptive accuracy
0.68 → 0.57, because v0 could not express `NoValue` and answered 0.0 on four of them. v1 is compared
with this re-scored v0.

### v1 — aggregation tools and expert practice

- **Hypothesis.** Aggregation belongs in deterministic tools, not in the model's text. Generic tools that
  average across seeds, rank edges by a measure, and compare baseline with treatment should remove the
  text-only steps, cut input tokens on the 59 aggregation questions, and raise diagnostic and top-k accuracy
  without making the questions trivial.
- **Configuration** (`EXPERT_VERSION = "v1"`; model and budget as v0):
  - New tools `edge_stats`, `rank_edges`, `compare_edges`, `compare_kpis` (ADR-0022), listed first in the
    prompt; `query_edgedata` described as expensive, a last resort.
  - Prompt, "answer like a traffic engineer": mean across seed runs and mind the spread; total delay is
    `time_loss` and a bottleneck is where it concentrates; no vehicles → `no_value`, never 0; request
    independent tool calls together and submit as soon as the data supports an answer.
  - Prompt: `get_scenario` takes the `scenario_id` from `get_result`, never a result id (v0 wasted calls).
  - `NoValue` answer kind (ADR-0021).
- **Sweep.** `v1-forced-1rep`: 117 × 1, forced mode, 6 workers, 0.98 USD, no crashes.
- **Results** (against v0 re-scored).

  | Family | v0 correct | v1 correct | v1 budget stops |
  |---|---|---|---|
  | `-desc-occ` | 11 / 20 | 20 / 20 | 0 |
  | `-desc-tt` | 12 / 20 | 20 / 20 | 0 |
  | `-diag` | 2 / 20 | 14 / 20 | 6 |
  | `-cf-dir` | 15 / 19 | 19 / 19 | 0 |
  | `-cf-topk` | 0 / 19 | 18 / 19 | 1 |
  | `-cf-band` | 17 / 19 | 19 / 19 | 0 |
  | **Total** | **57 / 117** | **110 / 117** | **7** |

  Budget stops 48 → 7; no answer was wrong or rejected; cost 1.54 → 0.98 USD and input tokens 8.4 M →
  5.3 M (−37 %). `query_edgedata` was called 5 times in 117 runs. All DoD thresholds met on this single
  repetition except `accepted` (0.94).
- **Findings.**
  1. Aggregation tools removed the dominant failure: no text step was cut at the token limit outside the
     diagnostic family, and every top-k question but one was answered.
  2. The seed-mean instruction fixed all 8 `-desc-occ` errors; `NoValue` was used on all 8 edges without
     traffic.
  3. Remaining stops are diagnostic questions exploring topology to explain the "why" (`get_edge` 35,
     `get_neighbours` 30 calls across the 6 stops), plus 3 failed submissions.
  4. Every run fetches each result and scenario to tell baseline from treatment (522 `get_result`, 174
     `get_scenario` calls): the largest remaining source of steps.
- **Caveats.** One repetition; the DEV-NET bank is the tuning set, so these numbers are optimistic until
  3 repetitions and the held-out REAL-NET bank. The tools do more of the work, as intended (ADR-0022):
  the benchmark now measures choosing the right measure and comparison, not arithmetic.
- **Conclusion.** Kept. Next: the diagnostic budget stops (topology exploration for the "why") and the
  per-run `get_result`/`get_scenario` overhead; then a 3-repetition sweep of the retained version.
- **Risk to watch.** Tools must stay generic (rank by *any* measure); a tool shaped like the gold answer
  would make the benchmark measure tool selection rather than reasoning.

### v2 — batched topology tools

- **Status.** Code changed and unit-tested; a small-scale check on v1's 7 budget stops is done
  ($0.10); the DoD's 3-repetition sweep over the full bank is **deferred**, see below. *Update
  2026-09-25:* a 1-repetition development sweep of v2 ran on the rebuilt E3.8 bank; see
  "Development sweep on the rebuilt bank" below.
- **Configuration** (`EXPERT_VERSION = "v2"`; prompt and budget otherwise unchanged from v1):
  `get_edge`, `get_neighbours`, `capacity_estimate` and `get_tls` are replaced, Expert-side only, by
  `get_edges`/`get_neighbours`/`capacity_estimate`/`get_tls` taking a **list** of ids instead of one
  (`application/tools/expert.py`, `EXPERT_TOPOLOGY_TOOLS`). NetworkMCP itself
  (`application/tools/network.py`, the DoD-documented contract also exposed by
  `interface/mcp/network_server.py`) is untouched — the Expert still takes `get_lanes`/`shortest_path`
  from it as-is (`EXPERT_NETWORK_TOOLS`).
- **Hypothesis.** Re-reading the v1 trace of every budget stop with the actual tool-call *arguments*,
  not just names, showed the Expert was not looping on the same call: it ran a legitimate, broadening
  neighbourhood survey (top edges → their attributes → their neighbours → capacity → traffic lights →
  the neighbours' own neighbours). But NetworkMCP's topology tools take one id per call, so describing
  an 8-edge neighbourhood cost 20-30 separate tool calls and used 5 of the 6 available steps just
  gathering data, leaving none to close. Batching should free steps without changing how the Expert
  reasons about the question — no prompt change.
- **Small-scale check.** `v2-retry-failed`: the 7 questions that stopped on budget in v1 (`S00-diag`,
  `S03-diag`, `S05-diag`, `S06-diag`, `S16-diag`, `S17-diag`, `S12-cf-topk`), 1 repetition, $0.10.
  **4 of 7 now answer successfully** (S05-diag, S06-diag, S17-diag, S12-cf-topk). **3 still stop on
  budget** (S00-diag, S03-diag, S16-diag).
- **The remaining 3 show two mechanisms batching cannot fix, plus one that is not about tokens at
  all.**
  1. *A free-text step with zero tool calls, cut at the 2048-output-token limit* (S03-diag step 4,
     S16-diag step 4): the model writes unstructured reasoning instead of calling a tool; the text is
     cut before it says anything decisive, so the step produces no ledger entry and no progress.
  2. *A genuine tool call's own JSON arguments cut mid-generation* (S00-diag's `rank_edges` call,
     S16-diag's last-step `edge_stats` call): the model does call a tool, but the arguments — which
     repeat long content-hash result ids verbatim — are long enough to hit the same 2048-token ceiling
     before the JSON closes, so parsing fails and the step is wasted anyway.
  3. S00-diag specifically is neither: every one of its 6 steps *is* a tool call, yet it never once
     attempts `submit_output`. By step 3 it already has enough evidence (ranked edges, their
     attributes, capacity, neighbours, and the neighbours' own neighbours) but keeps broadening the
     search — more `rank_edges` calls on other measures — instead of converging.
- **`tool_choice="required"` considered, not applied.** Forcing every step to include a tool call
  (`anthropic_client.py` currently sets `tool_choice="auto"`) would remove mechanism 1 structurally —
  the provider cannot return a content-only turn — and is arguably consistent with this agent's own
  rule ("never state a fact you did not get from a tool call"): a free-text turn was never a
  legitimate way for it to make progress anyway. Decided against it for now: it is a permanent
  behavioural change to the `ToolAgent` loop shared by every agent module, not something scoped to
  these 3 questions, and it narrows the model's freedom to judge when it has enough evidence — a
  bigger architectural commitment than the (at most 2 of 3) failures it would close justify on their
  own. A softer alternative — a prompt sentence nudging the Expert to prefer a tool call over writing
  reasoning out — was drafted but also not applied, pending the decision below.
- **Not chasing 100% `accepted`.** The `accepted = 1.00` row in §3's version table is *not* a DoD
  requirement: `tfm-architecture-and-dod.md` §4.7 asks for "100% of answers **reference a resolvable
  artifact or query**" (evidence traceability of answers actually given — already true, 0 rejected
  answers in v1) plus the per-family accuracy thresholds, none of which demand zero budget stops.
  Remaining stops after v2 will be reported and characterised as a limitation of
  `deepseek/deepseek-v4.1-flash` on this question shape (loses steps to unstructured reasoning that
  gets cut; does not reliably recognise it has enough evidence to converge) rather than engineered
  around further on the light model. Trying a stronger model on just these cases is future work,
  gated on the explicit cost approval CLAUDE.md's LLM policy requires — not decided here.
- **Sweep.** Deferred (2026-09-17): the DoD's 3-repetition sweep over the full 117-question bank
  (≈ $2.9 at current rates — `evaluating-resto.md` §4.2) is postponed; a sponsor may cover the
  experiment budget. Run it, and fill in this entry's metrics table row, once that is resolved.
- **Conclusion.** Kept, pending the full sweep. `EXPERT_VERSION` is already bumped to `"v2"` so any
  future run is labelled correctly.

### Measurement fix after v2: the bank in clock time (E3.8, 2026-09-24)

ADR-0028 makes every window time of day. The DEV-NET demands moved from `[0, 3600)` to 08:00–09:00, and
the matrix and the question bank were rebuilt on them. Question text now reads "between 08:00 and 08:05"
instead of "between 0s and 300s", and every `scenario_id`/`result_id` changed. Gold answers are the
same except on the `signal_program` rows (S13–S16), whose windows moved to whole minutes (18 gold
answers). The Expert's tools now describe `window` as seconds since midnight, with 08:00–08:05 =
`[28800, 29100]` as the example, where they used to say "simulation seconds". Without that, a correct
reading of the new question text would query an empty window. This is a measurement fix, not an
optimisation: `EXPERT_VERSION` stays `"v2"`, and the v0–v2 figures above come from the old bank. The
first sweep on the rebuilt bank is v2's own sweep (E4.2–E4.4).

**Smoke on the rebuilt bank (2026-09-25).** Development run to check that v2 reads clock time, not a
sweep: `e38-clocktime-smoke`, 15 questions × 1 repetition, $0.137. The questions were the six S13
questions (`signal_program`, whose windows moved) plus S16-desc-tt/diag/cf-dir, S00-desc-occ/desc-tt/diag,
S03-cf-topk, S05-diag and S17-cf-band. 14 of 15 were correct. Every `window` the model passed was in
seconds since midnight (`[28800, 29100]`, `[28920, 29100]`, `[29460, 29640]`); none used the old
`[0, 300]` form. Descriptive 1.00, diagnostic Jaccard 0.75, CF direction 1.00, CF band 1.00, Brier 0.02
(15 questions, not a figure to quote against the DoD). The one failure is S05-diag stopping on budget
without an answer, the known diagnostic budget-stop pattern (v2 answered it correctly in
`v2-retry-failed`), not a migration effect.

**Development sweep on the rebuilt bank (2026-09-25, E4.2–E4.4).** At first the full 1-repetition sweep
was not going to run; the maintainer reversed that in E4.4's triage, because the M2 acceptance and the
E4.2–E4.4 rows ask for a development sweep on the E3.8 bank with per-family figures. One sweep serves the
three tasks. `v2-e38-forced-1rep`: 117 × 1, forced, `EXPERT_VERSION = "v2"` unchanged, 6 workers,
$0.99 (cap $1.30), no crashes. Report: `eval/expert_benchmark/reports/v2-e38-forced-1rep.md`.

| Family | Correct | Budget stops | Notes |
|---|---|---|---|
| `-desc-occ` | 20 / 20 | 0 | |
| `-desc-tt` | 20 / 20 | 0 | |
| `-diag` | 16 / 20 | 4 | Jaccard 0.80 (v1, old bank: 0.70) |
| `-cf-dir` | 19 / 19 | 0 | |
| `-cf-topk` | 17 / 19 | 0 | Jaccard 0.89 |
| `-cf-band` | 19 / 19 | 0 | |
| **Total** | **111 / 117** | **4** | |

- **Against the DoD (one repetition, tuning bank, not a reported result).** Descriptive 1.00 ≥ 0.90,
  diagnostic Jaccard 0.80 ≥ 0.60, CF direction 1.00 ≥ 0.75, CF band 1.00 ≥ 0.50, Brier 0.03 ≤ 0.25.
  No tuning change is needed for E4.2, E4.3 (Jaccard; the "why" rubric is not scored by the harness) or
  E4.4, so `EXPERT_VERSION` stays `"v2"`.
- **Basis.** 113 answers: 112 `observed` (accuracy 0.98), 1 `inferred` (S14-cf-band, correct), none
  `extrapolated`, as expected with every result available (§4.5 of `evaluating-resto.md`). Every CF
  answer but that one is `observed`.
- **The 4 budget stops are all diagnostic** (S00, S05, S10, S11): 6 steps each, and in every one of them
  one step ends with `finish_reason = length` and no tool call. This is mechanism 1/2 of v2's small-scale
  check (text or tool arguments cut at 2,048 output tokens). They are the only runs without an answer, so
  `accepted` is 113/117 = 0.97; no answer was rejected at promotion. E4.3's to handle.
- **The 2 `-cf-topk` misses are answer-shape errors, not wrong content** (S07-cf-topk, S16-cf-topk). Both
  name exactly the five gold edges with the gold deltas, in order, in the prose and in the evidence
  excerpt. But `values` holds five per-edge `change` entries instead of one `edges` value, so the scorer
  reports "missing edges value". `-cf-topk` has no DoD threshold of its own. A prompt line on "top k →
  one `edges` value" would be a v3 change; it is not made here.
- **Migration check.** Accuracy on the rebuilt bank matches or beats v1 on the old bank in every
  family. The clock-time move (ADR-0028) cost no accuracy, and batching (v2) cut the diagnostic budget
  stops from 6 to 4.

### v3: a typed Bottleneck cause per edge (E4.3, ADR-0029)

- **Configuration** (`EXPERT_VERSION = "v3"`, commit `c759a21`; tools, budget and model as v2):
  - a new answer value kind, `causes` (`BottleneckCauses`), holds one (edge, cause) pair for each
    bottleneck edge;
  - the prompt lists the kind and defines the five causes in precedence order: `intervention` >
    `merge` > `spillback` > `signal` > `demand`, first match wins;
  - the diagnostic question text now asks "why is each of them congested?" (bank rebuild `b137b36`);
  - the benchmark grades the cause of every edge the answer shares with the gold (`537d910`).
- **Hypothesis.** A judge model is not needed to grade the "why" of a diagnosis if the Expert states
  it as a closed category. The facts it needs (the target, the traffic lights, the lanes) come from
  tools the Expert already calls when it explains a bottleneck in prose. The new value should
  therefore cost little more than a few output tokens in the final submission. Risk noted in the
  spec: the diagnostic family already reached the 2,048-token limit.
- **Sweep.** `v3-diag-1rep`: the 20 `-diag` questions × 1, forced, 6 workers, $0.32 (estimated
  $0.25, cap $0.40). The other families are unaffected and were not rerun. Report:
  `eval/expert_benchmark/reports/v3-diag-1rep.md`.
- **Results** (against v2 on the same 20 questions of the E3.8 bank, taken from `v2-e38-forced-1rep`).

  | | v2 | v3 |
  |---|---|---|
  | Answered (all with Jaccard 1.00) | 16 / 20 | 2 / 20 |
  | Diagnostic Jaccard | 0.80 | 0.10 |
  | Cause accuracy | 0.00 (no value) | 1.00 (6 / 6 edges) |
  | Budget stops | 4 | 18 |
  | Steps | 100 | 117 |
  | Text-only steps cut at 2,048 tokens | 4 | 21 |
  | Tool calls (failed) | 222 (3) | 315 (30) |
  | `get_tls` calls (failed) | 9 (1) | 48 (24) |
  | Output tokens | 84.8 k | 129.8 k |
  | Cost (USD) | 0.23 | 0.32 |

- **Findings.** The value itself works: both answers named the right three edges and gave the right
  cause for all six. The failures came before that point. The traces show three mechanisms:
  1. *Guessing traffic-light ids.* `signal` and one form of `intervention` depend on which light
     controls an edge. No tool lists the lights: `get_tls` takes ids, so the Expert guessed them (`B1`,
     `A1`, `B2C2`, `tls_A1`, `0`, …). One unknown id fails the whole batched call. 24 of the 48
     `get_tls` calls failed, and every failure cost a step. S06 made 10 `get_tls` calls, 6 of them
     failed, and it never answered.
  2. *Hunting for lane drops.* To check `merge` ("the road loses a lane"), the Expert called
     `get_lanes` on one edge after another, up to 8 times in one step, although `get_edges` already
     returns `lane_count`.
  3. *Deliberation cut at the token limit.* 21 steps ended with `finish_reason = length` and produced
     no text and no tool call. The model spent its 2,048 output tokens reasoning about the precedence
     rule before it acted (S00, S04, S07 and S11 lost three steps each this way).
  Each of the 18 stops falls into one of three groups:
  - 10 lose at least one step to a cut text-only step (S00, S02, S03, S04, S07, S09, S11, S12, S17,
    S18);
  - 6 use up all 6 steps on tool calls, mostly failed `get_tls` calls and `get_lanes` (S05, S06, S10,
    S14, S16, S19);
  - 2 submit an answer cut at the limit that has lost its `evidence`, which is rejected (S01, S13).
- **Conclusion.** The contract stays: the value, the gold rule and the grading are kept. The prompt
  must also tell the Expert how to get the facts cheaply. Cause accuracy is formally ≥ 0.70, but
  measured on 6 edges it means nothing, and Jaccard 0.10 fails E4.3. Next version: v4.

### v4: cause lookups in two steps, a diagnosis with two values

- **Configuration** (`EXPERT_VERSION = "v4"`; prompt only, with tools, budget and model as v3). The
  diagnosis paragraph of the prompt:
  - says a diagnosis carries exactly two values (ranked edges and causes) and puts its numbers in a
    short `answer`; v3 also sent `quantity` and `no_value` values (S08 submitted 7);
  - defines each cause with fields the tools return (`to_node`, `from_node`, `lane_count`) instead of
    in words ("feeds", "loses a lane");
  - lists the lookups the causes need, in two steps once the edges are ranked:
    1. `get_scenario`, then `get_edges` and `get_neighbours` on the ranked edges;
    2. `get_edges` on the target and on the edges the ranked edges lead into, and `get_tls` on each
       edge's `to_node`, one call per id: a light usually has its junction's id (netconvert's
       default, general SUMO knowledge rather than anything specific to DEV-NET), and an unknown id
       only means there is no light;
  - ends with "Then submit; look no further."

  Caveat: the lookups fetch the edges a ranked edge leads into, not the edges that lead into it. A
  lane drop at the *start* of an edge is only visible if its feeder is fetched for some other reason.
  DEV-NET's gold has no `merge` cause, so this sweep cannot show the gap; REAL-NET's bank (E3.6) can.
- **Hypothesis.** v3's stops came from searching for facts (light ids, lane counts) and from
  deliberating over the rule. Naming the fields and the exact lookups should remove the search, and
  with one `get_tls` call per id a miss no longer costs a step. With fewer open choices, the
  reasoning should also get shorter.
- **Sweep.** `v4-diag-1rep`: the 20 `-diag` questions × 1, forced, 6 workers, $0.28 (estimated
  $0.30, cap $0.40). Report: `eval/expert_benchmark/reports/v4-diag-1rep.md`.
- **Results.**

  | | v2 | v3 | v4 |
  |---|---|---|---|
  | Answered (all with Jaccard 1.00) | 16 / 20 | 2 / 20 | 12 / 20 |
  | Diagnostic Jaccard | 0.80 | 0.10 | 0.60 |
  | Cause accuracy | 0.00 (no value) | 1.00 (6 / 6) | 0.89 (32 / 36) |
  | Budget stops | 4 | 18 | 8 |
  | Steps | 100 | 117 | 113 |
  | Text-only steps cut at 2,048 tokens | 4 | 21 | 11 |
  | Tool calls (failed) | 222 (3) | 315 (30) | 238 (11) |
  | `get_tls` calls (failed) | 9 (1) | 48 (24) | 40 (10) |
  | Rejected `submit_output` attempts | 6 | 2 | 8 |
  | Output tokens | 84.8 k | 129.8 k | 104.7 k |
  | Cost (USD) | 0.23 | 0.32 | 0.28 |

- **Findings.**
  1. As in v2, every answer names the gold top-3 (Jaccard 1.00 on all 12). The diagnostic Jaccard
     is therefore the share of questions answered: 0.60 means 12 answers out of 20.
  2. The spelled-out lookups did their job: failed tool calls fell from 30 to 11 and failed
     `get_tls` calls from 24 to 10, and text-only steps cut at the limit fell from 21 to 11.
  3. All 4 wrong causes (out of 36) are a `spillback` given too readily:
     - S00 A2B2 and S12 A2B2 and B2C2 are labelled `spillback` because they lead into another edge
       of the top-3. That edge is ranked *lower*, however, and the rule needs a worse (higher-ranked)
       edge downstream. Gold: `signal`.
     - S09 A2B2 does lead into the top-ranked edge, but the target light controls it, so
       `intervention` comes first. The Expert missed the precedence.
  4. The 8 stops, one by one:
     - 6 lose steps to reasoning cut at 2,048 tokens with no tool call (S03, S04, S05, S07, S11,
       S14);
     - 1 has a tool call cut at the limit: its `edge_stats` call lost its `edge_ids` argument and
       failed, and the retry took the last step (S10);
     - 1 submits an answer cut at the limit that has no `evidence`, and has no step left to retry
       (S19).
  5. The limit also shows up in the submissions: 8 `submit_output` attempts were cut at 2,048 tokens
     and rejected (7 had lost `evidence` or `values`, 1 was invalid JSON). 7 of them succeeded on a
     second submission one step later (S00, S02, S08, S12, S15, S16, S18). Only S19 had no step left.
  Every remaining failure, whether a stop or a rejected submission, is the 2,048-token output limit
  per step: the reasoning and the prose `answer` do not fit in the final step, or the reasoning over
  the rule fills a step with nothing to show for it.
- **Against the DoD** (one repetition on the tuning bank, not a reported result). Jaccard 0.60 ≥ 0.60
  and cause accuracy 0.89 ≥ 0.70: the E4.3 development sweep meets both bars. The Jaccard margin is
  zero, because one more stop would fail it.
- **Conclusion.** v4 is kept. It recovers most of what v3 lost (stops 18 → 8) but not v2's level (4).
  The next levers are each the maintainer's decision and none is taken here:
  - the `spillback` wording ("a *higher-ranked* edge") and a reminder of precedence: a prompt change
    that fixes at most 4 edges and does nothing for the stops;
  - the output limit of 2,048 tokens per step, which is now the only mechanism behind every stop. A
    raise for the Expert's call is a deliberate `Budget` decision (CLAUDE.md), with its cost stated
    first;
  - `tool_choice="required"` (see v2), which is outside E4.3.
- **Why the stops happen, and what was left for later** (analysis of the v4 traces, 2026-09-25, no
  new run).
  - *Hidden reasoning, not hallucination.* Unlike the text-only steps of v0–v2, the 11 cut steps
    contain no visible text (`text_chars = 0`) and no tool call. DeepSeek v4.1 Flash reasons before
    it answers, and OpenRouter counts that reasoning as output tokens. The model thinks for the whole
    2,048 tokens and is cut before it acts. The cut submissions are the same case: the arguments
    take about 300–900 tokens and reasoning takes the rest. No answer states a fact it did not get
    from a tool, and every answer names the gold edges. The client does not record the reasoning,
    so what the model thinks in those steps cannot be read.
  - *No slack in the step budget.* The lookups the prompt asks for take 5 of the 6 steps:
    `get_result`, then `get_scenario` + `rank_edges`, then `get_edges` + `get_neighbours`, then
    `get_edges` + `get_tls`, then `submit_output`. A single cut step is enough to leave a run
    without an answer.
  - *Levers identified, in the order they would be tried before any raise of the output limit.*
    1. Record the reasoning in the trace (`include_reasoning`); this costs nothing.
    2. Cap the reasoning separately from the output. OpenRouter's `reasoning` and
       `reasoning_effort` are supported for this model (checked on its models endpoint). It must
       be per-agent configuration, and its effect on cause accuracy must be measured.
    3. Shorten the chain with Expert-side tools, as v2's batching did: `get_edges` could report
       the traffic light that controls each edge, and `get_result` the scenario's interventions.
       The chain would drop from 5 steps to about 3. Traffic-light control is a topology fact,
       not the gold answer.
    4. A specific nudge after a cut step, since the loop currently answers it with the generic
       "call a tool or submit". Little expected, because in v4 the cuts are rarely consecutive.
  - *Decision (maintainer, 2026-09-25).* None of these is applied now. v4 meets both E4.3 bars,
    and further tuning would optimise past the DoD at the maintainer's own cost. The accepted risk
    is the zero Jaccard margin: if EXP-01 in Validation 2 reads below 0.60, that is reported as a
    result, not re-tuned. Levers 1–2 are cheap enough (≈ $0.35 including their sweep) to try before
    Validation 1 if the calendar allows.

### v5: per-tool guidance moved into the descriptions (refactor r3, ADR-0033 part 2)

- **Configuration** (`EXPERT_VERSION = "v5"`; tools, budget, model and answer schema as v4). Advice that
  concerns one tool left the system prompt and went into that tool's description:
  - `query_edgedata` says it is very large and a last resort (the prompt keeps "raw data, only when the
    aggregated tools cannot express what you need");
  - `get_scenario` says to pass the `scenario_id` from `get_result`, never a result id, and `get_result`
    says its `scenario_id` is what `get_scenario` takes;
  - `get_tls` says to give one id per call, that an unknown id only means there is no light, and that a
    light usually has the id of its junction (removed from the diagnosis paragraph).
  The cross-tool rules stay in the prompt: facts only through tools, aggregated tools first, evidence
  format, basis and mode. The descriptions of `get_edges`, `get_neighbours`, `capacity_estimate`,
  `compare_edges` and `compare_kpis` also stopped mid-sentence since the r3 migration; they are now the
  full sentence of their docstring.
- **Hypothesis.** Same information in a different place, so accuracy should not move. Any change would
  be noise from a single repetition.
- **Sweep.** `v5-diag-1rep`: the same 20 `-diag` questions as v4 × 1, forced, 6 workers, estimated
  $0.24, real $0.145 as billed (estimated before the run: $0.30, cap $0.40). A development run, no
  held-out split. Report: `eval/expert_benchmark/reports/v5-diag-1rep.md`.
- **Results.**

  | | v4 | v5 |
  |---|---|---|
  | Answered (all with Jaccard 1.00) | 12 / 20 | 11 / 20 |
  | Diagnostic Jaccard | 0.60 | 0.55 |
  | Cause accuracy | 0.89 (32 / 36) | 0.94 |
  | Budget stops | 8 | 9 |
  | Steps | 113 | 101 |
  | Text-only steps cut at 2,048 tokens | 11 | 12 |
  | Tool calls | 238 | 226 |
  | `get_tls` calls | 40 | 53 |
  | `query_edgedata` calls | 0 | 0 |
  | Output tokens | 104.7 k | 81.4 k |
  | Cost (USD, estimated) | 0.28 | 0.24 |

- **Conclusion.** Kept. The one-answer difference (11 against 12) is within what one repetition can
  show, and every remaining stop is the reasoning cut at the 2,048-token limit, as in v4. Cause
  accuracy and tool use are unchanged in kind. Jaccard 0.55 is under the 0.60 bar on this
  1-repetition development sweep; v4 sat exactly on it with no margin, and the decision of
  2026-09-25 (no re-tuning for it before Validation 1) still applies. Nothing was rerun.

### Diagnostic questions from v0 to v4

The diagnostic family is the one that drove most of the tuning. Its history in one table (1
repetition each, 20 questions; v0–v1 on the old bank, v2–v4 on the E3.8 bank):

| Version | What changed for the diagnosis | Answered | Jaccard | Cause acc. | Budget stops | Main failure |
|---|---|---|---|---|---|---|
| v0 | Baseline: raw per-seed edgedata | 2 | 0.10 | — | 18 | Aggregation done in text, cut at 2,048 tokens |
| v1 | Aggregation tools (`rank_edges`, `edge_stats`, …) | 14 | 0.70 | — | 6 | Topology survey for the prose "why", one id per call |
| v2 | Batched topology tools | 16 | 0.80 | not asked | 4 | Text or tool arguments cut at 2,048 tokens |
| v3 | Typed cause per edge (ADR-0029) | 2 | 0.10 | 1.00 (6 edges) | 18 | Guessing light ids, hunting lane drops, deliberation cut |
| v4 | Cause lookups spelled out; a diagnosis with two values | 12 | 0.60 | 0.89 (36 edges) | 8 | Reasoning cut at 2,048 tokens |

The same pattern holds in every version: when the Expert answers, it names the right edges, and what
changes is whether it answers within 6 steps of 2,048 output tokens. The versions changed this as
follows:
- v1 moved the arithmetic into tools and v2 cut the number of topology calls;
- v3 asked for more, a typed cause per edge, and left the Expert to find the facts on its own, which
  spent its budget on searching;
- v4 told the Expert which fields answer each cause and which calls fetch them. That recovered most
  of the loss, with 0.89 cause accuracy.

The limit left at the end is the one first seen in v0: the output-token budget per step.

Spent on Expert runs so far (sum of the runs' estimated costs; v5 billed $0.145 of its $0.24): **$4.71** (v0 $1.54, v1 $0.98, v2 retry $0.10, smokes $0.27,
`v2-e38-forced-1rep` $0.99, `v3-diag-1rep` $0.32, `v4-diag-1rep` $0.28, `v5-diag-1rep` $0.24 estimated, $0.145 billed). E4.3's share is $0.60.

## 4. Entry template

```markdown
### vN — <short name>

- **Configuration.** What differs from vN-1 (prompt / tools / budget / schema), with commits.
- **Hypothesis.** What should improve, and why.
- **Sweep.** `<name>`: questions × repetitions, cost.
- **Results.** Metrics table vs vN-1, plus steps / text-only steps / tokens per family.
- **Conclusion.** Kept or reverted, and what the next version tries.
```
