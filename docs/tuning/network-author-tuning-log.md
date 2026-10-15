# Network Author tuning log

- Status: living document, started 2026-10-15
- Purpose: record each real run of the Network Author with the prompt version it used, its cost and
  the result. Same role as the [Composer's log](composer-tuning-log.md).
- Related: E6.1 ticket 08 (`.scratch/e6-1-network-author-minimal/issues/08-real-path-golden-path-and-dev-run.md`).

Running total spent: **about $0.005**.

## 2026-10-15, Network Author `v1`, first manual run

- **Script:** `scripts/manual_network_author_run.py --run` on branch `e6-1-network-author-minimal`.
  Not part of the suite.
- **Model and budget:** `deepseek/deepseek-v4.1-flash`, 40 steps, 2048 output tokens, 900 s, 3 rounds.
- **Estimate before the run:** at most $0.109. Development run, below the $1 limit in
  `docs/llm-cost-policy.md`. The maintainer approved it before it started.
- **Request:** `"a 5 by 5 grid"`, with Nominatim and Overpass switched off.
- **Result:** 5 tool calls (`find_network`, `generate_grid`, `sanity_check`, `probe_run`,
  `submit_output`), stop reason `output`, 39,260 input and 944 output tokens, cost $0.0048
  (`usage.cost_usd`). The draft had a `GridNetwork(5, 5, 100 m)` recipe, a sanity report of
  1.0 / 0 / true, a probe report with 0 teleports and 0 collisions, and an empty `unresolved[]`.
  `NetworkPromoter.promote` replayed the recipe and got the same `content_hash` (`d8e23de2...`).
- **Reading:** the wiring works from the model to a promoted `Network`. No repair round was needed,
  so this run does not test the repair loop, derivation or `NeedsUser`. Those wait for E6.2.
