# Evaluation cost plan (full, internal)

Generated from `eval/budget/cost-data.toml` by `python -m eval.budget`; do not edit.
Every figure is a low-to-high range in USD. `measured` rests on a recorded run;
`proxy` is an estimate and names what it derives from. A run is one agent run;
tokens are per run.

## Capability levels

Levels carry no model names in the short version or the page; this plan names the
backing.
Prices are USD per million tokens.

| Level | In | Out | Backing | Policy |
|---|---|---|---|---|
| non-reasoning-low | 0.05 | 0.15 | manifest: google/gemma-3-12b-it | pending policy approval (approved for: input-parser) |
| non-reasoning-medium | 0.1 | 0.32 | manifest: meta-llama/llama-3.3-70b-instruct | pending policy approval |
| non-reasoning-high | 2 | 8 | assumption: OpenRouter list price of a frontier non-reasoning model, from memory; verify at openrouter.ai/models | pending policy approval |
| reasoning-low | 0.15 | 0.6 | manifest: deepseek/deepseek-v4.1-flash | approved |
| reasoning-medium | 1.1 | 4.4 | assumption: OpenRouter list price of a mid-tier reasoning model, from memory; verify at openrouter.ai/models | pending policy approval |
| reasoning-high | 3 | 15 | assumption: OpenRouter list price of a frontier reasoning model, from memory; verify at openrouter.ai/models | pending policy approval |

## Suites

### Input Parser (`input-parser`)

- Measures: Structured-output agreement of the Parser on the request bank: validity, intent, interventions, topology, metrics, ambiguity, arm structure, consistency across runs
- Threshold read: DoD 4.1 (E5.1); N4: intent agreement >= 95 % over 3 runs on held-out
- Varies: repetitions
- Per-suite contingency reserve: 25%
- Shape: fixed

#### minimum: $0.92 to $1.16 before contingency

Measured $0.92 to $0.92, proxy $0.00 to $0.25 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 255 x 2 | 1 x reasoning-low | 5,381-5,381 in, 827-827 out | measured: v8-dev (255 dev requests, 1 repetition), mean tokens | $0.66 to $0.66 |
| V1 | 255 x 2 | 1 x reasoning-low | 0-1,119 in, 0-173 out | proxy: assumed headroom over the measured mean (about +20 %: prompt growth, longer outputs on multi-arm requests); no run | $0.00 to $0.14 |
| V2 | 114 x 2 | 1 x reasoning-low | 5,118-5,118 in, 553-553 out | measured: v6-heldout (114 held-out requests x 3 repetitions), mean tokens | $0.25 to $0.25 |
| V2 | 114 x 2 | 1 x reasoning-low | 0-1,382 in, 0-447 out | proxy: assumed headroom over the measured mean (about +20 %: prompt growth, longer outputs on multi-arm requests); no run | $0.00 to $0.11 |

#### planned: $1.37 to $1.74 before contingency

Measured $1.37 to $1.37, proxy $0.00 to $0.37 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 255 x 3 | 1 x reasoning-low | 5,381-5,381 in, 827-827 out | measured: v8-dev (255 dev requests, 1 repetition), mean tokens | $1.00 to $1.00 |
| V1 | 255 x 3 | 1 x reasoning-low | 0-1,119 in, 0-173 out | proxy: assumed headroom over the measured mean (about +20 %: prompt growth, longer outputs on multi-arm requests); no run | $0.00 to $0.21 |
| V2 | 114 x 3 | 1 x reasoning-low | 5,118-5,118 in, 553-553 out | measured: v6-heldout (114 held-out requests x 3 repetitions), mean tokens | $0.38 to $0.38 |
| V2 | 114 x 3 | 1 x reasoning-low | 0-1,382 in, 0-447 out | proxy: assumed headroom over the measured mean (about +20 %: prompt growth, longer outputs on multi-arm requests); no run | $0.00 to $0.16 |

#### extended (pending policy approval: reasoning-medium): $4.36 to $8.28 before contingency

