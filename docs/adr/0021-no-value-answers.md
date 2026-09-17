# ADR-0021: `NoValue` — an evidence-backed "this measure is undefined" answer

- Status: Accepted — adds a kind to ADR-0019's `AnswerValue`
- Date: 2026-09-17
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3, §4.7;
  [ADR-0019](0019-typed-expert-answer-values.md); [`expert-tuning-log.md`](../expert-tuning-log.md) v0

## Context

The v0 benchmark asked for the mean travel time of edges closed for the whole window (S01–S08
`-desc-tt`). No vehicle crossed them, `query_edgedata` zero-fills the measures, and the gold said 0.0 s:
a physically meaningless travel time. The Expert either answered 0.0 or spent its whole budget looking
for data that does not exist. The correct expert answer is "undefined: no vehicle crossed the edge", but
`values` had no way to say it, and abstaining (`needs_simulation`) means something else — missing data —
and is not allowed in forced mode.

## Decision

- `AnswerValue` gains `NoValue(measure, edge_id, reason)`, with `reason = no_traffic`.
- Only per-vehicle means (`travel_time`, `speed`) can be undefined; a 0 % occupancy or a zero total delay
  is a real value, so `NoValue` rejects every other measure.
- Question bank: a travel-time gold averages only the runs where the edge had traffic
  (`sampled_seconds > 0`), and is `no_value` when none had. Scoring accepts `NoValue` exactly there and
  counts it as wrong on an edge with traffic.

## Consequences

- S01–S08 `-desc-tt` gold changed to `no_value`; no question text changed.
- Re-scoring v0 against the corrected bank lowers its descriptive accuracy (0.68 → 0.57): v0 could not
  express `NoValue`, so these questions count against it by construction. The tuning log states it.
- Adding a kind does not invalidate stored answers (ADR-0019).
