# Input Parser benchmark — smoke-v1

9 requests, 9 runs (repetitions [1]), models ['deepseek/deepseek-v4.1-flash'], parser ['v1']; $0.0099, mean 4730 input / 648 output tokens; stop reasons {'output': 9}.

| Metric | Result | E5.1 threshold | Met |
|---|---|---|---|
| schema_validity | 100.0 % (9/9) | ≥ 98% | yes |
| intent | 100.0 % (7/7) | ≥ 85% | yes |
| interventions | 85.7 % (6/7) | ≥ 85% | yes |
| topology_changes | 85.7 % (6/7) | ≥ 85% | yes |
| metrics_of_interest | 85.7 % (6/7) | ≥ 85% | yes |
| ambiguity_detection | 100.0 % (2/2) | ≥ 80% | yes |
| arm_structure | 66.7 % (2/3) | ≥ 90% | **no** |

Reported, not graded:

- arm_structure_single: 100.0 % (4/4)
- required_arms: 66.7 % (2/3)
- spurious_ambiguity: 0.0 % (0/7)
- used_shorthand: 100.0 % (4/4)
- network_ref: 85.7 % (6/7)
- demand_ref: 100.0 % (7/7)
- time_window: 100.0 % (7/7)
- consistency across variants: —

## By category

| category | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| adversarial | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | — | — |
| ambiguous | 100.0 % (1/1) | — | — | — | — | 100.0 % (1/1) | — |
| combined | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | 100.0 % (1/1) | — | — |
| multi_arm | 100.0 % (3/3) | 100.0 % (3/3) | 66.7 % (2/3) | 66.7 % (2/3) | 66.7 % (2/3) | — | 66.7 % (2/3) |
| out_of_scope | 100.0 % (1/1) | — | — | — | — | 100.0 % (1/1) | — |
| single | 100.0 % (2/2) | 100.0 % (2/2) | 100.0 % (2/2) | 100.0 % (2/2) | 100.0 % (2/2) | — | — |

## By split

| split | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| dev | 100.0 % (9/9) | 100.0 % (7/7) | 85.7 % (6/7) | 85.7 % (6/7) | 85.7 % (6/7) | 100.0 % (2/2) | 66.7 % (2/3) |

## By lang

| lang | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| en | 100.0 % (9/9) | 100.0 % (7/7) | 85.7 % (6/7) | 85.7 % (6/7) | 85.7 % (6/7) | 100.0 % (2/2) | 66.7 % (2/3) |

## By style

| style | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| plain | 100.0 % (9/9) | 100.0 % (7/7) | 85.7 % (6/7) | 85.7 % (6/7) | 85.7 % (6/7) | 100.0 % (2/2) | 66.7 % (2/3) |

## By vague

| vague | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| none | 100.0 % (9/9) | 100.0 % (7/7) | 85.7 % (6/7) | 85.7 % (6/7) | 85.7 % (6/7) | 100.0 % (2/2) | 66.7 % (2/3) |

## By noise

| noise | schema_validity | intent | interventions | topology_changes | metrics_of_interest | ambiguity_detection | arm_structure |
|---|---|---|---|---|---|---|---|
| none | 100.0 % (9/9) | 100.0 % (7/7) | 85.7 % (6/7) | 85.7 % (6/7) | 85.7 % (6/7) | 100.0 % (2/2) | 66.7 % (2/3) |

## Failures (1)

### `R065` rep 1 — interventions, topology_changes, metrics_of_interest, arm_structure

> On DEV-NET I have four measures and three network changes, and I do not want every combination, only the ones below, all by mean travel time. The measures: A, closing lane 1 of edge B0C0 from 08:00 to 08:30; B, limiting edge B2C2 to 30 km/h from 08:00 to 09:00; C, switching the traffic light at junction C2 to program 1 from 08:00 to 09:00; D, limiting the new edge NEW3 to 30 km/h from 08:00 to 09:00. The changes: 1, widening edge C0D0 to three lanes; 2, removing edge B1C1 for good; 3, building a two-lane edge NEW3 from junction B1 to junction C2 with a 50 km/h limit. First, which is faster, A or B? Compare those two with each other only. With change 1 we can still do A but not B, although we can do C: with change 1 in place, which is faster, A or C? With change 2, does B work as well as it does on today's network? Finally, does change 3 on its own help compared with today, and does adding D to change 3 improve on change 3 alone?

Gold: intent `compare` · network `DEV-NET` · metrics mean_travel_time
- arm `a`: `lane_closure(B0C0/1, 08:00–08:30)`
- arm `b`: `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `widened_a`: `set_lanes(edge_id=C0D0, lanes=3)` + `lane_closure(B0C0/1, 08:00–08:30)`
- arm `widened_c`: `set_lanes(edge_id=C0D0, lanes=3)` + `signal_program(C2, program_id=1, 08:00–09:00)`
- arm `removed_b`: `remove_edge(edge_id=B1C1)` + `speed_limit(B2C2, speed=8.333, 08:00–09:00)`
- arm `new_edge`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)`
- arm `new_edge_d`: `add_edge(from_junction=B1, to_junction=C2, lanes=2, speed=13.889, edge_id=NEW3)` + `speed_limit(NEW3, speed=8.333, 08:00–09:00)`
- contrasts: `a` vs `b`, `widened_a` vs `widened_c`, `removed_b` vs `b`, `new_edge` vs `base`, `new_edge_d` vs `new_edge`

Parsed: intent `compare`

