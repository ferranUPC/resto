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

| Version | Date | Change | Sweep | Descriptive acc. | Diagnostic Jaccard | CF direction | CF band | Brier | Accepted | Cost (USD) |
|---|---|---|---|---|---|---|---|---|---|---|
| v0 | 2026-09-17 | Baseline | `v0-forced-1rep` (117 × 1) | 0.68 | 0.10 | 0.79 | 0.89 | 0.08 | 0.59 | 1.54 |
| v0 re-scored | 2026-09-17 | Same runs, bank with `NoValue` gold (ADR-0021) | `v0-forced-1rep-rescored` | 0.57 | 0.10 | 0.79 | 0.89 | 0.13 | 0.59 | 0 |
| v1 | 2026-09-17 | Aggregation tools + expert practice in the prompt | `v1-forced-1rep` (117 × 1) | 1.00 | 0.70 | 1.00 | 1.00 | 0.02 | 0.94 | 0.98 |

DoD thresholds (DEV-NET): descriptive ≥ 0.90, diagnostic Jaccard ≥ 0.60, CF direction ≥ 0.75, CF band ≥ 0.50,
Brier ≤ 0.25, accepted = 1.00.

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

### v2 — batched topology tools (in progress, sweep deferred)

- **Status.** Code changed and unit-tested; a small-scale check on v1's 7 budget stops is done
  ($0.10); the DoD's 3-repetition sweep over the full bank is **deferred**, see below — do not treat
  this entry as a reported result yet.
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

## 4. Entry template

```markdown
### vN — <short name>

- **Configuration.** What differs from vN-1 (prompt / tools / budget / schema), with commits.
- **Hypothesis.** What should improve, and why.
- **Sweep.** `<name>`: questions × repetitions, cost.
- **Results.** Metrics table vs vN-1, plus steps / text-only steps / tokens per family.
- **Conclusion.** Kept or reverted, and what the next version tries.
```
