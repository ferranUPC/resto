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

### Scenario Builder (`scenario-builder`)

- Measures: Builder bank: does the Builder turn a request into a valid stored scenario and compare it to the gold scenario, per case
- Threshold read: DoD E2.7 (Builder bank, 3 repetitions)
- Varies: repetitions
- Per-suite contingency reserve: 20%
- Shape: unfixed until its benchmark is designed

#### minimum: $0.34 to $0.72 before contingency

Measured $0.00 to $0.00, proxy $0.34 to $0.72 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 10 x 2 | 1 x reasoning-low | 20,000-40,000 in, 2,000-5,000 out | proxy: work plan figure for this suite ($0.5-1.2 at 3 repetitions); tokens are an assumed tool-agent run, no run exists | $0.08 to $0.18 |
| V2 | 30 x 2 | 1 x reasoning-low | 20,000-40,000 in, 2,000-5,000 out | proxy: work plan figure for this suite ($0.5-1.2 at 3 repetitions); tokens are an assumed tool-agent run, no run exists | $0.25 to $0.54 |

#### planned: $0.46 to $0.99 before contingency

Measured $0.00 to $0.00, proxy $0.46 to $0.99 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 10 x 2 | 1 x reasoning-low | 20,000-40,000 in, 2,000-5,000 out | proxy: work plan figure for this suite ($0.5-1.2 at 3 repetitions); tokens are an assumed tool-agent run, no run exists | $0.08 to $0.18 |
| V2 | 30 x 3 | 1 x reasoning-low | 20,000-40,000 in, 2,000-5,000 out | proxy: work plan figure for this suite ($0.5-1.2 at 3 repetitions); tokens are an assumed tool-agent run, no run exists | $0.38 to $0.81 |

#### extended (pending policy approval: reasoning-medium): $2.31 to $7.46 before contingency

Measured $0.00 to $0.00, proxy $2.31 to $7.46 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V1 | 10 x 2 | 1 x reasoning-low | 20,000-40,000 in, 2,000-5,000 out | proxy: work plan figure for this suite ($0.5-1.2 at 3 repetitions); tokens are an assumed tool-agent run, no run exists | $0.08 to $0.18 |
| V2 | 30 x 3 | 1 x reasoning-low | 20,000-40,000 in, 2,000-5,000 out | proxy: work plan figure for this suite ($0.5-1.2 at 3 repetitions); tokens are an assumed tool-agent run, no run exists | $0.38 to $0.81 |
| V2 | 30 x 2 | 1 x reasoning-medium | 20,000-50,000 in, 2,000-12,000 out | proxy: same assumed run; output high allows a longer reasoning trace (assumption) | $1.85 to $6.47 |

### Network Author (`network-author`)

- Measures: GEN-LOCATIONS generation and derivation of edited networks: validity and match to the requested change, each generation seeded
- Threshold read: DoD E6.2 (GEN-LOCATIONS and derivation, 3 repetitions)
- Varies: seeds
- Per-suite contingency reserve: 30%
- Shape: unfixed until its benchmark is designed

#### minimum: $0.50 to $1.24 before contingency

Measured $0.00 to $0.00, proxy $0.50 to $1.24 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 30 x 2 | 1 x reasoning-low | 40,000-90,000 in, 4,000-12,000 out | proxy: work plan figure for this suite ($0.6-3 at 3 repetitions); tokens are an assumed long tool-agent run, no run exists | $0.50 to $1.24 |

#### planned: $0.76 to $1.86 before contingency

Measured $0.00 to $0.00, proxy $0.76 to $1.86 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 30 x 3 | 1 x reasoning-low | 40,000-90,000 in, 4,000-12,000 out | proxy: work plan figure for this suite ($0.6-3 at 3 repetitions); tokens are an assumed long tool-agent run, no run exists | $0.76 to $1.86 |

#### extended (pending policy approval: reasoning-medium): $4.96 to $14.98 before contingency

Measured $0.00 to $0.00, proxy $4.96 to $14.98 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 30 x 5 | 1 x reasoning-low | 40,000-90,000 in, 4,000-12,000 out | proxy: work plan figure for this suite ($0.6-3 at 3 repetitions); tokens are an assumed long tool-agent run, no run exists | $1.26 to $3.10 |
| V2 | 30 x 2 | 1 x reasoning-medium | 40,000-100,000 in, 4,000-20,000 out | proxy: same assumed run; output high allows a longer reasoning trace (assumption) | $3.70 to $11.88 |

