# Expert benchmark — e45-smoke

Expert: v2 · Model: deepseek/deepseek-v4.1-flash · 4 questions × repetitions [1] = 8 runs · budget stops: 0 · estimated cost: $0.056

Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | 1.00 | n/a | >= 0.90 ✅ |
| desc_occ_accuracy | 1.00 | n/a |  |
| desc_tt_accuracy | 1.00 | n/a |  |
| diag_accuracy | 1.00 | n/a |  |
| diag_mean_jaccard | 1.00 | n/a | >= 0.60 ✅ |
| cf_dir_accuracy | 1.00 | n/a | >= 0.75 ✅ |
| cf_topk_accuracy | n/a | n/a |  |
| cf_topk_mean_jaccard | n/a | n/a |  |
| cf_band_accuracy | n/a | n/a |  |
| brier | 0.01 | n/a | <= 0.25 ✅ |
| accepted_share | 1.00 | n/a | >= 1.00 ✅ |
| abstention_recall | n/a | n/a |  |
| abstention_false_requests | n/a | n/a |  |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| observed | 4 | 1.00 |

## Steps and cost by family

| Family | Runs | Steps | Text-only steps | Cut at token limit | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| cf-dir | 2 | 9 | 0 | 0 | 112946 | 4472 | 0.0196 |
| desc-occ | 2 | 8 | 0 | 0 | 76873 | 3194 | 0.0134 |
| desc-tt | 2 | 6 | 0 | 0 | 52810 | 2255 | 0.0093 |
| diag | 2 | 7 | 0 | 0 | 69444 | 4732 | 0.0133 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-desc-tt | 1 | ✅ | predicted 23.40 s, gold 23.40 s |
| S00-diag | 1 | ✅ | predicted ['A2B2', 'E3E2', 'B2C2'], gold ['A2B2', 'E3E2', 'B2C2'], jaccard 1.00 |
| S03-desc-occ | 1 | ✅ | predicted ['B1B0'], gold ['B1B0'] |
| S09-cf-dir | 1 | ✅ | predicted increase, gold increase |
