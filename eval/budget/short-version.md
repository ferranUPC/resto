# Evaluation budget (short version)

Generated from `eval/budget/cost-data.toml` by `python -m eval.budget`; do not edit.
All figures are low-to-high ranges in USD. Runs are agent runs. `measured` rests on a
recorded run, `proxy` on an estimate. Model capability is given as a level, not a model.

## Suites

Runs and cost are shown as minimum / planned (cost before contingency).

| Suite | Measures | Threshold read | Pass | Runs | Basis | Cost | Shape |
|---|---|---|---|---|---|---|---|
| Input Parser | Structured-output agreement of the Parser on the request bank: validity, intent, interventions, topology, metrics, ambiguity, arm structure, consistency across runs | DoD 4.1 (E5.1); N4: intent agreement >= 95 % over 3 runs on held-out | V1+V2 | 2214 / 1476 | measured + proxy | $0.92 to $1.16 / $1.37 to $1.74 | fixed |
| Scenario Builder | Builder bank: does the Builder turn a request into a valid stored scenario and compare it to the gold scenario, per case | DoD E2.7 (Builder bank, 3 repetitions) | V1+V2 | 110 / 80 | proxy | $0.34 to $0.72 / $0.46 to $0.99 | unfixed |
| Network Author | GEN-LOCATIONS generation and derivation of edited networks: validity and match to the requested change, each generation seeded | DoD E6.2 (GEN-LOCATIONS and derivation, 3 repetitions) | V2 | 90 / 60 | proxy | $0.50 to $1.24 / $0.76 to $1.86 | unfixed |
| Demand Generator | Demand calibration: does generated demand reproduce the target flows within tolerance, each calibration run simulated with its own seed | DoD E7.4 (demand calibration) | V2 | 60 / 40 | proxy | $0.13 to $0.36 / $0.19 to $0.54 | unfixed |
| Network Expert, forced and free abstention (EXP-01) | Forced-mode accuracy across repetitions (N1) and whether the Expert abstains exactly where its forced answer would be wrong (N2), on the same 117 questions | DoD 4.7 per-family accuracy (E4.2-E4.4); abstention_recall >= 70 % and abstention_false_requests <= 30 % (E4.5) | V1+V2 | 858 / 624 | measured + proxy | $5.11 to $6.93 / $7.03 to $9.52 | unfixed |
| Network Expert on REAL-NET | Forced-mode accuracy of the Expert on the frozen real district: descriptive, Jaccard and direction metrics | DoD 4.7 REAL-NET (descriptive >= 85 %, Jaccard >= 0.5, direction >= 65 %; E8.5) | V2 | 120 / 80 | proxy | $0.66 to $0.96 / $0.98 to $1.44 | unfixed |
| Network Expert learning effect | Does accuracy rise as the Expert holds more prior experiences (0, 5, 15, 25): the learning-effect curve | DoD E4.9 (learning-effect curve) | V2 | 360 / 240 | proxy | $2.15 to $3.07 / $3.22 to $4.60 | unfixed |
| Output Composer | Hallucination review of composed text against the Expert's answer (no invented or contradicted claim), plus what the golden-path rubric already covers | DoD E5.7 rubric (Composer faithfulness) and E9.5 | V2 | 360 / 120 | proxy | $0.09 to $0.25 / $0.22 to $0.60 | unfixed |
| Golden-path integration | The 11 golden paths end to end through the CLI: pass/fail and the rubric over the composed answer | DoD E9.4 and E9.5 (golden paths), E5.7 rubric | V2 | 33 / 22 | proxy | $0.63 to $1.72 / $0.94 to $2.57 | unfixed |

## Totals

Against the $30 reference (V1 and V2 combined). With contingency.

| Tier | V1 | V2 | Combined | Excess over reference |
|---|---|---|---|---|
| minimum | $2.71 to $3.63 | $11.54 to $18.67 | $14.25 to $22.30 | none |
| planned | $3.17 to $4.18 | $17.41 to $28.29 | $20.58 to $32.47 | $0.00 to $2.47 |
| extended | $3.17 to $4.18 | $61.28 to $124.40 | $64.45 to $128.58 | $34.45 to $98.58 |

The planned tier exceeds the $30 reference by $0.00 to $2.47. That excess is what the funding request can ask for.

## Suites unfixed until their benchmark is designed

Early ranges, not a commitment: Scenario Builder, Network Author, Demand Generator, Network Expert, forced and free abstention (EXP-01), Network Expert on REAL-NET, Network Expert learning effect, Output Composer, Golden-path integration.