### Demand Generator (`demand-generator`)

- Measures: Demand calibration: does generated demand reproduce the target flows within tolerance, each calibration run simulated with its own seed
- Threshold read: DoD E7.4 (demand calibration)
- Varies: seeds
- Per-suite contingency reserve: 25%
- Shape: unfixed until its benchmark is designed

#### minimum: $0.13 to $0.36 before contingency

Measured $0.00 to $0.00, proxy $0.13 to $0.36 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 20 x 2 | 1 x reasoning-low | 15,000-40,000 in, 1,500-5,000 out | proxy: work plan figure for this suite ($0.2-1); tokens are an assumed calibration run, no run exists | $0.13 to $0.36 |

#### planned: $0.19 to $0.54 before contingency

Measured $0.00 to $0.00, proxy $0.19 to $0.54 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 20 x 3 | 1 x reasoning-low | 15,000-40,000 in, 1,500-5,000 out | proxy: work plan figure for this suite ($0.2-1); tokens are an assumed calibration run, no run exists | $0.19 to $0.54 |

#### extended (pending policy approval: reasoning-medium): $1.24 to $4.86 before contingency

Measured $0.00 to $0.00, proxy $1.24 to $4.86 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 20 x 5 | 1 x reasoning-low | 15,000-40,000 in, 1,500-5,000 out | proxy: work plan figure for this suite ($0.2-1); tokens are an assumed calibration run, no run exists | $0.32 to $0.90 |
| V2 | 20 x 2 | 1 x reasoning-medium | 15,000-50,000 in, 1,500-10,000 out | proxy: same assumed run; output high allows a longer reasoning trace (assumption) | $0.92 to $3.96 |

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

### Network Expert on REAL-NET (`expert-real-net`)

- Measures: Forced-mode accuracy of the Expert on the frozen real district: descriptive, Jaccard and direction metrics
- Threshold read: DoD 4.7 REAL-NET (descriptive >= 85 %, Jaccard >= 0.5, direction >= 65 %; E8.5)
- Varies: repetitions
- Per-suite contingency reserve: 20%
- Shape: unfixed until its benchmark is designed

#### minimum: $0.66 to $0.96 before contingency

Measured $0.00 to $0.00, proxy $0.66 to $0.96 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 40 x 2 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens (forced mode, 117 questions x 1 repetition) assumed for this suite on a different network; no run on it | $0.66 to $0.96 |

#### planned: $0.98 to $1.44 before contingency

Measured $0.00 to $0.00, proxy $0.98 to $1.44 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 40 x 3 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens (forced mode, 117 questions x 1 repetition) assumed for this suite on a different network; no run on it | $0.98 to $1.44 |

#### extended (pending policy approval: reasoning-medium): $5.79 to $9.98 before contingency

Measured $0.00 to $0.00, proxy $5.79 to $9.98 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 40 x 3 | 1 x reasoning-low | 45,000-65,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens (forced mode, 117 questions x 1 repetition) assumed for this suite on a different network; no run on it | $0.98 to $1.44 |
| V2 | 40 x 2 | 1 x reasoning-medium | 45,000-65,000 in, 2,400-8,000 out | proxy: v2-e38-forced-1rep tokens of the default level; output high allows a longer reasoning trace (assumption) | $4.80 to $8.54 |

### Network Expert learning effect (`expert-learning-effect`)

- Measures: Does accuracy rise as the Expert holds more prior experiences (0, 5, 15, 25): the learning-effect curve
- Threshold read: DoD E4.9 (learning-effect curve)
- Varies: seeds
- Per-suite contingency reserve: 30%
- Shape: unfixed until its benchmark is designed

#### minimum: $2.15 to $3.07 before contingency

Measured $0.00 to $0.00, proxy $2.15 to $3.07 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 120 x 2 | 1 x reasoning-low | 50,000-70,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens plus an assumed memory of earlier experiences in the prompt; no run | $2.15 to $3.07 |

#### planned: $3.22 to $4.60 before contingency

