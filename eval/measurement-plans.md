# Measurement runs and validation passes

- Status: living document, split from `docs/evaluating-resto.md` §7 on 2026-10-06
- Scope: which measurement runs are planned, with which model and at what cost. The procedures are in
  [`README.md`](README.md); the rules for when a real call may run are in
  [`docs/llm-cost-policy.md`](../docs/llm-cost-policy.md). Section numbers cited below (§4.x) are those of
  [`README.md`](README.md); decisions are in [`decisions-log.md`](decisions-log.md).

---

Per `docs/llm-cost-policy.md`, runs are split by purpose. A **development run** (smoke, tuning, a
1-repetition check) runs now with its cost stated and is not logged here. A **measurement run**
produces the figure a DoD threshold reads; it waits for one of two passes dated in the work plan:

- **Validation 1** (mid-December): reduced checkpoints of what is built by then, on dev splits only, to
  see how things stand while there is still time to fix them. Its figures are interim; they turn no task
  ✅. If funding is confirmed by then, frozen modules may be measured at definitive size here.
- **Validation 2** (before the results chapter, E10.5): every definitive measurement, each suite once. A
  threshold missed here is reported as a result, not re-tuned.

Both passes together are capped at $30 unless funding arrives; under the cap a suite shrinks in scale
(inputs × repetitions × models, never below the 2 repetitions a std or an agreement metric needs), it is
not dropped. Two layers, kept separate:

- **Evaluation needs** — *what* still needs measuring against a real model. Add a row whenever a DoD
  threshold (`README.md` §4, or `docs/tfm-architecture-and-dod.md`) or an open question ([`decisions-log.md`](decisions-log.md)) can only be
  answered by a measurement run. A need is not itself a thing to run.
- **Measurement suites** — concrete runs, each covering one or more needs; needs that share a pass
  are merged into one suite rather than paid for twice (see EXP-01). A suite's final shape (inputs,
  repetitions, models) is fixed when its benchmark is designed, not before. This table moves to the
  evaluation budget document for supervisors once that is written (work plan task).

### 7.1 Evaluation needs

| ID | Need | Drives | Status |
|---|---|---|---|
| N1 | Forced-mode accuracy across repetitions (mean ± std, not a single pass/fail) on the full 117-question bank | E4.2, E4.3, E4.4 (per-family Done thresholds) and E4.7 (DoD report, §4.7) | A 1-repetition sweep (`v1-forced-1rep`) exists and meets every per-family threshold; the DoD's 3-repetition bar is unmet |
| N2 | Does the Expert abstain (free mode) exactly where its forced-mode answer would have been wrong, at the DoD's recall/false-request thresholds? | E4.5 (`abstention_recall` ≥ 70 %, `abstention_false_requests` ≤ 30 %, §4.5) | Harness built; the 4-question smoke (`e45-smoke`, $0.056) validated it end to end but gave no signal — zero forced-incorrect and zero abstentions in that tiny sample |
| N3 *(parked)* | Whether 3 repetitions is actually the right count for N1/N2, or fewer/more would materially change the read | Methodology question, not a DoD threshold | Raised 2026-09-22 as a side thought, not yet scoped as something worth spending on — revisit if N1/N2's results look unstable enough to justify it |
| N4 | Input Parser on held-out, second use: `intent` agreement ≥ 95 % over 3 runs with every other §4.1 threshold held | E5.1 (the first held-out pass, `v6-heldout`, missed only `intent` agreement: 93.9 %) | Validation 2, with the prompt frozen; labelled a second use and reported next to the first |

Add a row here first, before adding or changing anything in Experiment plans, whenever a new DoD threshold or
open question turns out to need a real run.

### 7.2 Experiment plans

| ID | Name | Covers | Scope | Model | Estimated cost | Notes |
|---|---|---|---|---|---|---|
| EXP-01 | `forced3-free-abstention` | N1 + N2 | 117 questions × 3 repetitions forced + free mode paired on the same questions, free-mode repetitions TBD | `deepseek/deepseek-v4.1-flash` | ≈ $2.9 (forced, fixed) + ≈ $1.0/repetition (free) → **≈ $3.9** at 1 free repetition or **≈ $5.8** at 3 (§4.2) | Validation 2 (a reduced checkpoint in Validation 1), after the ADR-0028 migration rebuilds the question bank. N1 and N2 both need a forced-mode sweep of the same questions; running it once at 3 repetitions serves N1 directly and *is* the forced half of N2's abstention pairing, so paying for a second, separate forced-mode pass would be redundant — merged for that reason. Free-mode repetition count (1 vs 3) is an open choice: 3 matches the forced count and gives mean ± std on N2's metrics too; 1 is cheaper with a single-point estimate. `--mode both` in `eval/expert_benchmark/run.py` runs both legs into the same `runs/<name>.jsonl`; use `--name forced3-free-abstention` to keep the file matching this row. |
