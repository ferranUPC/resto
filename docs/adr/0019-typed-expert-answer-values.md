# ADR-0019: `ExpertAnswer` carries typed `values`; prose is the justification

- Status: Accepted
- Date: 2026-09-17
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.3
  (`ExpertAnswer`), §4.7; [ADR-0011](0011-network-expert-knowledge-model.md),
  [ADR-0018](0018-network-expert-tools-and-evidence-refs.md);
  [`evaluating-resto.md`](../evaluating-resto.md) §4.3–§4.4; work-plan E3.3

## Context

`ExpertAnswer.answer` was free prose; only its metadata (`basis`, `confidence`, `evidence`,
`needs_simulation`, `proposed_experiment`) was typed. The §4.7 metrics (exact match, Jaccard, direction,
magnitude band) need the answer's content as data. Extracting it from prose is fragile — in the first
real-model run (2026-09-17) an answer about "edges above 3.5 % occupancy" also named three edges that were
below it — and an LLM extractor would add a paid call per answer plus its own validation against a human.

## Decision

- `ExpertAnswer` gains `values: tuple[AnswerValue, ...]`, required unless the Expert abstains
  (`needs_simulation`). `answer` stays as the prose justification; when the two disagree, `values` is
  authoritative.
- `AnswerValue` (`domain/value_objects/answer_value.py`) is a discriminated union, deliberately small:
  - `Edges(edge_ids, ranked)` — a set, or a ranking when `ranked`; empty is a valid answer.
  - `Quantity(measure, value, edge_id)` — one number.
  - `Change(measure, direction, relative_change_pct?, edge_id)` — direction increase / decrease /
    unchanged relative to a reference; an optional percentage whose sign cannot contradict it.
- `Measure` is a closed enum. Its unit is fixed per measure (so an answer cannot switch units), and it is
  either per edge (`edge_id` required) or network-wide (`edge_id` forbidden).
- `ask_expert` rejects a value naming an edge that is not on the network.

## Consequences

- Scoring is deterministic: no extractor, no judge (`evaluating-resto.md` §4.4).
- Hallucinated edge ids in the answer are rejected at promotion; they no longer pass unseen.
- `submit_output`'s schema grows by about 1,500 characters, resent on every agent step — negligible next to
  the edgedata payloads that dominate input tokens.
- A question these three kinds cannot express can only be answered in prose and scores as wrong. New kinds
  (e.g. `Route`, `ScenarioRef`, `YesNo`) are added when a benchmark needs them; adding a variant does not
  invalidate stored answers, removing one does.
- The model must pick the right kind; validation failures cost agent steps. Measured on the real model
  before the metrics harness is built on it.

## Alternatives considered

- **Regex extraction from prose.** Rejected: cannot tell an edge that answers the question from one named
  for contrast.
- **LLM extraction or LLM-as-judge.** Rejected for now: one extra paid call per answer, and its agreement
  with a human would have to be measured first.
- **Six kinds from the start (`Route`, `ScenarioRef`, `YesNo` too).** Rejected: no question in the bank
  needs them, and every extra kind is one more choice the model can get wrong.
