# Expert benchmark — v0-forced-1rep

Expert: v0 · Model: deepseek/deepseek-v4.1-flash · 117 questions × repetitions [1] = 117 runs · budget stops: 48 · estimated cost: $1.536

Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | 0.68 | n/a | >= 0.90 ❌ |
| desc_occ_accuracy | 0.55 | n/a |  |
| desc_tt_accuracy | 0.80 | n/a |  |
| diag_accuracy | 0.10 | n/a |  |
| diag_mean_jaccard | 0.10 | n/a | >= 0.60 ❌ |
| cf_dir_accuracy | 0.79 | n/a | >= 0.75 ✅ |
| cf_topk_accuracy | 0.00 | n/a |  |
| cf_topk_mean_jaccard | 0.00 | n/a |  |
| cf_band_accuracy | 0.89 | n/a | >= 0.50 ✅ |
| brier | 0.08 | n/a | <= 0.25 ✅ |
| accepted_share | 0.59 | n/a | >= 1.00 ❌ |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| inferred | 1 | 1.00 |
| observed | 68 | 0.88 |

## Steps and cost by family

| Family | Runs | Steps | Text-only steps | Cut at token limit | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| cf-band | 19 | 69 | 3 | 3 | 782672 | 50374 | 0.1476 |
| cf-dir | 19 | 95 | 1 | 1 | 1087101 | 74415 | 0.2077 |
| cf-topk | 19 | 114 | 39 | 38 | 2362393 | 114229 | 0.4229 |
| desc-occ | 20 | 88 | 3 | 3 | 1408540 | 59514 | 0.2470 |
| desc-tt | 20 | 88 | 1 | 1 | 779885 | 47088 | 0.1452 |
| diag | 20 | 119 | 29 | 29 | 1967434 | 117653 | 0.3657 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-desc-occ | 1 | ❌ | predicted ['B2C2'], gold [] |
| S00-desc-tt | 1 | ✅ | predicted 23.40 s, gold 23.40 s |
| S00-diag | 1 | ❌ | no answer |
| S01-cf-band | 1 | ✅ | predicted +11.4 % (5-20%), gold 5-20% |
| S01-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S01-cf-topk | 1 | ❌ | no answer |
| S01-desc-occ | 1 | ✅ | predicted ['A2B2', 'B1B2', 'B3B2'], gold ['A2B2', 'B1B2', 'B3B2'] |
| S01-desc-tt | 1 | ❌ | no answer |
| S01-diag | 1 | ❌ | no answer |
| S02-cf-band | 1 | ✅ | predicted +11.0 % (5-20%), gold 5-20% |
| S02-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S02-cf-topk | 1 | ❌ | no answer |
| S02-desc-occ | 1 | ✅ | predicted ['B2C2', 'C3C2'], gold ['B2C2', 'C3C2'] |
| S02-desc-tt | 1 | ❌ | no answer |
| S02-diag | 1 | ✅ | predicted ['B2C2', 'C3C2', 'A2B2'], gold ['B2C2', 'C3C2', 'A2B2'], jaccard 1.00 |
| S03-cf-band | 1 | ✅ | predicted +1.8 % (<5%), gold <5% |
| S03-cf-dir | 1 | ❌ | no answer |
| S03-cf-topk | 1 | ❌ | no answer |
| S03-desc-occ | 1 | ❌ | predicted ['B1B0', 'B2C2'], gold ['B1B0'] |
| S03-desc-tt | 1 | ❌ | no answer |
| S03-diag | 1 | ❌ | no answer |
| S04-cf-band | 1 | ✅ | predicted +1.3 % (<5%), gold <5% |
| S04-cf-dir | 1 | ❌ | no answer |
| S04-cf-topk | 1 | ❌ | no answer |
| S04-desc-occ | 1 | ❌ | predicted ['B1C1', 'B2C2'], gold ['B1C1'] |
| S04-desc-tt | 1 | ❌ | no answer |
| S04-diag | 1 | ❌ | no answer |
| S05-cf-band | 1 | ✅ | predicted +2.5 % (<5%), gold <5% |
| S05-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S05-cf-topk | 1 | ❌ | no answer |
| S05-desc-occ | 1 | ❌ | predicted ['B2C2'], gold [] |
| S05-desc-tt | 1 | ✅ | predicted 0.00 s, gold 0.00 s |
| S05-diag | 1 | ❌ | no answer |
| S06-cf-band | 1 | ✅ | predicted +1.3 % (<5%), gold <5% |
| S06-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S06-cf-topk | 1 | ❌ | no answer |
| S06-desc-occ | 1 | ✅ | predicted [], gold [] |
| S06-desc-tt | 1 | ✅ | predicted 0.00 s, gold 0.00 s |
| S06-diag | 1 | ❌ | no answer |
| S07-cf-band | 1 | ✅ | predicted +5.0 % (5-20%), gold 5-20% |
| S07-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S07-cf-topk | 1 | ❌ | no answer |
| S07-desc-occ | 1 | ✅ | predicted ['C2D2'], gold ['C2D2'] |
| S07-desc-tt | 1 | ✅ | predicted 0.00 s, gold 0.00 s |
| S07-diag | 1 | ❌ | no answer |
| S08-cf-band | 1 | ✅ | predicted +11.4 % (5-20%), gold 5-20% |
| S08-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S08-cf-topk | 1 | ❌ | no answer |
| S08-desc-occ | 1 | ✅ | predicted ['A2B2', 'B1B2', 'B3B2'], gold ['A2B2', 'B1B2', 'B3B2'] |
| S08-desc-tt | 1 | ✅ | predicted 0.00 s, gold 0.00 s |
| S08-diag | 1 | ✅ | predicted ['A2B2', 'B1B2', 'B3B2'], gold ['B1B2', 'A2B2', 'B3B2'], jaccard 1.00 |
| S09-cf-band | 1 | ✅ | predicted +0.7 % (<5%), gold <5% |
| S09-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S09-cf-topk | 1 | ❌ | no answer |
| S09-desc-occ | 1 | ✅ | predicted ['B2C2'], gold ['B2C2'] |
| S09-desc-tt | 1 | ✅ | predicted 60.14 s, gold 60.14 s |
| S09-diag | 1 | ❌ | no answer |
| S10-cf-band | 1 | ✅ | predicted -0.3 % (<5%), gold <5% |
| S10-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S10-cf-topk | 1 | ❌ | no answer |
| S10-desc-occ | 1 | ❌ | predicted ['B2C2'], gold [] |
| S10-desc-tt | 1 | ✅ | predicted 47.19 s, gold 47.19 s |
| S10-diag | 1 | ❌ | no answer |
| S11-cf-band | 1 | ✅ | predicted +0.6 % (<5%), gold <5% |
| S11-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S11-cf-topk | 1 | ❌ | no answer |
| S11-desc-occ | 1 | ❌ | predicted ['B2C2', 'C2D2'], gold ['B2C2'] |
| S11-desc-tt | 1 | ✅ | predicted 39.44 s, gold 39.44 s |
| S11-diag | 1 | ❌ | no answer |
| S12-cf-band | 1 | ✅ | predicted -0.0 % (<5%), gold <5% |
| S12-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S12-cf-topk | 1 | ❌ | no answer |
| S12-desc-occ | 1 | ❌ | predicted ['B2C2'], gold [] |
| S12-desc-tt | 1 | ✅ | predicted 44.04 s, gold 44.04 s |
| S12-diag | 1 | ❌ | no answer |
| S13-cf-band | 1 | ❌ | no answer |
| S13-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S13-cf-topk | 1 | ❌ | no answer |
| S13-desc-occ | 1 | ✅ | predicted ['B2C2', 'D2C2'], gold ['B2C2', 'D2C2'] |
| S13-desc-tt | 1 | ✅ | predicted 22.87 s, gold 22.87 s |
| S13-diag | 1 | ❌ | no answer |
| S14-cf-band | 1 | ✅ | predicted +1.1 % (<5%), gold <5% |
| S14-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S14-cf-topk | 1 | ❌ | no answer |
| S14-desc-occ | 1 | ❌ | no answer |
| S14-desc-tt | 1 | ✅ | predicted 33.51 s, gold 33.51 s |
| S14-diag | 1 | ❌ | no answer |
| S15-cf-band | 1 | ✅ | predicted +2.9 % (<5%), gold <5% |
| S15-cf-dir | 1 | ❌ | no answer |
| S15-cf-topk | 1 | ❌ | no answer |
| S15-desc-occ | 1 | ✅ | predicted ['C2D2', 'D2C2', 'E2D2'], gold ['C2D2', 'D2C2', 'E2D2'] |
| S15-desc-tt | 1 | ✅ | predicted 29.15 s, gold 29.15 s |
| S15-diag | 1 | ❌ | no answer |
| S16-cf-band | 1 | ❌ | no answer |
| S16-cf-dir | 1 | ❌ | no answer |
| S16-cf-topk | 1 | ❌ | no answer |
| S16-desc-occ | 1 | ❌ | predicted ['E2D2'], gold [] |
| S16-desc-tt | 1 | ✅ | predicted 24.96 s, gold 24.96 s |
| S16-diag | 1 | ❌ | no answer |
| S17-cf-band | 1 | ✅ | predicted +7.6 % (5-20%), gold 5-20% |
| S17-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S17-cf-topk | 1 | ❌ | no answer |
| S17-desc-occ | 1 | ✅ | predicted ['B2C2', 'C2D2'], gold ['B2C2', 'C2D2'] |
| S17-desc-tt | 1 | ✅ | predicted 21.84 s, gold 21.84 s |
| S17-diag | 1 | ❌ | no answer |
| S18-cf-band | 1 | ✅ | predicted -4.5 % (<5%), gold <5% |
| S18-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S18-cf-topk | 1 | ❌ | no answer |
| S18-desc-occ | 1 | ✅ | predicted [], gold [] |
| S18-desc-tt | 1 | ✅ | predicted 23.80 s, gold 23.80 s |
| S18-diag | 1 | ❌ | no answer |
| S19-cf-band | 1 | ✅ | predicted +16.0 % (5-20%), gold 5-20% |
| S19-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S19-cf-topk | 1 | ❌ | no answer |
| S19-desc-occ | 1 | ✅ | predicted ['A2B2', 'B2C2', 'C2D2', 'E3E2'], gold ['A2B2', 'B2C2', 'C2D2', 'E3E2'] |
| S19-desc-tt | 1 | ✅ | predicted 32.00 s, gold 32.00 s |
| S19-diag | 1 | ❌ | no answer |
