# Expert benchmark — smoke-typed-diag-retry

Model: deepseek/deepseek-v4.1-flash · 1 questions × repetitions [1] = 1 runs · budget stops: 1 · estimated cost: $0.022

Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | n/a | n/a |  |
| desc_occ_accuracy | n/a | n/a |  |
| desc_tt_accuracy | n/a | n/a |  |
| diag_accuracy | 0.00 | n/a |  |
| diag_mean_jaccard | 0.00 | n/a | >= 0.60 ❌ |
| cf_dir_accuracy | n/a | n/a |  |
| cf_topk_accuracy | n/a | n/a |  |
| cf_topk_mean_jaccard | n/a | n/a |  |
| cf_band_accuracy | n/a | n/a |  |
| brier | n/a | n/a |  |
| accepted_share | 0.00 | n/a | >= 1.00 ❌ |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|

## Cost by family

| Family | Runs | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|
| diag | 1 | 117910 | 6958 | 0.0219 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-diag | 1 | ❌ | no answer |
