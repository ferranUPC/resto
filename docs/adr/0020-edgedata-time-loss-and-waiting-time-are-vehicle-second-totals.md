# ADR-0020: `time_loss` and `waiting_time` are vehicle-second totals — summed, not averaged

- Status: Accepted — amends [`DATABASE_MCP_CONTRACT.md`](../DATABASE_MCP_CONTRACT.md) v1.0 §5.4
- Date: 2026-09-17
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §4.7, §4.9;
  [ADR-0019](0019-typed-expert-answer-values.md); [`evaluating-resto.md`](../evaluating-resto.md) §4.1

## Context

Contract v1.0 §5.4 grouped `waiting_time` and `time_loss` with the rates and means (`density`,
`occupancy`, `speed`, `travel_time`) and averaged them across intervals weighted by `sampled_seconds`.

Checked against DEV-NET edgedata while designing Expert tools, SUMO writes both as **totals over every
vehicle on the edge in the interval**. On `B2C2`, `[0, 300)`, S00 seed 1: 15 vehicles, travel time
21.95 s against 13.36 s at free flow, so ≈ 8.6 s lost per vehicle and ≈ 129 s in total. The edgedata
says `time_loss = 129.85`. Five of six edges checked matched within a few percent.

Averaging totals under-reports them on any window spanning more than one interval. For `B2C2`,
`query_edgedata` returned 140 for `[0, 600)`, where the total is ≈ 281, and 178 for the whole hour,
where it is ≈ 1,855.

The same misreading reached the question bank. Its diagnostic gold ranked edges by
`time_loss × entered` as "delay × flow", counting the flow twice.

## Decision

- `waiting_time` and `time_loss` are **vehicle-second totals**. In `query_edgedata` they are summed over
  the clipped intervals, prorated by the overlapping fraction like counters, but not rounded.
- `Measure.TIME_LOSS` and `Measure.WAITING_TIME` carry the unit `veh·s`. The Expert prompt and tool
  docstrings state that they are totals, and that a per-vehicle value divides by `entered`.
- The question bank ranks diagnostic bottlenecks by total `time_loss`. Counterfactual questions say
  "total delay (time lost by all vehicles)", matching the `time_loss` their gold uses.

## Consequences

- Any window aligned to a single edgedata interval returns the same values as before; windows spanning
  several intervals, and `window = null`, now return real totals.
- Regenerating the question bank changed 15 of 20 diagnostic gold answers: 14 from the ranking fix, 1
  (S15, window `[500, 700)` over two intervals) from the aggregation fix. No descriptive or
  counterfactual gold answer changed.
- A third-party DatabaseMCP backend built against v1.0 must change the same two measures; the conformance
  suite now checks it.

## Alternatives considered

- **Keep them as means and document per-vehicle semantics.** Rejected: that is not what SUMO writes, and
  a per-vehicle mean is undefined on an edge no vehicle entered.
- **Divide by `entered` in the contract and return per-vehicle delay.** Rejected: the contract returns
  SUMO's measures, and a derived per-vehicle value belongs in the aggregation tools planned for the
  Expert.
