# Expert benchmark — v1-forced-1rep

Expert: v1 · Model: deepseek/deepseek-v4.1-flash · 117 questions × repetitions [1] = 117 runs · budget stops: 7 · estimated cost: $0.976

Scoring rules: docs/evaluating-resto.md §4.4. Thresholds: DoD §4.7 (DEV-NET).

| Metric | Mean | Std | DoD |
|---|---|---|---|
| descriptive_accuracy | 1.00 | n/a | >= 0.90 ✅ |
| desc_occ_accuracy | 1.00 | n/a |  |
| desc_tt_accuracy | 1.00 | n/a |  |
| diag_accuracy | 0.70 | n/a |  |
| diag_mean_jaccard | 0.70 | n/a | >= 0.60 ✅ |
| cf_dir_accuracy | 1.00 | n/a | >= 0.75 ✅ |
| cf_topk_accuracy | 0.95 | n/a |  |
| cf_topk_mean_jaccard | 0.95 | n/a |  |
| cf_band_accuracy | 1.00 | n/a | >= 0.50 ✅ |
| brier | 0.02 | n/a | <= 0.25 ✅ |
| accepted_share | 0.94 | n/a | >= 1.00 ❌ |

## Accuracy by basis

| Basis | Answers | Accuracy |
|---|---|---|
| inferred | 1 | 1.00 |
| observed | 109 | 1.00 |

## Steps and cost by family

| Family | Runs | Steps | Text-only steps | Cut at token limit | Input tokens | Output tokens | Cost (USD) |
|---|---|---|---|---|---|---|---|
| cf-band | 19 | 72 | 0 | 0 | 852027 | 40068 | 0.1518 |
| cf-dir | 19 | 81 | 0 | 0 | 994464 | 48466 | 0.1782 |
| cf-topk | 19 | 79 | 0 | 0 | 958256 | 47136 | 0.1720 |
| desc-occ | 20 | 67 | 0 | 0 | 620709 | 36238 | 0.1148 |
| desc-tt | 20 | 62 | 0 | 0 | 556039 | 30723 | 0.1018 |
| diag | 20 | 111 | 3 | 3 | 1297480 | 104967 | 0.2576 |

## Per question

