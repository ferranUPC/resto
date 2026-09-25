# Expert benchmark — v3-diag-1rep

Expert: v3 · Model: deepseek/deepseek-v4.1-flash · 20 questions × repetitions [1] = 20 runs · budget stops: 18 · estimated cost: $0.324

Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | n/a | n/a |  |
| desc_occ_accuracy | n/a | n/a |  |
| desc_tt_accuracy | n/a | n/a |  |
| diag_accuracy | 0.10 | n/a |  |
| diag_mean_jaccard | 0.10 | n/a | >= 0.60 ❌ |
| diag_cause_accuracy | 1.00 | n/a | >= 0.70 ✅ |
| cf_dir_accuracy | n/a | n/a |  |
| cf_topk_accuracy | n/a | n/a |  |
| cf_topk_mean_jaccard | n/a | n/a |  |
| cf_band_accuracy | n/a | n/a |  |
| brier | 0.02 | n/a | <= 0.25 ✅ |
| accepted_share | 0.10 | n/a | >= 1.00 ❌ |
| abstention_recall | 0.00 | n/a | >= 0.70 ❌ |
| abstention_false_requests | n/a | n/a |  |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| observed | 2 | 1.00 |

## Steps and cost by family

| Family | Runs | Steps | Text-only steps | Cut at token limit | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| diag | 20 | 117 | 21 | 21 | 1641992 | 129789 | 0.3242 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-diag | 1 | ❌ | no answer |
| S01-diag | 1 | ❌ | no answer |
| S02-diag | 1 | ❌ | no answer |
| S03-diag | 1 | ❌ | no answer |
| S04-diag | 1 | ❌ | no answer |
| S05-diag | 1 | ❌ | no answer |
| S06-diag | 1 | ❌ | no answer |
| S07-diag | 1 | ❌ | no answer |
| S08-diag | 1 | ✅ | predicted ['B1B2', 'A2B2', 'B3B2'], gold ['B1B2', 'A2B2', 'B3B2'], jaccard 1.00; causes (predicted/gold) 3/3: B1B2 intervention/intervention, A2B2 intervention/intervention, B3B2 intervention/intervention |
| S09-diag | 1 | ❌ | no answer |
| S10-diag | 1 | ❌ | no answer |
| S11-diag | 1 | ❌ | no answer |
| S12-diag | 1 | ❌ | no answer |
| S13-diag | 1 | ❌ | no answer |
| S14-diag | 1 | ❌ | no answer |
| S15-diag | 1 | ✅ | predicted ['C2D2', 'E2D2', 'D2C2'], gold ['C2D2', 'E2D2', 'D2C2'], jaccard 1.00; causes (predicted/gold) 3/3: C2D2 intervention/intervention, E2D2 intervention/intervention, D2C2 spillback/spillback |
| S16-diag | 1 | ❌ | no answer |
| S17-diag | 1 | ❌ | no answer |
| S18-diag | 1 | ❌ | no answer |
| S19-diag | 1 | ❌ | no answer |
