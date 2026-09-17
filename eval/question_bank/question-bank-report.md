# Question bank (work-plan E3.2)

Built by `python -m eval.question_bank.build` from `eval/scenario_matrix/rows.py`'s 20 rows, against `eval/scenario_matrix/matrix.db`. 117 questions total (work-plan floor: 60): 40 descriptive, 20 diagnostic, 57 counterfactual.

| id | intent | text |
|---|---|---|
| S00-desc-occ | describe | Which edges exceed 3.5% occupancy between 0s and 300s in the scenario with no interventions? |
| S00-desc-tt | describe | What is the mean travel time on B2C2 between 0s and 300s in the scenario with no interventions? |
| S00-diag | diagnose | Which three edges form the main bottleneck between 0s and 300s in the scenario with no interventions, and why? |
| S01-desc-occ | describe | Which edges exceed 3.5% occupancy between 0s and 300s in the scenario with lane_closure B2C2 lane 0, [0, 300)? |
| S01-desc-tt | describe | What is the mean travel time on B2C2 between 0s and 300s in the scenario with lane_closure B2C2 lane 0, [0, 300)? |
| S01-diag | diagnose | Which three edges form the main bottleneck between 0s and 300s in the scenario with lane_closure B2C2 lane 0, [0, 300), and why? |
| S01-cf-dir | counterfactual | If lane_closure B2C2 lane 0, [0, 300), does mean delay on B2C2 increase, decrease, or stay within 5% relative to the baseline, over 0s-300s? |
| S01-cf-topk | counterfactual | If lane_closure B2C2 lane 0, [0, 300), which 5 edges change the most in delay relative to the baseline, over 0s-300s? |
| S01-cf-band | counterfactual | By roughly how much does network-wide mean delay change if lane_closure B2C2 lane 0, [0, 300)? |
| S02-desc-occ | describe | Which edges exceed 3.5% occupancy between 0s and 300s in the scenario with lane_closure C2D2 lane 0, [0, 300)? |

Full bank: `question-bank.json` (117 entries).

**Scope note on diagnostic items:** each `-diag` entry's `gold_answer["top_3"]` is machine-gradeable today (Jaccard against the Expert's own answer, DoD §4.7). `gold_answer["reason"]` (merge/signal/demand) is *not* wired to any grading metric yet - how to score the Expert's free-text "why" against it is an open question (architecture doc §8), left for E3.3 to decide. The field is present and free to compute, just unused by any metric today.
