# Evaluation budget (short version)

Generated from `eval/budget/cost-data.toml` by `python -m eval.budget`; do not edit.
All figures are low-to-high ranges in USD. Runs are agent runs. `measured` rests on a
recorded run, `proxy` on an estimate. Model capability is given as a level, not a model;
a level marked `pending policy approval` may not be used until the cost policy approves it.

## Suites

| Suite | Measures | Threshold read | Shape |
|---|---|---|---|
| Input Parser | Structured-output agreement of the Parser on the request bank: validity, intent, interventions, topology, metrics, ambiguity, arm structure, consistency across runs | DoD 4.1 (E5.1); N4: intent agreement >= 95 % over 3 runs on held-out | fixed |
| Scenario Builder | Builder bank: does the Builder turn a request into a valid stored scenario and compare it to the gold scenario, per case | DoD E2.7 (Builder bank, 3 repetitions) | unfixed |
| Network Author | GEN-LOCATIONS generation and derivation of edited networks: validity and match to the requested change, each generation seeded | DoD E6.2 (GEN-LOCATIONS and derivation, 3 repetitions) | unfixed |
| Demand Generator | Demand calibration: does generated demand reproduce the target flows within tolerance, each calibration run simulated with its own seed | DoD E7.4 (demand calibration) | unfixed |
| Network Expert, forced and free abstention (EXP-01) | Forced-mode accuracy across repetitions (N1) and whether the Expert abstains exactly where its forced answer would be wrong (N2), on the same 117 questions | DoD 4.7 per-family accuracy (E4.2-E4.4); abstention_recall >= 70 % and abstention_false_requests <= 30 % (E4.5) | unfixed |
| Network Expert on REAL-NET | Forced-mode accuracy of the Expert on the frozen real district: descriptive, Jaccard and direction metrics | DoD 4.7 REAL-NET (descriptive >= 85 %, Jaccard >= 0.5, direction >= 65 %; E8.5) | unfixed |
| Network Expert learning effect | Does accuracy rise as the Expert holds more prior experiences (0, 5, 15, 25): the learning-effect curve | DoD E4.9 (learning-effect curve) | unfixed |
| Output Composer | Hallucination review of composed text against the Expert's answer (no invented or contradicted claim), plus what the golden-path rubric already covers | DoD E5.7 rubric (Composer faithfulness) and E9.5 | unfixed |
| Golden-path integration | The 11 golden paths end to end through the CLI: pass/fail and the rubric over the composed answer | DoD E9.4 and E9.5 (golden paths), E5.7 rubric | unfixed |

## Design and cost per suite

Levels are those of the planned tier, with the models run at each (`x2` = two models).
Basis shows the share of cost resting on a run or an estimate. Reviewer hours are manual
time, never converted to USD. Runs, hours and cost (before contingency) are shown as
minimum / planned. The suite varies repetitions or seeds as stated. The interactive page
lets a reader set the inputs, the levels, the models per level and the repetitions of each
suite within bounds fixed in the cost data, starting from any of these three sizes.

| Suite | Pass | Levels tested | Varies | Runs | Basis | Reviewer hours | Cost |
|---|---|---|---|---|---|---|---|
| Input Parser | V1+V2 | reasoning-low x1 | repetitions | 1476 / 2214 | measured 79% + proxy 21% | none / none | $0.92 to $1.16 / $1.37 to $1.74 |
| Scenario Builder | V1+V2 | reasoning-low x1 | repetitions | 80 / 110 | proxy 100% | none / none | $0.34 to $0.72 / $0.46 to $0.99 |
| Network Author | V2 | reasoning-low x1 | seeds | 60 / 90 | proxy 100% | none / none | $0.50 to $1.24 / $0.76 to $1.86 |
| Demand Generator | V2 | reasoning-low x1 | seeds | 40 / 60 | proxy 100% | none / none | $0.13 to $0.36 / $0.19 to $0.54 |
| Network Expert, forced and free abstention (EXP-01) | V1+V2 | reasoning-low x1 | repetitions | 624 / 858 | measured 37% + proxy 63% | none / none | $5.11 to $6.93 / $7.03 to $9.52 |
| Network Expert on REAL-NET | V2 | reasoning-low x1 | repetitions | 80 / 120 | proxy 100% | none / none | $0.66 to $0.96 / $0.98 to $1.44 |
| Network Expert learning effect | V2 | reasoning-low x1 | seeds | 240 / 360 | proxy 100% | none / none | $2.15 to $3.07 / $3.22 to $4.60 |
| Output Composer | V2 | non-reasoning-low x2 (pending policy approval), reasoning-low x1 | repetitions | 120 / 360 | proxy 100% | 3 to 5 h / 9 to 15 h | $0.09 to $0.25 / $0.22 to $0.60 |
| Golden-path integration | V2 | reasoning-low x1 | repetitions | 22 / 33 | proxy 100% | none / none | $0.63 to $1.72 / $0.94 to $2.57 |

## Totals

Against the $30 reference (V1 and V2 combined). Reserve is the per-suite plus
the global contingency; V1 and V2 are with contingency.

| Tier | Without contingency | Reserve | With contingency | V1 | V2 | Excess |
|---|---|---|---|---|---|---|
| minimum | $10.51 to $16.41 | $3.74 to $5.89 | $14.25 to $22.30 | $2.71 to $3.63 | $11.54 to $18.67 | none |
| planned (pending policy approval) | $15.16 to $23.88 | $5.42 to $8.59 | $20.58 to $32.47 | $3.17 to $4.18 | $17.41 to $28.29 | up to $2.47 (may exceed) |
| extended (pending policy approval) | $47.71 to $94.92 | $16.74 to $33.66 | $64.45 to $128.58 | $3.17 to $4.18 | $61.28 to $124.40 | $34.45 to $98.58 |

Planned tier before contingency, by evidence: measured $4.25 to $4.94 (28% of the low, 21% of the high); proxy $10.92 to $18.94 (72% of the low, 79% of the high).

The planned tier may exceed the $30 reference: the low estimate is within it, the high estimate is over by up to $2.47 (combined V1 and V2, with contingency). That possible excess is what the funding request can ask for.

## Suites unfixed until their benchmark is designed

Early ranges, not a commitment: Scenario Builder, Network Author, Demand Generator, Network Expert, forced and free abstention (EXP-01), Network Expert on REAL-NET, Network Expert learning effect, Output Composer, Golden-path integration.
