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
| v1 | — | Aggregation tools + domain concepts | planned | — | — | — | — | — | — | — |

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

### v1 — planned

- **Hypothesis.** Aggregation belongs in deterministic tools, not in the model's text. Generic tools that
  average across seeds, rank edges by a measure, and compare baseline with treatment should remove the
  text-only steps, cut input tokens on the 59 aggregation questions, and raise diagnostic and top-k accuracy
  without making the questions trivial.
- **Planned change.**
  - New tools: `edge_stats`, `rank_edges`, `compare_edges`, `compare_kpis` (new ADR, DoD §2.2).
  - `query_edgedata` described as expensive, to be used only when the others cannot express the need.
  - Domain concepts in the prompt: what delay and a bottleneck are, in terms of the measures.
- **Risk to watch.** Tools must stay generic (rank by *any* measure); a tool shaped like the gold answer
  would make the benchmark measure tool selection rather than reasoning.

## 4. Entry template

```markdown
### vN — <short name>

- **Configuration.** What differs from vN-1 (prompt / tools / budget / schema), with commits.
- **Hypothesis.** What should improve, and why.
- **Sweep.** `<name>`: questions × repetitions, cost.
- **Results.** Metrics table vs vN-1, plus steps / text-only steps / tokens per family.
- **Conclusion.** Kept or reverted, and what the next version tries.
```
