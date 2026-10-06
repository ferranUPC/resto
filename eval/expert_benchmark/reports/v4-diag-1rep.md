# Expert benchmark — v4-diag-1rep

Expert: v4 · Model: deepseek/deepseek-v4.1-flash · 20 questions × repetitions [1] = 20 runs · budget stops: 8 · estimated cost: $0.283

Scoring rules: eval/README.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | n/a | n/a |  |
| desc_occ_accuracy | n/a | n/a |  |
| desc_tt_accuracy | n/a | n/a |  |
| diag_accuracy | 0.60 | n/a |  |
| diag_mean_jaccard | 0.60 | n/a | >= 0.60 ✅ |
| diag_cause_accuracy | 0.89 | n/a | >= 0.70 ✅ |
| cf_dir_accuracy | n/a | n/a |  |
| cf_topk_accuracy | n/a | n/a |  |
| cf_topk_mean_jaccard | n/a | n/a |  |
| cf_band_accuracy | n/a | n/a |  |
| brier | 0.02 | n/a | <= 0.25 ✅ |
| accepted_share | 0.60 | n/a | >= 1.00 ❌ |
| abstention_recall | 0.00 | n/a | >= 0.70 ❌ |
| abstention_false_requests | n/a | n/a |  |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| observed | 12 | 1.00 |

## Steps and cost by family

| Family | Runs | Steps | Text-only steps | Cut at token limit | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| diag | 20 | 113 | 11 | 11 | 1470510 | 104710 | 0.2834 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-diag | 1 | ✅ | predicted ['A2B2', 'E3E2', 'B2C2'], gold ['A2B2', 'E3E2', 'B2C2'], jaccard 1.00; causes (predicted/gold) 2/3: A2B2 spillback/signal, E3E2 signal/signal, B2C2 signal/signal |
| S01-diag | 1 | ✅ | predicted ['B1B2', 'A2B2', 'B3B2'], gold ['B1B2', 'A2B2', 'B3B2'], jaccard 1.00; causes (predicted/gold) 3/3: B1B2 intervention/intervention, A2B2 intervention/intervention, B3B2 intervention/intervention |
| S02-diag | 1 | ✅ | predicted ['B2C2', 'C3C2', 'A2B2'], gold ['B2C2', 'C3C2', 'A2B2'], jaccard 1.00; causes (predicted/gold) 3/3: B2C2 intervention/intervention, C3C2 intervention/intervention, A2B2 spillback/spillback |
| S03-diag | 1 | ❌ | no answer |
| S04-diag | 1 | ❌ | no answer |
| S05-diag | 1 | ❌ | no answer |
| S06-diag | 1 | ✅ | predicted ['A2A1', 'A2B2', 'E3E2'], gold ['A2A1', 'A2B2', 'E3E2'], jaccard 1.00; causes (predicted/gold) 3/3: A2A1 intervention/intervention, A2B2 signal/signal, E3E2 signal/signal |
| S07-diag | 1 | ❌ | no answer |
| S08-diag | 1 | ✅ | predicted ['B1B2', 'A2B2', 'B3B2'], gold ['B1B2', 'A2B2', 'B3B2'], jaccard 1.00; causes (predicted/gold) 3/3: B1B2 intervention/intervention, A2B2 intervention/intervention, B3B2 intervention/intervention |
| S09-diag | 1 | ✅ | predicted ['B2C2', 'A2B2', 'E3E2'], gold ['B2C2', 'A2B2', 'E3E2'], jaccard 1.00; causes (predicted/gold) 2/3: B2C2 intervention/intervention, A2B2 spillback/intervention, E3E2 signal/signal |
| S10-diag | 1 | ❌ | no answer |
| S11-diag | 1 | ❌ | no answer |
| S12-diag | 1 | ✅ | predicted ['E3E2', 'A2B2', 'B2C2'], gold ['E3E2', 'A2B2', 'B2C2'], jaccard 1.00; causes (predicted/gold) 1/3: E3E2 signal/signal, A2B2 spillback/signal, B2C2 spillback/signal |
| S13-diag | 1 | ✅ | predicted ['B2C2', 'D2C2', 'A2B2'], gold ['B2C2', 'D2C2', 'A2B2'], jaccard 1.00; causes (predicted/gold) 3/3: B2C2 intervention/intervention, D2C2 intervention/intervention, A2B2 spillback/spillback |
| S14-diag | 1 | ❌ | no answer |
| S15-diag | 1 | ✅ | predicted ['C2D2', 'E2D2', 'D2C2'], gold ['C2D2', 'E2D2', 'D2C2'], jaccard 1.00; causes (predicted/gold) 3/3: C2D2 intervention/intervention, E2D2 intervention/intervention, D2C2 spillback/spillback |
| S16-diag | 1 | ✅ | predicted ['B2A2', 'E2D2', 'C2D2'], gold ['B2A2', 'E2D2', 'C2D2'], jaccard 1.00; causes (predicted/gold) 3/3: B2A2 intervention/intervention, E2D2 signal/signal, C2D2 signal/signal |
| S17-diag | 1 | ✅ | predicted ['A2B2', 'C2D2', 'B1B2'], gold ['A2B2', 'C2D2', 'B1B2'], jaccard 1.00; causes (predicted/gold) 3/3: A2B2 signal/signal, C2D2 signal/signal, B1B2 signal/signal |
| S18-diag | 1 | ✅ | predicted ['E3E2', 'A2B2', 'A3A2'], gold ['E3E2', 'A2B2', 'A3A2'], jaccard 1.00; causes (predicted/gold) 3/3: E3E2 signal/signal, A2B2 signal/signal, A3A2 spillback/spillback |
| S19-diag | 1 | ❌ | no answer |
