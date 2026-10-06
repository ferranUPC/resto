# Expert benchmark — e38-clocktime-smoke

Expert: v2 · Model: deepseek/deepseek-v4.1-flash · 15 questions × repetitions [1] = 15 runs · budget stops: 1 · estimated cost: $0.137

Scoring rules: eval/README.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | 1.00 | n/a | >= 0.90 ✅ |
| desc_occ_accuracy | 1.00 | n/a |  |
| desc_tt_accuracy | 1.00 | n/a |  |
| diag_accuracy | 0.75 | n/a |  |
| diag_mean_jaccard | 0.75 | n/a | >= 0.60 ✅ |
| cf_dir_accuracy | 1.00 | n/a | >= 0.75 ✅ |
| cf_topk_accuracy | 1.00 | n/a |  |
| cf_topk_mean_jaccard | 1.00 | n/a |  |
| cf_band_accuracy | 1.00 | n/a | >= 0.50 ✅ |
| brier | 0.02 | n/a | <= 0.25 ✅ |
| accepted_share | 0.93 | n/a | >= 1.00 ❌ |
| abstention_recall | 0.00 | n/a | >= 0.70 ❌ |
| abstention_false_requests | n/a | n/a |  |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| observed | 14 | 1.00 |

## Steps and cost by family

| Family | Runs | Steps | Text-only steps | Cut at token limit | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| cf-band | 2 | 8 | 0 | 0 | 101094 | 4605 | 0.0179 |
| cf-dir | 2 | 8 | 0 | 0 | 102606 | 4910 | 0.0183 |
| cf-topk | 2 | 9 | 0 | 0 | 119675 | 5736 | 0.0214 |
| desc-occ | 2 | 8 | 0 | 0 | 81152 | 4400 | 0.0148 |
| desc-tt | 3 | 9 | 0 | 0 | 86255 | 3732 | 0.0152 |
| diag | 4 | 21 | 1 | 1 | 256434 | 18316 | 0.0495 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-desc-occ | 1 | ✅ | predicted [], gold [] |
| S00-desc-tt | 1 | ✅ | predicted 23.40 s, gold 23.40 s |
| S00-diag | 1 | ✅ | predicted ['A2B2', 'E3E2', 'B2C2'], gold ['A2B2', 'E3E2', 'B2C2'], jaccard 1.00 |
| S03-cf-topk | 1 | ✅ | predicted ['B1B0', 'A0B0', 'C1C2', 'B0C0', 'B0A0'], gold ['B1B0', 'A0B0', 'C1C2', 'B0C0', 'B0A0'], jaccard 1.00 |
| S05-diag | 1 | ❌ | no answer |
| S13-cf-band | 1 | ✅ | predicted +5.2 % (5-20%), gold 5-20% |
| S13-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S13-cf-topk | 1 | ✅ | predicted ['B2C2', 'D2C2', 'C2B2', 'C1C2', 'C2D2'], gold ['B2C2', 'D2C2', 'C2B2', 'C1C2', 'C2D2'], jaccard 1.00 |
| S13-desc-occ | 1 | ✅ | predicted ['B2C2', 'D2C2'], gold ['B2C2', 'D2C2'] |
| S13-desc-tt | 1 | ✅ | predicted 22.87 s, gold 22.87 s |
| S13-diag | 1 | ✅ | predicted ['B2C2', 'D2C2', 'A2B2'], gold ['B2C2', 'D2C2', 'A2B2'], jaccard 1.00 |
| S16-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S16-desc-tt | 1 | ✅ | predicted 27.09 s, gold 27.09 s |
| S16-diag | 1 | ✅ | predicted ['B2A2', 'E2D2', 'C2D2'], gold ['B2A2', 'E2D2', 'C2D2'], jaccard 1.00 |
| S17-cf-band | 1 | ✅ | predicted +7.6 % (5-20%), gold 5-20% |
