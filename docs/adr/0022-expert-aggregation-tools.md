# ADR-0022: Expert aggregation tools — `edge_stats`, `rank_edges`, `compare_edges`, `compare_kpis`

- Status: Accepted — extends the Expert tool list of DoD §2.2 and ADR-0018
- Date: 2026-09-17
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2, §4.7;
  [ADR-0011](0011-network-expert-knowledge-model.md), [ADR-0018](0018-network-expert-tools-and-evidence-refs.md);
  [`expert-tuning-log.md`](../expert-tuning-log.md) v0 → v1

## Context

In the v0 sweep, 48 of 117 questions ended without an answer. In 34 of them the model reasoned in text over
raw per-run edgedata of every edge (~17,000 characters per result) and was cut at the output-token limit;
none of the 19 top-k questions was answered. The only simulated-data tool returning per-edge measures was
`query_edgedata`, raw and per run, so every mean, ranking and baseline/treatment difference was mental
arithmetic in the model's text.

## Decision

- Four read-only tools over `ResultRepository`, deterministic, recorded in the evidence ledger like every
  Expert tool, and bound by the `result_ids` allow-list:
  - `edge_stats(result_ids, edge_ids, window)`: per edge and measure, mean, std and run count across runs.
  - `rank_edges(result_ids, measure, window, top_k, min_value, ascending)`: whole-network ranking by the
    mean of one measure.
  - `compare_edges(baseline_result_ids, treatment_result_ids, measure, window, edge_ids | top_k)`: per
    edge, both means, difference and relative change; named edges or the largest differences.
  - `compare_kpis(baseline_result_ids, treatment_result_ids)`: network KPIs, both means, difference and
    relative change.
- Measures are the per-edge contract measures plus `time_loss_per_vehicle`. Per-vehicle means
  (`travel_time`, `speed`, `time_loss_per_vehicle`) only count runs where the edge had traffic and are
  null when none had (ADR-0021).
- The tools are generic: any measure, any runs. No tool returns a question's answer shape (e.g. "the
  bottleneck"); the Expert still decides what to rank, compare and conclude.
- `query_edgedata` stays, described as expensive and a last resort.

## Consequences

- Aggregation questions need a few small tool results instead of several 17,000-character dumps.
- Answers still rest on ledger refs; excerpts now cite aggregated values the ledger holds exactly.
- The benchmark measures whether the Expert picks the right measure and comparison, not arithmetic.

## Alternatives considered

- **Raise the step and token budget.** Rejected: pays more for the same mental arithmetic.
- **A tool per question type (`bottleneck`, `edges_above`).** Rejected: the benchmark would measure tool
  selection, not reasoning.