Measured $1.37 to $1.37, proxy $2.99 to $6.90 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 255 x 3 | 1 x reasoning-low | 5,381-5,381 in, 827-827 out | measured: v8-dev (255 dev requests, 1 repetition), mean tokens | $1.00 to $1.00 |
| V1 | 255 x 3 | 1 x reasoning-low | 0-1,119 in, 0-173 out | proxy: assumed headroom over the measured mean (about +20 %: prompt growth, longer outputs on multi-arm requests); no run | $0.00 to $0.21 |
| V2 | 114 x 3 | 1 x reasoning-low | 5,118-5,118 in, 553-553 out | measured: v6-heldout (114 held-out requests x 3 repetitions), mean tokens | $0.38 to $0.38 |
| V2 | 114 x 3 | 1 x reasoning-low | 0-1,382 in, 0-447 out | proxy: assumed headroom over the measured mean (about +20 %: prompt growth, longer outputs on multi-arm requests); no run | $0.00 to $0.16 |
| V2 | 114 x 3 | 2 x non-reasoning-low | 5,118-6,500 in, 553-1,000 out | proxy: v6-heldout tokens of the default model, assumed equal; a weaker-model parser run (v4-dev, 212 requests, $0.148; report in eval/parser_benchmark/reports/) shows a weaker model needs more output retries | $0.23 to $0.32 |
| V2 | 114 x 3 | 1 x reasoning-medium | 5,118-6,500 in, 553-2,500 out | proxy: v6-heldout tokens of the default model; output high allows a longer reasoning trace (assumption, no run) | $2.76 to $6.21 |

### Network Expert, forced and free abstention (EXP-01) (`exp-01`)

- Measures: Forced-mode accuracy across repetitions (N1) and whether the Expert abstains exactly where its forced answer would be wrong (N2), on the same 117 questions
- Threshold read: DoD 4.7 per-family accuracy (E4.2-E4.4); abstention_recall >= 70 % and abstention_false_requests <= 30 % (E4.5)
- Varies: repetitions
- Per-suite contingency reserve: 20%
- Shape: unfixed until its benchmark is designed

#### minimum: $5.11 to $6.93 before contingency

Measured $1.92 to $2.38, proxy $3.19 to $4.55 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | proxy: v2-e38-forced-1rep tokens (forced mode, 117 questions x 1 repetition) on an assumed V1 size of 39 questions (a third of the bank); no V1 run | $0.64 to $0.79 |
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $0.64 to $0.94 |
| V2 | 117 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition) | $1.92 to $2.38 |
| V2 | 117 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $1.92 to $2.82 |

#### planned: $7.03 to $9.52 before contingency

Measured $2.87 to $3.57, proxy $4.15 to $5.95 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | proxy: v2-e38-forced-1rep tokens (forced mode, 117 questions x 1 repetition) on an assumed V1 size of 39 questions (a third of the bank); no V1 run | $0.64 to $0.79 |
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $0.64 to $0.94 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition) | $2.87 to $3.57 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $2.87 to $4.22 |

#### extended (pending policy approval: reasoning-medium): $21.08 to $34.49 before contingency

Measured $2.87 to $3.57, proxy $18.21 to $30.92 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | proxy: v2-e38-forced-1rep tokens (forced mode, 117 questions x 1 repetition) on an assumed V1 size of 39 questions (a third of the bank); no V1 run | $0.64 to $0.79 |
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $0.64 to $0.94 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition) | $2.87 to $3.57 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $2.87 to $4.22 |
| V2 | 117 x 2 | 1 x reasoning-medium | 45,000-65,000 in, 2,400-8,000 out | proxy: v2-e38-forced-1rep tokens of the default model; output high allows a longer reasoning trace (assumption, no run) | $14.05 to $24.97 |

## Totals

Tier per suite: `planned` (the default selection). The $30 reference
is a combined figure for V1 and V2 together; the plan defines no per-pass cap, so the
excess is stated for the combined total only.

| | Low to high |
|---|---|
| Total without contingency | $8.40 to $11.27 |
| Per-suite reserve | $1.75 to $2.34 |
| Global reserve (10% of cost plus per-suite reserve) | $1.01 to $1.36 |
| Total with contingency | $11.16 to $14.97 |
| V1 without contingency | $2.27 to $2.94 |
| V1 with contingency | $3.06 to $3.94 |
| V2 without contingency | $6.13 to $8.33 |
| V2 with contingency | $8.11 to $11.03 |

Share of the total without contingency that rests on a run or on an estimate:

| Basis | Low to high | Share |
|---|---|---|
| measured | $4.25 to $4.94 | 51% of the low, 44% of the high |
| proxy | $4.15 to $6.32 | 49% of the low, 56% of the high |

The plan stays within the $30 reference.

| Suite | Tier | Without contingency | Per-suite reserve | Measured share | Pending policy approval |
|---|---|---|---|---|---|
| input-parser | planned | $1.37 to $1.74 | $0.34 to $0.44 | 100% of the low, 79% of the high | no |
| exp-01 | planned | $7.03 to $9.52 | $1.41 to $1.90 | 41% of the low, 37% of the high | no |
