# ADR-0029: The diagnostic "why" is a typed cause per bottleneck edge

- Status: Accepted
- Date: 2026-09-25
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §4.7
  (diagnostic "why" rubric ≥ 70 %), §8 (open question: how the "why" is graded);
  [ADR-0019](0019-typed-expert-answer-values.md); `evaluating-resto.md` §4.4, §6; work-plan E4.3

## Context

The DoD asks for a diagnostic "why" rubric ≥ 70 %, and nothing grades it. v0.2 of the architecture doc
defined the rubric as three buckets (merge / signal / demand). The question bank computes a gold `reason`
from the top-1 edge only, by membership in two hand-written DEV-NET edge sets. That rule is wrong in two
ways. The `signal` set holds only the four eastbound row-2 edges, although each of the five traffic lights
controls every approach, so 6 of the 20 diagnostic questions label a signalised approach `demand`. And it
never looks at the scenario's intervention: S03 closes a lane of B0C0 and its worst edge, B1B0, feeds it
directly, yet the gold says `demand`. Graded as it stands, it would mark correct answers wrong. On the
top-1 edge alone the metric is also easy to game: "`intervention` if the scenario has one, else `signal`"
scores 16/20.

## Decision

1. **The "why" is graded as a categorical cause, not as free text.** No rubric by hand and no LLM judge
   (`evaluating-resto.md` principle 5, "structured before judged"). The Expert's prose stays and is not
   graded.
2. **One cause per edge, for each of the three bottleneck edges.** The question reads "Which three edges
   form the main bottleneck … and why is each of them congested?". The Expert answers with a typed value
   holding one (edge, cause) pair per edge, next to its top-3 edges (ADR-0019).
3. **Five causes, applied in this order, first match wins.**
   1. `intervention`: the edge is an intervention's target edge, ends at the node where the target edge
      starts (feeds it directly), or ends at the target traffic light.
   2. `merge`: the edge is a known lane drop of the network.
   3. `spillback`: the edge ends where a higher-ranked edge of the same top-3 starts (its queue comes from
      downstream).
   4. `signal`: the edge ends at a traffic-light junction.
   5. `demand`: none of the above.
   A `demand_scale` intervention has no target, so it never yields `intervention`: the cause describes
   the local mechanism, and more demand only makes it worse.
4. **Scored on the edges both answers share.** Cause accuracy is computed over the edges in both the
   Expert's top-3 and the gold's. An edge that is missing is already penalised by the Jaccard. The DoD's
   ≥ 70 % reads on this per-edge accuracy.

## Consequences

- On DEV-NET the gold becomes 21 `intervention`, 33 `signal`, 6 `spillback`, and no `merge` or `demand`
  (the merge edge only tops S05, where the closure of C0D0 takes precedence). Both stay in the set
  because REAL-NET can produce them.
- The question bank is rebuilt: new diagnostic text and a per-edge gold cause. The diagnostic score from
  sweeps before this ADR does not carry a cause, so Expert v3 (prompt + typed value) needs a new
  diagnostic sweep.
- A new answer value kind in the domain, and a scorer metric reported next to the Jaccard.
- The answer carries more typed output. This adds pressure on the diagnostic budget stops (output cut at
  the token limit), which E4.3 already has to watch.

## Alternatives considered

- **Human rubric on the free-text "why".** Rejected: it costs the maintainer's time on every pass (≈ 60
  answers in EXP-01) for what the DoD itself defined as a bucket.
- **LLM-as-judge with agreement measured against a human.** Rejected: it needs a judge model approved
  under the cost policy, and it grades prose where a typed value can exist.
- **Three buckets with the `signal` set fixed.** Rejected: 18 of 20 top-1 edges end at a signal or the
  merge, so answering "signal" would nearly always pass.
- **Multi-label gold (correct if the cause is any that applies).** Rejected: too lenient for the same
  reason.
- **Only the top-1 edge's cause.** Rejected: 20 labels, easy to game, and not what the question asks.
