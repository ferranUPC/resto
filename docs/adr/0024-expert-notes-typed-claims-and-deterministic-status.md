# ADR-0024: `ExpertNote` carries typed claims; code confirms or refutes them against `Kpis`

- Status: Accepted — extends ADR-0011's `ExpertNote` and ADR-0019's `AnswerValue` to notes
- Date: 2026-09-22
- Architecture reference: [`tfm-architecture-and-dod.md`](../tfm-architecture-and-dod.md) §2.2, §2.3
  (`ExpertNote`), §2.4, §4.7; [ADR-0011](0011-network-expert-knowledge-model.md),
  [ADR-0018](0018-network-expert-tools-and-evidence-refs.md),
  [ADR-0019](0019-typed-expert-answer-values.md);
  [`evaluating-resto.md`](../evaluating-resto.md) §4.8; work-plan E4.6

## Context

ADR-0011 says a note's `status` changes only because of a later `SimulationResult`, and only code
decides it. The note was prose only (`text`), so there was nothing code could compare with a result
without an LLM reading the prose, which would put the verdict back in the model's hands. The DoD's
knowledge-hygiene bullet also asks for the status to be updated "in 100 % of cases" (v0.2 §4.7).

Separately, writing a note after an experiment needed its own agent call; the question was whether it
gets tools of its own.

## Decision

- `ExpertNoteDraft` and `ExpertNote` gain `values: tuple[AnswerValue, ...] = ()`, the same union as
  `ExpertAnswer.values` (ADR-0019). Empty is valid and expected for most notes.
- The note-writing call (`run_expert_note`) gets **no tools**: its input is the finished `ExpertRound`
  (question + answer). `write_note` checks its evidence against the **same** `EvidenceLedger` the round
  was promoted with, so a note can cite only what the round already observed. One extra call, no new
  queries.
- `write_note` sets `note_id` (UUID), `provenance` (`simulation` when the note is about a scenario,
  `opinion` otherwise) and `status = unverified`.
- `update_note_status(note, result)` is deterministic code. First version, deliberately narrow: only
  network-wide `Quantity` claims (`mean_delay`, `mean_travel_time`, `teleports`, `departed`,
  `arrived`) are checked, against `result.kpis`, with the benchmark's ±5 % tolerance
  (`domain/services/comparison.py`, shared with `eval/expert_benchmark/scoring.py`). All claims within
  tolerance → `confirmed`; any outside → `refuted`. The result must be for the note's `scenario_id`.
  A note that is already resolved, has no checkable claim, or meets a result without `kpis` is left
  `unverified` and the function returns `None`.

## Consequences

- "100 % of cases" is read as 100 % of *applicable* cases: notes with a checkable claim. Per-edge
  `Quantity`, `Edges` and `Change` claims stay `unverified` for now. A `Change` needs its own
  baseline result and a per-edge value needs an edgedata query over a window the note does not record;
  both are possible later extensions, not guessed now.
- The in-memory `NoteRepository` (`adapters/persistence/memory.py`) follows the same filter and ranking
  rules as the SQLite one, for tests and the hygiene probes.
- Adding the field keeps stored notes valid (default `()`); the JSON schemas are regenerated.
- Calling `write_note`/`update_note_status` at the right moment of a `Study` is the Executor's job
  (ADR-0023, E5.10), not E4.6's.
