# Expert benchmark — smoke-typed-2026-09-17

Model: deepseek/deepseek-v4.1-flash · 5 questions × repetitions [1] = 5 runs · budget stops: 1 · estimated cost: $0.052

Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | 1.00 | n/a | >= 0.90 ✅ |
| desc_occ_accuracy | 1.00 | n/a |  |
| desc_tt_accuracy | 1.00 | n/a |  |
| diag_accuracy | 0.00 | n/a |  |
| diag_mean_jaccard | 0.00 | n/a | >= 0.60 ❌ |
| cf_dir_accuracy | 1.00 | n/a | >= 0.75 ✅ |
| cf_topk_accuracy | n/a | n/a |  |
| cf_topk_mean_jaccard | n/a | n/a |  |
| cf_band_accuracy | 1.00 | n/a | >= 0.50 ✅ |
| brier | 0.01 | n/a | <= 0.25 ✅ |
| accepted_share | 0.80 | n/a | >= 1.00 ❌ |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| observed | 4 | 1.00 |

## Cost by family

| Family | Runs | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|
| cf-band | 1 | 29113 | 2241 | 0.0057 |
| cf-dir | 1 | 43117 | 3484 | 0.0086 |
| desc-occ | 1 | 80027 | 4780 | 0.0149 |
| desc-tt | 1 | 27783 | 1489 | 0.0051 |
| diag | 1 | 90256 | 7644 | 0.0181 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-desc-tt | 1 | ✅ | predicted 23.40 s, gold 23.40 s |
| S00-diag | 1 | ❌ | no answer |
| S03-desc-occ | 1 | ✅ | predicted ['B1B0'], gold ['B1B0'] |
| S09-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S17-cf-band | 1 | ✅ | predicted +7.6 % (5-20%), gold 5-20% |