Measured $0.00 to $0.00, proxy $3.22 to $4.60 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 120 x 3 | 1 x reasoning-low | 50,000-70,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens plus an assumed memory of earlier experiences in the prompt; no run | $3.22 to $4.60 |

#### extended: $5.36 to $7.67 before contingency

Measured $0.00 to $0.00, proxy $5.36 to $7.67 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 120 x 5 | 1 x reasoning-low | 50,000-70,000 in, 2,400-3,800 out | proxy: v2-e38-forced-1rep tokens plus an assumed memory of earlier experiences in the prompt; no run | $5.36 to $7.67 |

### Output Composer (`output-composer`)

- Measures: Hallucination review of composed text against the Expert's answer (no invented or contradicted claim), plus what the golden-path rubric already covers
- Threshold read: DoD E5.7 rubric (Composer faithfulness) and E9.5
- Varies: repetitions
- Per-suite contingency reserve: 15%
- Shape: unfixed until its benchmark is designed

#### minimum: $0.09 to $0.25 before contingency

Reviewer effort (separate from model cost, not in USD): 3 to 5 hours.

Measured $0.00 to $0.00, proxy $0.09 to $0.25 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 60 x 2 | 1 x reasoning-low | 3,000-8,000 in, 500-1,500 out | proxy: assumed small composer run (answer text from the Expert's answer); no run exists | $0.09 to $0.25 |

#### planned (pending policy approval: non-reasoning-low): $0.22 to $0.60 before contingency

Reviewer effort (separate from model cost, not in USD): 5 to 9 hours.

Measured $0.00 to $0.00, proxy $0.22 to $0.60 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 60 x 3 | 1 x reasoning-low | 3,000-8,000 in, 500-1,500 out | proxy: assumed small composer run (answer text from the Expert's answer); no run exists | $0.14 to $0.38 |
| V2 | 60 x 3 | 2 x non-reasoning-low | 3,000-8,000 in, 500-1,500 out | proxy: same assumed run on two cheaper non-reasoning models (assumption) | $0.08 to $0.23 |

#### extended (pending policy approval: non-reasoning-low, non-reasoning-medium, reasoning-medium): $1.04 to $2.91 before contingency

Reviewer effort (separate from model cost, not in USD): 9 to 16 hours.

Measured $0.00 to $0.00, proxy $1.04 to $2.91 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 60 x 3 | 1 x reasoning-low | 3,000-8,000 in, 500-1,500 out | proxy: assumed small composer run (answer text from the Expert's answer); no run exists | $0.14 to $0.38 |
| V2 | 60 x 3 | 2 x non-reasoning-low, 2 x non-reasoning-medium | 3,000-8,000 in, 500-1,500 out | proxy: same assumed run on four cheaper non-reasoning models (assumption) | $0.25 to $0.69 |
| V2 | 60 x 2 | 1 x reasoning-medium | 3,000-8,000 in, 500-1,500 out | proxy: same assumed run, longer reasoning trace (assumption) | $0.66 to $1.85 |

### Golden-path integration (`golden-path`)

- Measures: The 11 golden paths end to end through the CLI: pass/fail and the rubric over the composed answer
- Threshold read: DoD E9.4 and E9.5 (golden paths), E5.7 rubric
- Varies: repetitions
- Per-suite contingency reserve: 25%
- Shape: unfixed until its benchmark is designed

#### minimum: $0.63 to $1.72 before contingency

Measured $0.00 to $0.00, proxy $0.63 to $1.72 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 11 x 2 | 1 x reasoning-low | 150,000-400,000 in, 10,000-30,000 out | proxy: work plan figure for this suite ($1-3 at 11 paths x 3 repetitions); tokens are an assumed full-pipeline run, no run exists | $0.63 to $1.72 |

#### planned: $0.94 to $2.57 before contingency

Measured $0.00 to $0.00, proxy $0.94 to $2.57 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 11 x 3 | 1 x reasoning-low | 150,000-400,000 in, 10,000-30,000 out | proxy: work plan figure for this suite ($1-3 at 11 paths x 3 repetitions); tokens are an assumed full-pipeline run, no run exists | $0.94 to $2.57 |

#### extended: $1.57 to $4.29 before contingency

Measured $0.00 to $0.00, proxy $1.57 to $4.29 (before contingency).

| Pass | Inputs x reps | Models | Tokens per run | Basis | Cost |
|---|---|---|---|---|---|
| V2 | 11 x 5 | 1 x reasoning-low | 150,000-400,000 in, 10,000-30,000 out | proxy: work plan figure for this suite ($1-3 at 11 paths x 3 repetitions); tokens are an assumed full-pipeline run, no run exists | $1.57 to $4.29 |

### Plan bank routing (`plan-bank-routing`)

Excluded from every total: removed by r13 (the Coordinator is replaced by a deterministic planner); delete once the r13 ADR is accepted.

## Totals

Tier per suite: `planned` (the default selection). The $30 reference
is a combined figure for V1 and V2 together; the plan defines no per-pass cap, so the
excess is stated for the combined total only.

| | Low to high |
|---|---|
| Total without contingency | $15.16 to $23.88 |
| Per-suite reserve | $3.54 to $5.64 |
| Global reserve (10% of cost plus per-suite reserve) | $1.87 to $2.95 |
| Total with contingency | $20.58 to $32.47 |
| V1 without contingency | $2.36 to $3.12 |
| V1 with contingency | $3.17 to $4.18 |
| V2 without contingency | $12.81 to $20.77 |
| V2 with contingency | $17.41 to $28.29 |

Share of the total without contingency that rests on a run or on an estimate:

| Basis | Low to high | Share |
|---|---|---|
| measured | $4.25 to $4.94 | 28% of the low, 21% of the high |
| proxy | $10.92 to $18.94 | 72% of the low, 79% of the high |

The plan may exceed the $30 reference: the low estimate is within it, the high estimate is over by up to $2.47 (combined V1 and V2, with contingency). That possible excess is what the funding request can ask for.

| Suite | Tier | Without contingency | Per-suite reserve | Measured share | Pending policy approval |
|---|---|---|---|---|---|
| input-parser | planned | $1.37 to $1.74 | $0.34 to $0.44 | 100% of the low, 79% of the high | no |
| scenario-builder | planned | $0.46 to $0.99 | $0.09 to $0.20 | 0% of the low, 0% of the high | no |
| network-author | planned | $0.76 to $1.86 | $0.23 to $0.56 | 0% of the low, 0% of the high | no |
| demand-generator | planned | $0.19 to $0.54 | $0.05 to $0.13 | 0% of the low, 0% of the high | no |
| exp-01 | planned | $7.03 to $9.52 | $1.41 to $1.90 | 41% of the low, 37% of the high | no |
| expert-real-net | planned | $0.98 to $1.44 | $0.20 to $0.29 | 0% of the low, 0% of the high | no |
| expert-learning-effect | planned | $3.22 to $4.60 | $0.97 to $1.38 | 0% of the low, 0% of the high | no |
| output-composer | planned | $0.22 to $0.60 | $0.03 to $0.09 | 0% of the low, 0% of the high | yes |
| golden-path | planned | $0.94 to $2.57 | $0.24 to $0.64 | 0% of the low, 0% of the high | no |

## Totals per tier

Every live suite at the same tier, against the $30 reference (V1 and V2
combined, with contingency). Per-pass figures are with contingency.

| Tier | Without contingency | V1 | V2 | With contingency | Excess over cap |
|---|---|---|---|---|---|
| minimum | $10.51 to $16.41 | $2.71 to $3.63 | $11.54 to $18.67 | $14.25 to $22.30 | none |
| planned | $15.16 to $23.88 | $3.17 to $4.18 | $17.41 to $28.29 | $20.58 to $32.47 | up to $2.47 (may exceed) |
| extended | $47.71 to $94.92 | $3.17 to $4.18 | $61.28 to $124.40 | $64.45 to $128.58 | $34.45 to $98.58 |

## Suites whose shape is unfixed

Early ranges for these are not a commitment; each is fixed once its benchmark exists.

- Scenario Builder (`scenario-builder`)
- Network Author (`network-author`)
- Demand Generator (`demand-generator`)
- Network Expert, forced and free abstention (EXP-01) (`exp-01`)
- Network Expert on REAL-NET (`expert-real-net`)
- Network Expert learning effect (`expert-learning-effect`)
- Output Composer (`output-composer`)
- Golden-path integration (`golden-path`)
