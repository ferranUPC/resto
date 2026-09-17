# Expert benchmark — v2-retry-failed

Expert: v2 · Model: deepseek/deepseek-v4.1-flash · 7 questions × repetitions [1] = 7 runs · budget stops: 3 · estimated cost: $0.104

Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | n/a | n/a |  |
| desc_occ_accuracy | n/a | n/a |  |
| desc_tt_accuracy | n/a | n/a |  |
| diag_accuracy | 0.50 | n/a |  |
| diag_mean_jaccard | 0.50 | n/a | >= 0.60 ❌ |
| cf_dir_accuracy | n/a | n/a |  |
| cf_topk_accuracy | 1.00 | n/a |  |
| cf_topk_mean_jaccard | 1.00 | n/a |  |
| cf_band_accuracy | n/a | n/a |  |
| brier | 0.04 | n/a | <= 0.25 ✅ |
| accepted_share | 0.57 | n/a | >= 1.00 ❌ |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| observed | 4 | 1.00 |

## Steps and cost by family

| Family | Runs | Steps | Text-only steps | Cut at token limit | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| cf-topk | 1 | 4 | 0 | 0 | 48258 | 2337 | 0.0086 |
| diag | 6 | 36 | 2 | 2 | 475443 | 39697 | 0.0951 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-diag | 1 | ❌ | no answer |
| S03-diag | 1 | ❌ | no answer |
| S05-diag | 1 | ✅ | predicted ['B0C0', 'A2B2', 'E3E2'], gold ['B0C0', 'A2B2', 'E3E2'], jaccard 1.00 |
| S06-diag | 1 | ✅ | predicted ['A2A1', 'A2B2', 'E3E2'], gold ['A2A1', 'A2B2', 'E3E2'], jaccard 1.00 |
| S12-cf-topk | 1 | ✅ | predicted ['B0C0', 'E3E2', 'C1C2', 'D0D1', 'D4D3'], gold ['B0C0', 'E3E2', 'C1C2', 'D0D1', 'D4D3'], jaccard 1.00 |
| S16-diag | 1 | ❌ | no answer |
| S17-diag | 1 | ✅ | predicted ['A2B2', 'C2D2', 'B1B2'], gold ['A2B2', 'C2D2', 'B1B2'], jaccard 1.00 |
