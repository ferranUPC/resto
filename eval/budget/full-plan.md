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

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 255 x 2 | 1 x reasoning-low | 5,381-6,500 in, 827-1,000 out | measured: v8-dev (255 dev requests, 1 repetition) | $0.66 to $0.80 |
| V2 | 114 x 2 | 1 x reasoning-low | 5,118-6,500 in, 553-1,000 out | measured: v6-heldout (114 held-out requests x 3 repetitions); output high from v8-dev | $0.25 to $0.36 |

#### planned: $1.37 to $1.74 before contingency

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 255 x 3 | 1 x reasoning-low | 5,381-6,500 in, 827-1,000 out | measured: v8-dev (255 dev requests, 1 repetition) | $1.00 to $1.20 |
| V2 | 114 x 3 | 1 x reasoning-low | 5,118-6,500 in, 553-1,000 out | measured: v6-heldout (114 held-out requests x 3 repetitions); output high from v8-dev | $0.38 to $0.54 |

#### extended (pending policy approval: reasoning-medium): $4.36 to $8.28 before contingency

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 255 x 3 | 1 x reasoning-low | 5,381-6,500 in, 827-1,000 out | measured: v8-dev (255 dev requests, 1 repetition) | $1.00 to $1.20 |
| V2 | 114 x 3 | 1 x reasoning-low | 5,118-6,500 in, 553-1,000 out | measured: v6-heldout (114 held-out requests x 3 repetitions); output high from v8-dev | $0.38 to $0.54 |
| V2 | 114 x 3 | 2 x non-reasoning-low | 5,118-6,500 in, 553-1,000 out | proxy: v6-heldout tokens of the default model, assumed equal; ministral-v4-dev ($0.148, 212 requests) shows a weaker model needs more output retries | $0.23 to $0.32 |
| V2 | 114 x 3 | 1 x reasoning-medium | 5,118-6,500 in, 553-2,500 out | proxy: v6-heldout tokens of the default model; output high allows a longer reasoning trace (assumption, no run) | $2.76 to $6.21 |

### Network Expert, forced and free abstention (EXP-01) (`exp-01`)

- Measures: Forced-mode accuracy across repetitions (N1) and whether the Expert abstains exactly where its forced answer would be wrong (N2), on the same 117 questions
- Threshold read: DoD 4.7 per-family accuracy (E4.2-E4.4); abstention_recall >= 70 % and abstention_false_requests <= 30 % (E4.5)
- Varies: repetitions
- Per-suite contingency reserve: 20%
- Shape: unfixed until its benchmark is designed

#### minimum: $5.11 to $6.93 before contingency

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition); V1 size is an assumption | $0.64 to $0.79 |
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $0.64 to $0.94 |
| V2 | 117 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition) | $1.92 to $2.38 |
| V2 | 117 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $1.92 to $2.82 |

#### planned: $7.03 to $9.52 before contingency

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition); V1 size is an assumption | $0.64 to $0.79 |
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $0.64 to $0.94 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition) | $2.87 to $3.57 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $2.87 to $4.22 |

#### extended (pending policy approval: reasoning-medium): $21.08 to $34.49 before contingency

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition); V1 size is an assumption | $0.64 to $0.79 |
| V1 | 39 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $0.64 to $0.94 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-55,000 in, 2,400-3,200 out | measured: v2-e38-forced-1rep (forced mode, 117 questions x 1 repetition) | $2.87 to $3.57 |
| V2 | 117 x 3 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens assumed for free mode; no full free-mode run exists | $2.87 to $4.22 |
| V2 | 117 x 2 | 1 x reasoning-medium | 45,000-65,000 in, 2,400-8,000 out | proxy: v2-e38-forced-1rep tokens of the default model; output high allows a longer reasoning trace (assumption, no run) | $14.05 to $24.97 |

## Totals

Tier per suite: `planned` (the default selection). Reference cap for V1 and V2 together: $30.

| | Low to high |
|---|---|
| Total without contingency | $8.40 to $11.27 |
| Per-suite reserve | $1.75 to $2.34 (global 10% on top: $1.01 to $1.36) |
| Total with contingency | $11.16 to $14.97 |
| V1 with contingency | $3.06 to $3.94 |
| V2 with contingency | $8.11 to $11.03 |

The plan stays within the $30 reference.

| Suite | Tier | Pending policy approval |
|---|---|---|
| input-parser | planned | no |
| exp-01 | planned | no |