| Question | Rep | Correct | Detail |
|---|---|---|---|
| S00-desc-occ | 1 | ✅ | predicted [], gold [] |
| S00-desc-tt | 1 | ✅ | predicted 23.40 s, gold 23.40 s |
| S00-diag | 1 | ❌ | no answer |
| S01-cf-band | 1 | ✅ | predicted +11.4 % (5-20%), gold 5-20% |
| S01-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S01-cf-topk | 1 | ✅ | predicted ['B1B2', 'A2B2', 'B3B2', 'B2C2', 'C2D2'], gold ['B1B2', 'A2B2', 'B3B2', 'B2C2', 'C2D2'], jaccard 1.00 |
| S01-desc-occ | 1 | ✅ | predicted ['A2B2', 'B1B2', 'B3B2'], gold ['A2B2', 'B1B2', 'B3B2'] |
| S01-desc-tt | 1 | ✅ | answered no value |
| S01-diag | 1 | ✅ | predicted ['B1B2', 'A2B2', 'B3B2'], gold ['B1B2', 'A2B2', 'B3B2'], jaccard 1.00 |
| S02-cf-band | 1 | ✅ | predicted +11.0 % (5-20%), gold 5-20% |
| S02-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S02-cf-topk | 1 | ✅ | predicted ['B2C2', 'C3C2', 'C2D2', 'C1C2', 'B1B2'], gold ['B2C2', 'C3C2', 'C2D2', 'C1C2', 'B1B2'], jaccard 1.00 |
| S02-desc-occ | 1 | ✅ | predicted ['B2C2', 'C3C2'], gold ['B2C2', 'C3C2'] |
| S02-desc-tt | 1 | ✅ | answered no value |
| S02-diag | 1 | ✅ | predicted ['B2C2', 'C3C2', 'A2B2'], gold ['B2C2', 'C3C2', 'A2B2'], jaccard 1.00 |
| S03-cf-band | 1 | ✅ | predicted +1.8 % (<5%), gold <5% |
| S03-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S03-cf-topk | 1 | ✅ | predicted ['B1B0', 'A0B0', 'C1C2', 'B0C0', 'B0A0'], gold ['B1B0', 'A0B0', 'C1C2', 'B0C0', 'B0A0'], jaccard 1.00 |
| S03-desc-occ | 1 | ✅ | predicted ['B1B0'], gold ['B1B0'] |
| S03-desc-tt | 1 | ✅ | answered no value |
| S03-diag | 1 | ❌ | no answer |
| S04-cf-band | 1 | ✅ | predicted +1.3 % (<5%), gold <5% |
| S04-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S04-cf-topk | 1 | ✅ | predicted ['B1C1', 'C1C2', 'C0C1', 'C2D2', 'C2B2'], gold ['B1C1', 'C1C2', 'C0C1', 'C2D2', 'C2B2'], jaccard 1.00 |
| S04-desc-occ | 1 | ✅ | predicted ['B1C1'], gold ['B1C1'] |
| S04-desc-tt | 1 | ✅ | answered no value |
| S04-diag | 1 | ✅ | predicted ['B1C1', 'A2B2', 'E3E2'], gold ['B1C1', 'A2B2', 'E3E2'], jaccard 1.00 |
| S05-cf-band | 1 | ✅ | predicted +2.5 % (<5%), gold <5% |
| S05-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S05-cf-topk | 1 | ✅ | predicted ['B0C0', 'C1C0', 'C1C2', 'C0C1', 'C1D1'], gold ['B0C0', 'C1C0', 'C1C2', 'C0C1', 'C1D1'], jaccard 1.00 |
| S05-desc-occ | 1 | ✅ | predicted [], gold [] |
| S05-desc-tt | 1 | ✅ | answered no value |
| S05-diag | 1 | ❌ | no answer |
| S06-cf-band | 1 | ✅ | predicted +1.3 % (<5%), gold <5% |
| S06-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S06-cf-topk | 1 | ✅ | predicted ['A2A1', 'B1B2', 'B2C2', 'A1B1', 'C1C2'], gold ['A2A1', 'B1B2', 'B2C2', 'A1B1', 'C1C2'], jaccard 1.00 |
| S06-desc-occ | 1 | ✅ | predicted [], gold [] |
| S06-desc-tt | 1 | ✅ | answered no value |
| S06-diag | 1 | ❌ | no answer |
| S07-cf-band | 1 | ✅ | predicted +5.0 % (5-20%), gold 5-20% |
| S07-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S07-cf-topk | 1 | ✅ | predicted ['C2D2', 'D1D2', 'D2E2', 'D2D1', 'C1C2'], gold ['C2D2', 'D1D2', 'D2E2', 'D2D1', 'C1C2'], jaccard 1.00 |
| S07-desc-occ | 1 | ✅ | predicted ['C2D2'], gold ['C2D2'] |
| S07-desc-tt | 1 | ✅ | answered no value |
| S07-diag | 1 | ✅ | predicted ['C2D2', 'A2B2', 'E3E2'], gold ['C2D2', 'A2B2', 'E3E2'], jaccard 1.00 |
| S08-cf-band | 1 | ✅ | predicted +11.4 % (5-20%), gold 5-20% |
| S08-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S08-cf-topk | 1 | ✅ | predicted ['B1B2', 'A2B2', 'B3B2', 'B2C2', 'C2D2'], gold ['B1B2', 'A2B2', 'B3B2', 'B2C2', 'C2D2'], jaccard 1.00 |
| S08-desc-occ | 1 | ✅ | predicted ['A2B2', 'B1B2', 'B3B2'], gold ['A2B2', 'B1B2', 'B3B2'] |
| S08-desc-tt | 1 | ✅ | answered no value |
| S08-diag | 1 | ✅ | predicted ['B1B2', 'A2B2', 'B3B2'], gold ['B1B2', 'A2B2', 'B3B2'], jaccard 1.00 |
| S09-cf-band | 1 | ✅ | predicted +0.7 % (<5%), gold <5% |
| S09-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S09-cf-topk | 1 | ✅ | predicted ['B2C2', 'D2E2', 'C2D2', 'D3D2', 'D1E1'], gold ['B2C2', 'D2E2', 'C2D2', 'D3D2', 'D1E1'], jaccard 1.00 |
| S09-desc-occ | 1 | ✅ | predicted ['B2C2'], gold ['B2C2'] |
| S09-desc-tt | 1 | ✅ | predicted 60.14 s, gold 60.14 s |
| S09-diag | 1 | ✅ | predicted ['B2C2', 'A2B2', 'E3E2'], gold ['B2C2', 'A2B2', 'E3E2'], jaccard 1.00 |
| S10-cf-band | 1 | ✅ | predicted -0.3 % (<5%), gold <5% |
| S10-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S10-cf-topk | 1 | ✅ | predicted ['C1D1', 'D1D0', 'E0D0', 'D4D3', 'D1E1'], gold ['C1D1', 'D1D0', 'E0D0', 'D4D3', 'D1E1'], jaccard 1.00 |
| S10-desc-occ | 1 | ✅ | predicted [], gold [] |
| S10-desc-tt | 1 | ✅ | predicted 47.19 s, gold 47.19 s |
| S10-diag | 1 | ✅ | predicted ['A2B2', 'E3E2', 'B2C2'], gold ['A2B2', 'E3E2', 'B2C2'], jaccard 1.00 |
| S11-cf-band | 1 | ✅ | predicted +0.6 % (<5%), gold <5% |
| S11-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S11-cf-topk | 1 | ✅ | predicted ['B2C2', 'A2B2', 'C2D2', 'D2E2', 'D3D2'], gold ['B2C2', 'A2B2', 'C2D2', 'D2E2', 'D3D2'], jaccard 1.00 |
| S11-desc-occ | 1 | ✅ | predicted ['B2C2'], gold ['B2C2'] |
| S11-desc-tt | 1 | ✅ | predicted 39.44 s, gold 39.44 s |
| S11-diag | 1 | ✅ | predicted ['B2C2', 'C2D2', 'E3E2'], gold ['B2C2', 'C2D2', 'E3E2'], jaccard 1.00 |
| S12-cf-band | 1 | ✅ | predicted -0.0 % (<5%), gold <5% |
| S12-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S12-cf-topk | 1 | ❌ | no answer |
| S12-desc-occ | 1 | ✅ | predicted [], gold [] |
| S12-desc-tt | 1 | ✅ | predicted 44.04 s, gold 44.04 s |
| S12-diag | 1 | ✅ | predicted ['E3E2', 'A2B2', 'B2C2'], gold ['E3E2', 'A2B2', 'B2C2'], jaccard 1.00 |
| S13-cf-band | 1 | ✅ | predicted +5.2 % (5-20%), gold 5-20% |
| S13-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S13-cf-topk | 1 | ✅ | predicted ['B2C2', 'D2C2', 'C2B2', 'C1C2', 'C2D2'], gold ['B2C2', 'D2C2', 'C2B2', 'C1C2', 'C2D2'], jaccard 1.00 |
| S13-desc-occ | 1 | ✅ | predicted ['B2C2', 'D2C2'], gold ['B2C2', 'D2C2'] |
| S13-desc-tt | 1 | ✅ | predicted 22.87 s, gold 22.87 s |
| S13-diag | 1 | ✅ | predicted ['B2C2', 'D2C2', 'A2B2'], gold ['B2C2', 'D2C2', 'A2B2'], jaccard 1.00 |
| S14-cf-band | 1 | ✅ | predicted +1.1 % (<5%), gold <5% |
| S14-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S14-cf-topk | 1 | ✅ | predicted ['C2B2', 'B3B2', 'B1B2', 'A2B2', 'B2C2'], gold ['C2B2', 'B3B2', 'B1B2', 'A2B2', 'B2C2'], jaccard 1.00 |
| S14-desc-occ | 1 | ✅ | predicted ['C2B2', 'D2C2'], gold ['C2B2', 'D2C2'] |
| S14-desc-tt | 1 | ✅ | predicted 33.51 s, gold 33.51 s |
| S14-diag | 1 | ✅ | predicted ['C2B2', 'D2C2', 'B2A2'], gold ['C2B2', 'D2C2', 'B2A2'], jaccard 1.00 |
| S15-cf-band | 1 | ✅ | predicted +2.9 % (<5%), gold <5% |
| S15-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S15-cf-topk | 1 | ✅ | predicted ['C2D2', 'E2D2', 'D3D2', 'D2C2', 'D2E2'], gold ['C2D2', 'E2D2', 'D3D2', 'D2C2', 'D2E2'], jaccard 1.00 |
| S15-desc-occ | 1 | ✅ | predicted ['C2D2', 'D2C2', 'E2D2'], gold ['C2D2', 'D2C2', 'E2D2'] |
| S15-desc-tt | 1 | ✅ | predicted 29.15 s, gold 29.15 s |
| S15-diag | 1 | ✅ | predicted ['C2D2', 'E2D2', 'D2C2'], gold ['C2D2', 'E2D2', 'D2C2'], jaccard 1.00 |
| S16-cf-band | 1 | ✅ | predicted +0.3 % (<5%), gold <5% |
| S16-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S16-cf-topk | 1 | ✅ | predicted ['B2A2', 'A3A2', 'A1A2', 'B2C2', 'A2B2'], gold ['B2A2', 'A3A2', 'A1A2', 'B2C2', 'A2B2'], jaccard 1.00 |
| S16-desc-occ | 1 | ✅ | predicted [], gold [] |
| S16-desc-tt | 1 | ✅ | predicted 24.96 s, gold 24.96 s |
| S16-diag | 1 | ❌ | no answer |
| S17-cf-band | 1 | ✅ | predicted +7.6 % (5-20%), gold 5-20% |
| S17-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S17-cf-topk | 1 | ✅ | predicted ['B1B2', 'C2D2', 'A2B2', 'B3B2', 'C1C2'], gold ['B1B2', 'C2D2', 'A2B2', 'B3B2', 'C1C2'], jaccard 1.00 |
| S17-desc-occ | 1 | ✅ | predicted ['B2C2', 'C2D2'], gold ['B2C2', 'C2D2'] |
| S17-desc-tt | 1 | ✅ | predicted 21.84 s, gold 21.84 s |
| S17-diag | 1 | ❌ | no answer |
| S18-cf-band | 1 | ✅ | predicted -4.5 % (<5%), gold <5% |
| S18-cf-dir | 1 | ✅ | predicted decrease, gold decrease |
| S18-cf-topk | 1 | ✅ | predicted ['C2D2', 'C1C2', 'B1B2', 'A2B2', 'B2C2'], gold ['C2D2', 'C1C2', 'B1B2', 'A2B2', 'B2C2'], jaccard 1.00 |
| S18-desc-occ | 1 | ✅ | predicted [], gold [] |
| S18-desc-tt | 1 | ✅ | predicted 23.80 s, gold 23.80 s |
| S18-diag | 1 | ✅ | predicted ['E3E2', 'A2B2', 'A3A2'], gold ['E3E2', 'A2B2', 'A3A2'], jaccard 1.00 |
| S19-cf-band | 1 | ✅ | predicted +16.0 % (5-20%), gold 5-20% |
| S19-cf-dir | 1 | ✅ | predicted increase, gold increase |
| S19-cf-topk | 1 | ✅ | predicted ['B2C2', 'C2D2', 'D2E2', 'C1C2', 'A2B2'], gold ['B2C2', 'C2D2', 'D2E2', 'C1C2', 'A2B2'], jaccard 1.00 |
| S19-desc-occ | 1 | ✅ | predicted ['A2B2', 'B2C2', 'C2D2', 'E3E2'], gold ['A2B2', 'B2C2', 'C2D2', 'E3E2'] |
| S19-desc-tt | 1 | ✅ | predicted 32.00 s, gold 32.00 s |
| S19-diag | 1 | ✅ | predicted ['B2C2', 'C2D2', 'A2B2'], gold ['B2C2', 'C2D2', 'A2B2'], jaccard 1.00 |
